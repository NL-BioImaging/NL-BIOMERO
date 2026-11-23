#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008 Glencoe Software, Inc.  All Rights Reserved.
# Use is subject to license terms supplied in LICENSE.txt
#

"""
OMERO Grid Processor
"""

import contextlib
import logging
from datetime import datetime, timezone
import os
import socket
import time
import signal
import uuid
from typing import (TYPE_CHECKING, Any, Callable, Dict, Iterable, Iterator,
                    List, Optional, Set, Tuple)
from omero_ext import killableprocess as subprocess


import Ice
import omero
import omero.clients
import omero.scripts
import omero.util
import omero.util.concurrency

from omero.util import load_dotted_class
from omero.util.temp_files import create_path, remove_path
from omero.util.decorators import remoted, perf, locked, wraps
from omero.rtypes import rint, rlong
from omero_ext.path import path

try:
    from biomero.constants import slurm_env as _slurm_env
    _BIOMERO_ENV_VARS = [
        v for k, v in vars(_slurm_env).items()
        if not k.startswith("_") and isinstance(v, str)
    ]
except ImportError:
    _slurm_env = None
    _BIOMERO_ENV_VARS = []

# The biomero pinned for this image provides both (the detached supervisor
# needs the claim), so there is no fallback.
from biomero import constants
from biomero.constants import LAUNCHER_CLAIM_LEASE_SECONDS
from biomero.eventsourcing import WorkflowInterrupted

if TYPE_CHECKING:  # only for the type hints
    from biomero import WorkflowTracker
    from biomero.slurm_client import SlurmClient
    from omero.gateway import BlitzGateway

sys = __import__("sys")


def with_context(func, context):
    """ Decorator for invoking Ice methods with a context """
    def handler(*args, **kwargs):
        args = list(args)
        args.append(context)
        return func(*args, **kwargs)
    handler = wraps(func)(handler)
    return handler


class WithGroup(object):
    """
    Wraps a ServiceInterfacePrx instance and applies
    a "omero.group" to the passed context on every
    invocation.

    For example, using a job handle as root requires logging
    manually into the group. (ticket:2044)
    """

    def __init__(self, service, group_id):
        self._service = service
        self._group_id = str(group_id)

    def _get_ctx(self, group=None):
        ctx = self._service.ice_getCommunicator()\
            .getImplicitContext().getContext()
        ctx = dict(ctx)
        ctx["omero.group"] = str(group)
        return ctx

    def __getattr__(self, name):
        if name.startswith("_"):
            return self.__dict__[name]
        elif hasattr(self._service, name):
            method = getattr(self._service, name)
            ctx = self._get_ctx(self._group_id)
            return with_context(method, ctx)
        raise AttributeError(
            "'%s' object has no attribute '%s'" % (self.service, name))


class ProcessI(omero.grid.Process, omero.util.SimpleServant):
    """
    Wrapper around a subprocess.Popen instance. Returned by ProcessorI
    when a job is submitted. This implementation uses the given
    interpreter to call a file that must be named "script" in the
    generated temporary directory.

    Call is equivalent to:

    cd TMP_DIR
    ICE_CONFIG=./config interpreter ./script >out 2>err &

    The properties argument is used to generate the ./config file.

    The params argument may be null in which case this process
    is being used solely to calculate the parameters for the script
    ("omero.scripts.parse=true")

    If iskill is True, then on cleanup, this process will reap the
    attached session completely.
    """

    def __init__(self, ctx, interpreter, properties, params, iskill=False,
                 Popen=subprocess.Popen,
                 callback_cast=omero.grid.ProcessCallbackPrx.uncheckedCast,
                 omero_home=path.getcwd()):
        """
        Popen and callback_Cast are primarily for testing.
        """
        omero.util.SimpleServant.__init__(self, ctx)
        self.omero_home = omero_home  #: Location for OMERO_HOME/lib/python
        #: Executable which will be used on the script
        self.interpreter = interpreter
        #: Properties used to create an Ice.Config
        self.properties = properties
        #: JobParams for this script. Possibly None if a ParseJob
        self.params = params
        #: Whether or not, cleanup should kill the session
        self.iskill = iskill
        #: Function which should be used for creating processes
        self.Popen = Popen
        #: Function used to cast all ProcessCallback proxies
        self.callback_cast = callback_cast
        # Non arguments (mutable state)
        self.rcode = None  #: return code from popen
        self.callbacks = {}  #: dictionary from id strings to callback proxies
        self.popen = None  #: process. if None then this instance isn't alive.
        self.pid = None  #: pid of the process. Once set, isn't nulled.
        self.started = None  #: time the process started
        self.stopped = None  #: time of deactivation
        #: status which will be sent on set_job_status
        self.final_status = None
        # Non arguments (immutable state)
        #: session this instance is tied to
        self.uuid = properties["omero.user"]

        # More fields set by these methods
        self.make_files()
        self.make_env()
        self.make_config()
        self.logger.info("Created %s in %s" % (self.uuid, self.dir))

    #
    # Initialization methods
    #

    def make_env(self):
        self.env = omero.util.Environment(
            "CLASSPATH",
            "DISPLAY",
            "DYLD_LIBRARY_PATH",
            "HOME",
            "JYTHON_HOME",
            "LC_ALL",
            "LANG",
            "LANGUAGE",
            "LD_LIBRARY_PATH",
            "MLABRAW_CMD_STR",
            "OMERODIR",
            "OMERO_TEMPDIR",
            "OMERO_TMPDIR",
            "PATH",
            "PYTHONPATH",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "FTP_PROXY",
            "PERSISTENCE_MODULE",
            "SQLALCHEMY_URL",
            "INGEST_TRACKING_DB_URL",
            "IMPORTER_ENABLED",
            "IMPORT_MOUNT_PATH",
            "OMERO_BIOMERO_CONFIG_FILE",
            "OMERO_BIOMERO_GROUP_MAPPINGS_FILE",
            # All BIOMERO_* env vars forwarded dynamically from biomero.constants.slurm_env.
            # Add new env vars there; they will be picked up here automatically.
            *_BIOMERO_ENV_VARS,
        )

        # Since we know the location of our OMERO, we're going to
        # force the value for OMERO_HOME. This is useful in scripts
        # which want to be able to find their location.
        self.env.set("OMERO_HOME", self.omero_home)

        # WORKAROUND
        # Currently duplicating the logic here as in the PYTHONPATH
        # setting of the grid application descriptor (see etc/grid/*.xml)
        # This should actually be taken care of in the descriptor itself
        # by having setting PYTHONPATH to an absolute value. This is
        # not currently possible with IceGrid (without using icepatch --
        # see 39.17.2 "node.datadir).
        self.env.append("PYTHONPATH", str(self.omero_home / "lib" / "python"))
        self.env.set("ICE_CONFIG", str(self.config_path))
        # Also actively adding all jars under lib/server to the CLASSPATH
        lib_server = self.omero_home / "lib" / "server"
        for jar_file in lib_server.walk("*.jar"):
            self.env.append("CLASSPATH", str(jar_file))

    def make_files(self):
        self.dir = create_path("process", ".dir", folder=True)
        self.script_path = self.dir / "script"
        self.config_path = self.dir / "config"
        self.stdout_path = self.dir / "out"
        self.stderr_path = self.dir / "err"

    def make_config(self):
        """
        Creates the ICE_CONFIG file used by the client.
        """
        config_file = open(str(self.config_path), "w")
        try:
            for key in self.properties.keys():
                config_file.write("%s=%s\n" % (key, self.properties[key]))
        finally:
            config_file.close()

    def tmp_client(self):
        """
        Create a client for performing cleanup operations.
        This client should be closed as soon as possible
        by the process
        """
        try:
            client = omero.client(["--Ice.Config=%s" % str(self.config_path)])
            client.setAgent("OMERO.process")
            client.createSession().detachOnDestroy()
            self.logger.debug("client: %s" % client.sf)
            return client
        except:
            self.logger.error("Failed to create client for %s" % self.uuid)
            return None

    #
    # Activation / Deactivation
    #

    @locked
    def activate(self):
        """
        Process creation has to wait until all external downloads, etc
        are finished.
        """

        if self.isActive():
            raise omero.ApiUsageException(None, None, "Already activated")

        self.stdout = open(str(self.stdout_path), "w")
        self.stderr = open(str(self.stderr_path), "w")
        self.popen = self.Popen(
            self.command(),
            cwd=str(self.dir), env=self.env(),
            stdout=self.stdout, stderr=self.stderr)
        self.pid = self.popen.pid
        self.started = time.time()
        self.stopped = None
        self.status("Activated")

    def command(self):
        """
        Method to allow subclasses to override the launch
        behavior by changing the command passed to self.Popen
        """
        return [self.interpreter, "./script"]

    @locked
    def deactivate(self):
        """
        Cleans up the temporary directory used by the process, and terminates
        the Popen process if running.
        """

        if not self.isActive():
            raise omero.ApiUsageException(None, None, "Not active")

        if self.stopped:
            # Prevent recursion since we are reusing kill & cancel
            return

        self.stopped = time.time()
        d_start = time.time()
        self.status("Deactivating")

        # None of these should throw, but just in case
        try:

            self.shutdown()     # Calls cancel & kill which recall this method!
            self.popen = None   # Now we are finished

            client = self.tmp_client()
            try:
                self.set_job_status(client)
                self.cleanup_output()
                self.upload_output(client)  # Important!
                self.cleanup_tmpdir()
            finally:
                if client:
                    client.__del__()  # Safe closeSession

        except Exception:
            self.logger.error(
                "FAILED TO CLEANUP pid=%s (%s)",
                self.pid, self.uuid, exc_info=True)

        d_stop = time.time()
        elapsed = int(self.stopped - self.started)
        d_elapsed = int(d_stop - d_start)
        self.status("Lived %ss. Deactivation took %ss." % (elapsed, d_elapsed))

    @locked
    def isActive(self):
        """
        Tests only if this instance has a non-None popen attribute. After
        activation this method will return True until the popen itself returns
        a non-None value (self.rcode) at which time it will be nulled and this
        method will again return False
        """
        return self.popen is not None

    @locked
    def wasActivated(self):
        """
        Returns true only if this instance has either a non-null
        popen or a non-null rcode field.
        """
        return self.popen is not None or self.rcode is not None

    @locked
    def isRunning(self):
        return self.popen is not None and self.rcode is None

    @locked
    def isFinished(self):
        return self.rcode is not None

    @locked
    def alreadyDone(self):
        """
        Allows short-cutting various checks if we already
        have a rcode for this popen. A non-None return value
        implies that a process was started and returned
        the given non-None value itself.
        """
        if not self.wasActivated:
            raise omero.InternalException(
                None, None, "Process never activated")
        return self.isFinished()

    #
    # Cleanup methods
    #

    def __del__(self):
        self.cleanup()

    @perf
    @locked
    def check(self):
        """
        Called periodically to keep the session alive. Returns
        False if this resource can be cleaned up. (Resources API)
        """

        if not self.wasActivated():
            return True  # This should only happen on startup, so ignore

        try:
            self.poll()
            self.ctx.getSession().getSessionService().getSession(self.uuid)
            return True
        except:
            self.status("Keep alive failed")
            return False

    @perf
    @locked
    def cleanup(self):
        """
        Deactivates the process (if active) and cleanups the server
        connection. (Resources API)
        """

        if self.isRunning():
            self.deactivate()

        if not self.iskill:
            return

        try:
            sf = self.ctx.getSession(recreate=False)
        except:
            self.logger.debug("Can't get session for cleanup")
            return

        self.status("Killing session")
        svc = sf.getSessionService()
        obj = omero.model.SessionI()
        obj.uuid = omero.rtypes.rstring(self.uuid)
        try:
            while svc.closeSession(obj) > 0:
                pass
            # No action to be taken when iskill == False if
            # we don't have an actual client to worry with.
        except:
            self.logger.error(
                "Error on session cleanup, kill=%s" %
                self.iskill, exc_info=True)

    def cleanup_output(self):
        """
        Flush and close the stderr and stdout streams.
        """
        try:
            if hasattr(self, "stderr"):
                self.stderr.flush()
                self.stderr.close()
        except:
            self.logger.error("cleanup of sterr failed", exc_info=True)
        try:
            if hasattr(self, "stdout"):
                self.stdout.flush()
                self.stdout.close()
        except:
            self.logger.error("cleanup of sterr failed", exc_info=True)

    def set_job_status(self, client):
        """
        Sets the job status
        """
        if not client:
            self.logger.error(
                "No client: Cannot set job status for pid=%s (%s)",
                self.pid, self.uuid)
            return

        gid = client.sf.getAdminService().getEventContext().groupId
        handle = WithGroup(client.sf.createJobHandle(), gid)
        try:
            status = self.final_status
            if status is None:
                status = (self.rcode == 0 and "Finished" or "Error")
            handle.attach(int(self.properties["omero.job"]))
            oldStatus = handle.setStatus(status)
            self.status(
                "Changed job status from %s to %s" % (oldStatus, status))
        finally:
            handle.close()

    def upload_output(self, client):
        """
        If this is not a params calculation (i.e. parms != null) and the
        stdout or stderr are non-null, they they will be uploaded and
        attached to the job.
        """
        if not client:
            self.logger.error(
                "No client: Cannot upload output for pid=%s (%s)",
                self.pid, self.uuid)
            return

        if self.params:
            out_format = self.params.stdoutFormat
            err_format = self.params.stderrFormat
        else:
            out_format = "text/plain"
            err_format = out_format

        self._upload(client, self.stdout_path, "stdout", out_format)
        self._upload(client, self.stderr_path, "stderr", err_format)

    def _upload(self, client, filename, name, format):

        if not format:
            return

        filename = str(filename)  # Might be path.path
        sz = os.path.getsize(filename)
        if not sz:
            self.status("No %s" % name)
            return

        try:
            ofile = client.upload(filename, name=name, type=format)
            jobid = int(client.getProperty("omero.job"))
            link = omero.model.JobOriginalFileLinkI()
            if self.params is None:
                link.parent = omero.model.ParseJobI(rlong(jobid), False)
            else:
                link.parent = omero.model.ScriptJobI(rlong(jobid), False)
            link.child = ofile.proxy()
            client.getSession().getUpdateService().saveObject(link)
            self.status(
                "Uploaded %s bytes of %s to %s" %
                (sz, filename, ofile.id.val))
        except:
            self.logger.error(
                "Error on upload of %s for pid=%s (%s)",
                filename, self.pid, self.uuid, exc_info=True)

    def cleanup_tmpdir(self):
        """
        Remove all known files and finally the temporary directory.
        If other files exist, an exception will be raised.
        """
        try:
            remove_path(self.dir)
        except:
            self.logger.error(
                "Failed to remove dir %s" % self.dir, exc_info=True)

    #
    # popen methods
    #

    def status(self, msg=""):
        if self.isRunning():
            self.rcode = self.popen.poll()
        self.logger.info("%s : %s", self, msg)

    @perf
    @remoted
    def poll(self, current=None):
        """
        Checks popen.poll() (if active) and notifies all callbacks
        if necessary. If this method returns a non-None value, then
        the process will be marked inactive.
        """

        if self.alreadyDone():
            return rint(self.rcode)

        self.status("Polling")
        if self.rcode is None:
            # Haven't finished yet, so do nothing.
            return None
        else:
            self.deactivate()
            rv = rint(self.rcode)
            self.allcallbacks("processFinished", self.rcode)
            return rv

    @perf
    @remoted
    def wait(self, current=None):
        """
        Waits on popen.wait() to return (if active) and notifies
        all callbacks. Marks this process as inactive.
        """

        if self.alreadyDone():
            return self.rcode

        self.status("Waiting")
        self.rcode = self.popen.wait()
        self.deactivate()
        self.allcallbacks("processFinished", self.rcode)
        return self.rcode

    def _term(self):
        """
        Attempts to cancel the process by sending SIGTERM
        (or similar)
        """
        try:
            self.status("os.kill(TERM)")
            os.kill(self.popen.pid, signal.SIGTERM)
        except AttributeError:
            self.logger.debug("No os.kill(TERM). Skipping cancel")

    def _send(self, iskill):
        """
        Helper method for sending signals. This method only
        makes a call is the process is active.
        """
        if self.isRunning():
            try:
                if self.popen.poll() is None:
                    if iskill:
                        self.status("popen.kill(True)")
                        self.popen.kill(True)
                    else:
                        self._term()

                else:
                    self.status("Skipped signal")
            except OSError as oserr:
                self.logger.debug(
                    "err on pid=%s iskill=%s : %s", self.popen.pid, iskill,
                    oserr)

    @perf
    @remoted
    def cancel(self, current=None):
        """
        Tries to cancel popen (if active) and notifies callbacks.
        """

        if self.alreadyDone():
            return True

        self.final_status = "Cancelled"
        self._send(iskill=False)
        finished = self.isFinished()
        if finished:
            self.deactivate()
        self.allcallbacks("processCancelled", finished)
        return finished

    @perf
    @remoted
    def kill(self, current=None):

        if self.alreadyDone():
            return True

        self.final_status = "Cancelled"
        self._send(iskill=True)
        finished = self.isFinished()
        if finished:
            self.deactivate()
        self.allcallbacks("processKilled", finished)
        return finished

    @perf
    @remoted
    def shutdown(self, current=None):
        """
        If self.popen is active, then first call cancel, wait a period of
        time, and finally call kill.
        """

        if self.alreadyDone():
            return

        self.status("Shutdown")
        try:
            for i in range(5, 0, -1):
                if self.cancel():
                    break
                else:
                    self.logger.warning(
                        "Shutdown: %s (%s). Killing in %s seconds.", self.pid,
                        self.uuid, 6*(i-1)+1)
                    self.stop_event.wait(6)
            self.kill()
        except:
            self.logger.error(
                "Shutdown failed: %s (%s)", self.pid, self.uuid,
                exc_info=True)

    #
    # Callbacks
    #

    @remoted
    @locked
    def registerCallback(self, callback, current=None):
        try:
            id = callback.ice_getIdentity()
            key = "%s/%s" % (id.category, id.name)
            callback = callback.ice_oneway()
            callback = self.callback_cast(callback)
            if not callback:
                e = "Callback is invalid"
            else:
                self.callbacks[key] = callback
                self.logger.debug("Added callback: %s", key)
                return
        except Exception as ex:
            e = ex
        # Only reached on failure
        msg = "Failed to add callback: %s. Reason: %s" % (callback, e)
        self.logger.debug(msg)
        raise omero.ApiUsageException(None, None, msg)

    @remoted
    @locked
    def unregisterCallback(self, callback, current=None):
        try:
            id = callback.ice_getIdentity()
            key = "%s/%s" % (id.category, id.name)
            if key not in self.callback:
                raise omero.ApiUsageException(
                    None, None, "No callback registered with id: %s" % key)
            del self.callbacks[key]
            self.logger.debug("Removed callback: %s", key)
        except Exception as e:
            msg = "Failed to remove callback: %s. Reason: %s" % (callback, e)
            self.logger.debug(msg)
            raise omero.ApiUsageException(None, None, msg)

    @locked
    def allcallbacks(self, method, arg):
        self.status("Callback %s" % method)
        for key, cb in list(self.callbacks.items()):
            try:
                m = getattr(cb, method)
                m(arg)
            except Ice.LocalException:
                self.logger.debug(
                    "LocalException calling callback %s on pid=%s (%s)"
                    % (key, self.pid, self.uuid), exc_info=False)
            except:
                self.logger.error(
                    "Error calling callback %s on pid=%s (%s)"
                    % (key, self.pid, self.uuid), exc_info=True)

    def __str__(self):
        return "<proc:%s,rc=%s,uuid=%s>" % (
            self.pid, (self.rcode is None and "-" or self.rcode), self.uuid)


class MATLABProcessI(ProcessI):

    def make_files(self):
        """
        Modify the script_path field from ProcessI.make_files
        in ordert to append a ".m"
        """
        ProcessI.make_files(self)
        self.script_path = self.dir / "script.m"

    def command(self):
        """
        Overrides ProcessI to call MATLAB idiosyncratically.
        """
        r = "try, cd('%s'); script; " % self.dir
        r += "catch e, disp(e.identifier); disp(e.message); exit(1); "
        r += "end, exit(0)"
        matlab_cmd = [
            self.interpreter, "-nosplash", "-nodisplay", "-nodesktop", "-r", r,
        ]
        return matlab_cmd


class UseSessionHolder(object):

    def __init__(self, sf):
        self.sf = sf

    def check(self):
        try:
            self.sf.keepAlive(None)
            return True
        except:
            return False

    def cleanup(self):
        pass


# ---------------------------------------------------------------------------
# BIOMERO: detached workflow execution
# ---------------------------------------------------------------------------
# A BIOMERO workflow run outlives the OMERO session that asks for it: data
# transfer, conversion, Slurm execution and result import together take longer
# than a browser tab or an OMERO session timeout can be relied on to last.
#
# So the workflow scripts do not run the pipeline inline. They validate the
# request, record everything the run needs in a launcher task and return (see
# biomero.detached). The supervisor thread below runs alongside this processor,
# finds those queued runs and executes each one in a worker thread, driving the
# very same pipeline function the script would have called itself.
#
# The supervisor only starts when BIOMERO_DETACHED_WORKFLOWS is enabled for
# this processor, so a stock deployment is unaffected.
from threading import Thread, Lock, Event, current_thread

# How many workflows to drive at once. Batched parents do not count: they only
# wait for their children, and counting them could starve those children.
MAX_ACTIVE_WORKFLOWS = int(os.environ.get(
    getattr(_slurm_env, "BIOMERO_MAX_ACTIVE_WORKFLOWS",
            "BIOMERO_MAX_ACTIVE_WORKFLOWS"), "4"))
# How often to look for newly queued workflows.
SUPERVISOR_POLL_SECONDS = int(
    os.environ.get(
        getattr(_slurm_env, "BIOMERO_SUPERVISOR_POLL_SECONDS",
                "BIOMERO_SUPERVISOR_POLL_SECONDS"), "10"))
# The longest wait between attempts to reach the tracking database at start.
SUPERVISOR_SETUP_RETRY_MAX_SECONDS = 60
# The shortest wait, so that a poll interval of 0 does not make it spin.
SUPERVISOR_SETUP_RETRY_MIN_SECONDS = 1
# How long to hold off the first poll. A run needs sub-scripts, which cannot
# start until this processor is registered and the server is routing work to
# it, so resuming a run the moment the process comes up would fail it.
SUPERVISOR_STARTUP_GRACE_SECONDS = int(
    os.environ.get(
        getattr(_slurm_env, "BIOMERO_SUPERVISOR_STARTUP_GRACE_SECONDS",
                "BIOMERO_SUPERVISOR_STARTUP_GRACE_SECONDS"), "60"))
# A sub-script launch is retried while the server reports no processor, which
# it does until registration has gone through after a restart.
SCRIPT_START_RETRY_SECONDS = 180
# A child script can make a large OMERO call on another server thread while
# this supervisor polls its process proxy. Ice may briefly surface that call's
# transport failure from poll() as well. Retry a few consecutive local
# transport errors so the child can handle its own exception and finish, but
# do not wait forever if the process proxy is genuinely unavailable.
SCRIPT_POLL_SECONDS = 2
SCRIPT_POLL_FAILURE_LIMIT = 5
# How often a batched parent checks on its children.
CHILD_POLL_SECONDS = 15
# A claim on a launcher task is valid for a lease (core's constant); the
# supervisor renews the claims of its running workflows three times per lease,
# so a lease only runs out when this supervisor is gone.
CLAIM_RENEW_SECONDS = LAUNCHER_CLAIM_LEASE_SECONDS // 3
# After a worker ended without its workflow reaching a final state, the
# supervisor waits this long before it runs that workflow again.
WORKER_RESTART_DELAY_SECONDS = 60
# How long a node shutdown waits for the supervisor to hand its claims back.
SUPERVISOR_STOP_TIMEOUT_SECONDS = 30
# How often a sub-script run looks for a cancel request of its workflow.
CANCEL_CHECK_SECONDS = 10
# How long a cancelled sub-script's process gets to end before it is killed.
SCRIPT_CANCEL_WAIT_SECONDS = 30
# The application whose recording carries the workflow progress events.
WORKFLOW_TRACKER_APPLICATION = "WorkflowTracker"
# For each batch index of a batched parent: the ID of its bookkeeping task and
# the ID of its child workflow.
ChildrenByBatch = Dict[int, Tuple[uuid.UUID, uuid.UUID]]
# Workflows found not to be ours are remembered so we do not keep inspecting
# them, but the memory is dropped periodically so that a transient database
# error cannot sideline a workflow until the next restart.
IGNORE_CACHE_POLLS = 90
# A script starts its workflow before it registers the launcher task, so a
# workflow this young without one is not evidence that it is not ours: it is
# re-examined on the next poll instead of being remembered.
IGNORE_MIN_AGE_SECONDS = 300

biomero_logger = logging.getLogger("biomero.detached")


def load_biomero_scripts():
    """Import the BIOMERO workflow scripts installed in this OMERO server.

    The scripts live in OMERO's script directory rather than on sys.path, so
    the biomero package's search path is extended to reach them.

    Returns:
        tuple: The SLURM_Run_Workflow and SLURM_Run_Workflow_Batched modules.
    """
    omero_home = os.environ.get("OMERODIR", "/opt/omero/server/OMERO.server")
    scripts_path = os.path.join(omero_home, "lib", "scripts")
    if scripts_path not in sys.path:
        sys.path.append(scripts_path)
    import biomero
    scripts_biomero_path = os.path.join(scripts_path, "biomero")
    if scripts_biomero_path not in biomero.__path__:
        biomero.__path__.append(scripts_biomero_path)
    import biomero.__workflows.SLURM_Run_Workflow as run_workflow_script
    import biomero.__workflows.SLURM_Run_Workflow_Batched as batched_script
    return run_workflow_script, batched_script


def load_metadata_script() -> Any:
    """Load the fixed administrative adapter, never a request-supplied module.

    Returns:
        Any: The ``SLURM_Init_environment`` module, logging to the BIOMERO log
            file.
    """
    load_biomero_scripts()
    import biomero.admin.SLURM_Init_environment as metadata_script
    if not hasattr(metadata_script, "_detached_log_handler"):
        from logging.handlers import RotatingFileHandler
        omero_home = os.environ.get("OMERODIR",
                                    "/opt/omero/server/OMERO.server")
        log_file = os.path.join(omero_home, "var", "log", "biomero.log")
        handler = RotatingFileHandler(log_file, maxBytes=500000000,
                                      backupCount=9)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] [%(process)d] "
            "(%(threadName)s) %(message)s"))
        metadata_script.logger.addHandler(handler)
        metadata_script.logger.setLevel(logging.INFO)
        maintenance_logger = logging.getLogger("biomero.detached.maintenance")
        maintenance_logger.addHandler(handler)
        maintenance_logger.setLevel(logging.INFO)
        metadata_script._detached_log_handler = handler
    return metadata_script


def wrap_value(value: Any) -> Any:
    """Wrap a recorded input value back into the OMERO rtype a script expects.

    Args:
        value (Any): The recorded Python value.

    Returns:
        Any: The matching OMERO rtype; None for None, and the value itself
            when OMERO cannot wrap it.
    """
    from omero.rtypes import rbool, rlong, rstring, rlist, rmap, wrap
    if value is None:
        return None
    if isinstance(value, bool):
        return rbool(value)
    if isinstance(value, int):
        return rlong(value)
    if isinstance(value, str):
        return rstring(value)
    if isinstance(value, (list, tuple)):
        return rlist([wrap_value(item) for item in value])
    if isinstance(value, dict):
        return rmap({key: wrap_value(item) for key, item in value.items()})
    try:
        return wrap(value)
    except Exception:
        return value


class RecordedInputsClient(object):
    """Stands in for an OMERO script client, serving a launcher task's inputs.

    The pipeline reads its inputs through client.getInput() and reports
    progress through client.setOutput(). A detached run has no script session,
    so the values recorded at launch time are served here instead, and outputs
    are collected for logging rather than returned to a caller.

    Sub-script launches need a live connection to keep alive while they run;
    that is carried here so the runner can reach it, together with the check
    that stops the sub-script when its workflow was cancelled.
    """

    def __init__(self, params: Optional[Dict[str, Any]],
                 conn: Optional["BlitzGateway"] = None,
                 raise_if_stopped: Optional[Callable[[], None]] = None
                 ) -> None:
        """Serve the inputs recorded for a detached run.

        Args:
            params (Optional[Dict[str, Any]]): The inputs recorded at launch
                time; None serves no inputs.
            conn (Optional[BlitzGateway]): The user's live OMERO connection,
                which sub-script launches keep alive while they run.
            raise_if_stopped (Optional[Callable[[], None]]): Check that raises
                when the workflow was cancelled or this supervisor lost its
                claim, so that a running sub-script is stopped.
        """
        self.params = params or {}
        self.conn = conn
        self.raise_if_stopped = raise_if_stopped
        self.outputs = {}

    def getInput(self, key: str) -> Any:
        """Serve one recorded input, as the script client does.

        Args:
            key (str): The input's name.

        Returns:
            Any: The input wrapped as an OMERO rtype; None when not recorded.
        """
        return wrap_value(self.params.get(key))

    def getInputs(self, unwrap: bool = False) -> Dict[str, Any]:
        """Serve all recorded inputs, as the script client does.

        Args:
            unwrap (bool): Whether to return the plain Python values instead
                of OMERO rtypes.

        Returns:
            Dict[str, Any]: The recorded inputs by name.
        """
        if unwrap:
            return dict(self.params)
        return {key: wrap_value(value) for key, value in self.params.items()}

    def setOutput(self, key: str, value: Any) -> None:
        """Collect an output, which a detached run only logs.

        Args:
            key (str): The output's name.
            value (Any): The output value.
        """
        self.outputs[key] = value

    def closeSession(self) -> None:
        """Do nothing: the worker owns the connection and closes it."""


class ClaimLost(WorkflowInterrupted):
    """This supervisor no longer holds the claim on the workflow it runs.

    Another supervisor owns the run now, so this worker stops without touching
    the workflow's state.
    """


def polling_script_runner(client: RecordedInputsClient, svc: Any,
                          script_id: int, inputs: Dict[str, Any],
                          slurmClient: Optional["SlurmClient"] = None
                          ) -> Tuple[Dict[str, Any], Any]:
    """Run an OMERO sub-script and wait for it, without a script session.

    omero.scripts.ProcessCallbackI needs a script session to receive the
    process callback on, which a detached run does not have. Poll the process
    instead, keeping the user's connection alive and pumping the workflow
    progress listener so that the UI keeps moving while the sub-script runs.
    While it runs, the workflow's stop check is made at a fixed interval, and
    the sub-script is cancelled when the check says to stop.

    Args:
        client (RecordedInputsClient): The stand-in client for this run
            (carries the connection and the stop check).
        svc (Any): OMERO script service.
        script_id (int): ID of the sub-script to run.
        inputs (Dict[str, Any]): Sub-script inputs.
        slurmClient (Optional[SlurmClient]): Active SLURM client, for its
            progress listener.

    Returns:
        Tuple[Dict[str, Any], Any]: (results, job) exactly as
            runOMEROScript() returns them.

    Raises:
        Ice.LocalException: When polling the process failed
            SCRIPT_POLL_FAILURE_LIMIT times in a row.
        WorkflowInterrupted: When the stop check asked to stop; the
            sub-script's process is cancelled first.
    """
    logger = logging.getLogger("biomero.detached.script")
    proc = start_script(svc, script_id, inputs, logger)
    conn = getattr(client, "conn", None)
    raise_if_stopped = getattr(client, "raise_if_stopped", None)
    next_cancel_check = time.monotonic()
    try:
        next_position = latest_progress_position(slurmClient, default=0)
        poll_failures = 0
        while True:
            try:
                return_code = proc.poll()
                poll_failures = 0
            except Ice.LocalException as e:
                poll_failures += 1
                if poll_failures >= SCRIPT_POLL_FAILURE_LIMIT:
                    raise
                logger.warning(
                    f"OMERO process poll failed "
                    f"({poll_failures}/{SCRIPT_POLL_FAILURE_LIMIT}); the "
                    f"child may be handling its own transport error, "
                    f"retrying: {e}")
                time.sleep(SCRIPT_POLL_SECONDS)
                continue

            if return_code is not None:
                break
            if raise_if_stopped and time.monotonic() >= next_cancel_check:
                next_cancel_check = time.monotonic() + CANCEL_CHECK_SECONDS
                cancel_process_if_stopped(proc, script_id, raise_if_stopped,
                                          logger)
            if conn is not None:
                try:
                    conn.keepAlive()
                except Exception as e:
                    logger.debug(f"Could not keep the connection alive: {e}")
            next_position = pump_progress_listener(slurmClient, next_position,
                                                   logger)
            time.sleep(SCRIPT_POLL_SECONDS)
        return proc.getResults(0), proc.getJob()
    finally:
        proc.close(False)


def latest_progress_position(slurmClient: Optional["SlurmClient"],
                             default: int) -> int:
    """Find the newest position in the workflow progress recording.

    Args:
        slurmClient (Optional[SlurmClient]): Active SLURM client; without a
            progress listener there is nothing to follow.
        default (int): The position to return when it cannot be read.

    Returns:
        int: The newest tracking ID, or ``default``.
    """
    if slurmClient is None or slurmClient.wfProgress is None:
        return default
    try:
        return slurmClient.wfProgress.recorder.max_tracking_id(
            application_name=WORKFLOW_TRACKER_APPLICATION) or 0
    except Exception:
        return default


def pump_progress_listener(slurmClient: Optional["SlurmClient"],
                           next_position: int, logger: logging.Logger) -> int:
    """Let the workflow progress listener catch up with what was recorded.

    Args:
        slurmClient (Optional[SlurmClient]): Active SLURM client; without a
            progress listener nothing is pumped.
        next_position (int): The position the listener continues from.
        logger (logging.Logger): Where a skipped poll is logged.

    Returns:
        int: The position to continue from at the next pump.
    """
    if slurmClient is None or slurmClient.wfProgress is None:
        return next_position
    try:
        slurmClient.bring_listener_uptodate(
            slurmClient.wfProgress, start=next_position)
    except Exception as e:
        logger.debug(f"Progress poll skipped: {e}")
    return latest_progress_position(slurmClient, default=next_position)


def cancel_process_if_stopped(proc: Any, script_id: int,
                              raise_if_stopped: Callable[[], None],
                              logger: logging.Logger) -> None:
    """Cancel a sub-script's process when its workflow must stop.

    A failing check is only logged: a tracker hiccup must not kill a running
    sub-script, and the next check tries again.

    Args:
        proc (Any): The OMERO process of the sub-script.
        script_id (int): ID of the sub-script, for the logs.
        raise_if_stopped (Callable[[], None]): The workflow's stop check.
        logger (logging.Logger): Where the decision is logged.

    Raises:
        WorkflowInterrupted: When the check asked to stop (the process has
            ended, or been killed, before this is raised).
    """
    try:
        raise_if_stopped()
    except WorkflowInterrupted as stopped:
        logger.info(f"Stopping the OMERO process of script "
                    f"{script_id}: {stopped}")
        proc.cancel()
        wait_for_cancelled_process(proc, script_id, logger)
        raise
    except Exception as e:
        logger.warning(f"Could not check for a cancel request "
                       f"of script {script_id}: {e}")


def wait_for_cancelled_process(proc: Any, script_id: int,
                               logger: logging.Logger) -> None:
    """Wait for a cancelled process to end, killing it when it does not.

    OMERO only marks the sub-script's job as cancelled when a poll sees the
    process end, and cancel() does not poll. Nobody polls after the runner
    closes the process, so the job would stay running without a process.
    A failing poll is only logged: the interrupt that follows matters more.

    Args:
        proc (Any): The OMERO process, already cancelled.
        script_id (int): ID of the sub-script, for the logs.
        logger (logging.Logger): Where the decisions are logged.
    """
    try:
        deadline = time.monotonic() + SCRIPT_CANCEL_WAIT_SECONDS
        process_ended = proc.poll() is not None
        while not process_ended and time.monotonic() < deadline:
            time.sleep(SCRIPT_POLL_SECONDS)
            process_ended = proc.poll() is not None
        if not process_ended:
            logger.info(f"The OMERO process of script {script_id} did not "
                        f"end within {SCRIPT_CANCEL_WAIT_SECONDS}s of the "
                        f"cancel; killing it")
            proc.kill()
            process_ended = proc.poll() is not None
        if not process_ended:
            logger.warning(f"The OMERO process of script {script_id} has "
                           f"not ended after being killed")
    except Ice.LocalException as e:
        logger.warning(f"Could not confirm that the OMERO process of "
                       f"script {script_id} ended: {e}")


def start_script(svc: Any, script_id: int, inputs: Dict[str, Any],
                 logger: logging.Logger) -> Any:
    """Start a sub-script, waiting out a processor that is not ready yet.

    Right after this processor restarts it is not yet being given work, so a
    resumed run would otherwise fail on its first sub-script.

    Args:
        svc (Any): The OMERO scripts service.
        script_id (int): The script to run.
        inputs (Dict[str, Any]): The script's inputs, as OMERO rtypes.
        logger (logging.Logger): Logger for the waits.

    Returns:
        Any: The started script's process proxy.

    Raises:
        omero.NoProcessorAvailable: When no processor became available within
            ``SCRIPT_START_RETRY_SECONDS``.
    """
    deadline = time.time() + SCRIPT_START_RETRY_SECONDS
    while True:
        try:
            return svc.runScript(int(script_id), inputs, None)
        except omero.NoProcessorAvailable:
            if time.time() >= deadline:
                raise
            logger.info(f"No processor available yet for script {script_id}; "
                        f"retrying.")
            time.sleep(10)


class WorkflowWorker(Thread):
    """Runs one queued workflow to completion, in the background."""

    # Parameters of the bookkeeping task that a batched parent keeps per batch.
    BATCH_INDEX_KEY = "batch_index"
    CHILD_WORKFLOW_ID_KEY = "child_workflow_id"

    def __init__(self, workflow_id: uuid.UUID, launcher_task_id: uuid.UUID,
                 batched: bool, supervisor: "WorkflowSupervisor") -> None:
        """Prepare a worker for a workflow whose launcher task is claimed.

        Args:
            workflow_id (uuid.UUID): The workflow to run.
            launcher_task_id (uuid.UUID): The launcher task holding the
                claim and the recorded inputs.
            batched (bool): Whether the workflow is a batched parent, which
                only waits for its child workflows.
            supervisor (WorkflowSupervisor): The supervisor that owns this
                worker and its claim.
        """
        super(WorkflowWorker, self).__init__(
            name=f"WorkflowWorker-{workflow_id}")
        self.daemon = True
        self.workflow_id = workflow_id
        self.launcher_task_id = launcher_task_id
        self.batched = batched
        self.supervisor = supervisor
        # A batched parent only waits for its children, so it must not take up
        # an execution slot: that could starve the children it is waiting for.
        self.holds_slot = not batched
        # Set when this supervisor lost the claim on the workflow: the worker
        # then stops at its next check instead of running a second copy.
        self.claim_lost = Event()
        # Set with ``claim_lost`` when another supervisor took the claim, as
        # opposed to this supervisor releasing it.
        self.taken_over = False
        self.logger = logging.getLogger(f"biomero.detached.{workflow_id}")

    def raise_if_claim_lost(self) -> None:
        """Stop this worker once its workflow's claim belongs to someone else.

        Raises:
            ClaimLost: When this supervisor no longer holds the claim.
        """
        if self.claim_lost.is_set():
            raise ClaimLost(f"The claim on workflow {self.workflow_id} was "
                            f"lost to another supervisor")

    def run(self) -> None:
        """Run the workflow and record how it ended, then free the slot."""
        from biomero.eventsourcing import WorkflowCancelled
        self.logger.info(f"Executing queued workflow {self.workflow_id}")
        try:
            self.execute()
            self.logger.info(f"Finished workflow {self.workflow_id}")
        except WorkflowCancelled as cancelled:
            # Stopped while a sub-script ran. The Slurm jobs, if any, are
            # cancelled by the pipeline, which is the one that submitted them.
            self.logger.info(f"Workflow {self.workflow_id} cancelled: "
                             f"{cancelled}")
            self.fail_workflow(str(cancelled))
        except Exception as e:
            self.handle_failure(e)
        finally:
            self.supervisor.remove_worker(self.workflow_id,
                                          self.launcher_task_id)

    def handle_failure(self, error: Exception) -> None:
        """Fail the workflow, unless another supervisor owns it now.

        Args:
            error (Exception): What stopped the run.
        """
        if self.claim_lost.is_set():
            # The claim is gone (taken over, or released at shutdown):
            # whoever owns this workflow now writes its outcome, and
            # failing it here would fail their run.
            if (self.supervisor.shutdown_event.is_set()
                    and not self.taken_over):
                self.logger.info(f"Worker of workflow {self.workflow_id} "
                                 f"stopped for the shutdown; its claim was "
                                 f"handed back.")
            else:
                # The takeover itself was logged at ERROR by the renewal.
                self.logger.warning(f"Worker of workflow {self.workflow_id} "
                                    f"stopped after losing its claim: "
                                    f"{error}")
            return
        self.logger.error(f"Workflow {self.workflow_id} failed: {error}",
                          exc_info=True)
        self.fail_workflow(str(error))

    def fail_workflow(self, error: str) -> None:
        """Record the failure, so the workflow does not sit unfinished.

        Args:
            error (str): What to record as the reason it failed.
        """
        try:
            from biomero.database import EngineManager
            from biomero.slurm_client import SlurmClient
            EngineManager.create_scoped_session()
            with SlurmClient.from_config() as slurm_client:
                slurm_client.workflowTracker.fail_workflow(
                    self.workflow_id, error)
        except Exception as e:
            self.logger.error(f"Could not record the failure of workflow "
                              f"{self.workflow_id}: {e}")

    def execute(self) -> None:
        """Run what this workflow's launcher task asks for.

        Raises:
            ValueError: When the task is not a launcher for this workflow.
        """
        from biomero.eventsourcing import is_launcher_task
        from biomero.database import EngineManager
        from biomero.slurm_client import SlurmClient

        run_workflow_script, batched_script = load_biomero_scripts()
        EngineManager.create_scoped_session()

        with SlurmClient.from_config() as slurm_client:
            tracker = slurm_client.workflowTracker
            launcher = tracker.repository.get(self.launcher_task_id)
            if not is_launcher_task(launcher):
                raise ValueError(f"Task {self.launcher_task_id} is not a "
                                 f"launcher for workflow {self.workflow_id}")

            workflow = tracker.repository.get(self.workflow_id)
            params = launcher.params or {}
            with self.user_connection(workflow) as conn:
                client = RecordedInputsClient(
                    params, conn,
                    raise_if_stopped=lambda: self.raise_if_stopped(tracker))
                if self.batched:
                    self.run_batches(run_workflow_script, batched_script,
                                     slurm_client, conn, workflow, params)
                else:
                    self.run_single(run_workflow_script, slurm_client, client,
                                    conn, params)

    def raise_if_stopped(self, tracker: "WorkflowTracker") -> None:
        """Stop between steps: when the claim is lost, or a cancel was asked.

        The scripts' ``PipelineRun.raise_if_stopped`` does the same for the
        pipeline (its ``stop_check`` is this worker's claim check, then it
        checks the cancel itself). This one serves the sub-script runner and
        the batched parent, which have no pipeline around them.

        Args:
            tracker (WorkflowTracker): Tracker to ask whether the workflow's
                cancel was requested.

        Raises:
            ClaimLost: When another supervisor owns this workflow now.
            WorkflowCancelled: When a cancel was requested for it.
        """
        self.raise_if_claim_lost()
        tracker.raise_if_cancel_requested(self.workflow_id)

    @contextlib.contextmanager
    def user_connection(self, workflow: Any) -> Iterator["BlitzGateway"]:
        """Connect to OMERO as the user whose workflow this is.

        The run has no session of its own, so the processor's own credentials
        are used to sudo into the requesting user's account and group. Results
        are then created and owned exactly as an inline run would create them.

        Args:
            workflow (Any): The workflow aggregate, which names the user and
                group.

        Yields:
            BlitzGateway: A connection as that user, in that group.

        Raises:
            ConnectionError: When OMERO cannot be reached.
            ValueError: When the workflow's user does not exist.
        """
        from omero.gateway import BlitzGateway

        username = os.environ.get("OMERO_USER", "root")
        password = os.environ.get("OMERO_PASSWORD", "omero")
        host = os.environ.get("OMERO_HOST", "omeroserver")
        port = int(os.environ.get("OMERO_PORT", "4064"))

        admin_conn = BlitzGateway(username, password, host=host, port=port,
                                  secure=True)
        if not admin_conn.connect():
            raise ConnectionError(
                f"Could not connect to OMERO at {host}:{port} as {username} "
                f"to run workflow {self.workflow_id}")
        try:
            admin_conn.c.enableKeepAlive(60)
            user = admin_conn.getObject("Experimenter", workflow.user)
            if not user:
                raise ValueError(f"No OMERO user with ID {workflow.user} for "
                                 f"workflow {self.workflow_id}")
            self.logger.info(f"Running as {user.getName()} in group "
                             f"{workflow.group}")
            # A day of leeway per session refresh; the runner keeps it alive
            # for as long as the run takes.
            with admin_conn.suConn(user.getName(), ttl=86400000) as user_conn:
                user_conn.c.enableKeepAlive(60)
                user_conn.keepAlive()
                user_conn.setGroupForSession(workflow.group)
                yield user_conn
        finally:
            admin_conn.close()

    def run_single(self, script: Any, slurm_client: "SlurmClient",
                   client: RecordedInputsClient, conn: "BlitzGateway",
                   params: Dict[str, Any]) -> None:
        """Drive the workflow pipeline, the same one an inline run drives.

        Args:
            script (Any): The SLURM_Run_Workflow module.
            slurm_client (SlurmClient): Active SLURM client.
            client (RecordedInputsClient): Serves the recorded inputs.
            conn (BlitzGateway): The user's OMERO connection.
            params (Dict[str, Any]): The inputs recorded in the launcher task.
        """
        pipeline_kwargs = script.resolve_pipeline_inputs(
            client, conn, slurm_client, params)
        self.logger.info(f"Running workflows {pipeline_kwargs['workflows']} "
                         f"for workflow {self.workflow_id}")
        messages = script.execute_workflow_pipeline(
            client, conn, slurm_client, self.workflow_id, resume=True,
            stop_check=self.raise_if_claim_lost, **pipeline_kwargs)
        self.logger.info(f"Workflow {self.workflow_id}: {messages}")

    def run_batches(self, script: Any, batched_script: Any,
                    slurm_client: "SlurmClient", conn: "BlitzGateway",
                    workflow: Any, params: Dict[str, Any]) -> None:
        """Run a batched request as one child workflow per batch.

        Each child is queued exactly as a single run is, so it is executed by
        the same pipeline and reports its own progress. This parent only
        spawns the children it does not have yet and then follows them.

        Args:
            script (Any): The SLURM_Run_Workflow module.
            batched_script (Any): The SLURM_Run_Workflow_Batched module.
            slurm_client (SlurmClient): Active SLURM client.
            conn (BlitzGateway): The user's OMERO connection.
            workflow (Any): The parent workflow aggregate.
            params (Dict[str, Any]): The inputs recorded in the launcher task.

        Raises:
            ValueError: When no batches were recorded.
            ClaimLost: When another supervisor owns the parent now.
        """
        tracker = slurm_client.workflowTracker
        launcher_params = constants.launcher_params
        batches = [list(batch)
                   for batch in (params.get(launcher_params.BATCHES) or [])]
        if not batches:
            raise ValueError(f"Batched workflow {self.workflow_id} has no "
                             f"batches recorded")
        base_inputs = params.get(launcher_params.BASE_INPUTS) or {}
        effective_type = params.get(launcher_params.EFFECTIVE_TYPE)
        self.logger.info(f"Batched workflow {self.workflow_id}: "
                         f"{len(batches)} batches")

        children = self.find_existing_children(tracker, workflow)
        self.queue_missing_children(script, slurm_client, conn, workflow,
                                    params, batches, children)

        failed, pending = self.await_children(
            slurm_client, conn, batched_script, children, batches,
            base_inputs, effective_type)
        if pending:
            # Shutting down: leave the workflow unfinished so that the next
            # processor adopts the children it already has.
            self.logger.info(f"Stopped following {len(pending)} batches of "
                             f"workflow {self.workflow_id}; they will be "
                             f"picked up again.")
            return
        # Not the owner any more: the new owner writes the outcome.
        self.raise_if_claim_lost()
        self.record_parent_outcome(tracker, len(batches), len(children),
                                   failed)

    def find_existing_children(self, tracker: "WorkflowTracker",
                               workflow: Any) -> "ChildrenByBatch":
        """Find the child workflows this parent has already queued.

        There is one bookkeeping task per batch on the parent workflow,
        holding the child's ID. Re-running this parent therefore adopts the
        children it already has instead of starting the work again.

        Args:
            tracker (WorkflowTracker): Tracker to read the tasks with.
            workflow (Any): The parent workflow aggregate.

        Returns:
            ChildrenByBatch: For each batch index, the bookkeeping task ID
                and the child workflow ID.
        """
        children = {}
        for task_id in getattr(workflow, "tasks", []):
            try:
                task = tracker.repository.get(task_id)
            except Exception as e:
                self.logger.warning(f"Could not read task {task_id}: {e}")
                continue
            task_params = task.params or {}
            if (self.BATCH_INDEX_KEY in task_params
                    and self.CHILD_WORKFLOW_ID_KEY in task_params):
                children[task_params[self.BATCH_INDEX_KEY]] = (
                    task_id,
                    uuid.UUID(str(task_params[self.CHILD_WORKFLOW_ID_KEY])))
        return children

    def queue_missing_children(self, script: Any, slurm_client: "SlurmClient",
                               conn: "BlitzGateway", workflow: Any,
                               params: Dict[str, Any],
                               batches: List[List[Any]],
                               children: "ChildrenByBatch") -> None:
        """Queue a child workflow for each batch that has none yet.

        No new child is queued for a workflow whose claim is lost (stop at
        once) or that was cancelled: then queuing stops, the children already
        queued are told to cancel, and the parent waits for them afterwards.

        Args:
            script (Any): The SLURM_Run_Workflow module.
            slurm_client (SlurmClient): Active SLURM client.
            conn (BlitzGateway): The user's OMERO connection.
            workflow (Any): The parent workflow aggregate.
            params (Dict[str, Any]): The inputs recorded in the launcher task.
            batches (List[List[Any]]): The IDs of each batch.
            children (ChildrenByBatch): The children queued so far; extended
                in place.

        Raises:
            ClaimLost: When another supervisor owns the parent now.
        """
        from biomero import constants
        from biomero.eventsourcing import WorkflowCancelled

        tracker = slurm_client.workflowTracker
        for index, batch in enumerate(batches):
            if index in children:
                continue
            # The claim is checked before each of the writes below (the child
            # workflow, its launcher task, this parent's bookkeeping task), so
            # a supervisor that lost the claim leaves nothing half-queued for
            # the new owner to find.
            self.raise_if_claim_lost()
            try:
                tracker.raise_if_cancel_requested(self.workflow_id)
            except WorkflowCancelled:
                self.logger.info(f"Workflow {self.workflow_id} was cancelled "
                                 f"while queuing batches; {len(children)} "
                                 f"queued.")
                self.cancel_children(tracker, children.values())
                break
            child_params = self.child_inputs(params, batch)
            self.raise_if_claim_lost()
            child_wf_id = tracker.initiate_workflow(
                f"{workflow.name} (batch {index + 1}/{len(batches)})",
                "\n".join([workflow.description, script.VERSION]),
                workflow.user,
                workflow.group)
            self.raise_if_claim_lost()
            script.register_detached_launcher(
                RecordedInputsClient(child_params, conn), slurm_client,
                child_wf_id, constants.RUN_WF_SCRIPT,
                params.get(constants.launcher_params.WORKFLOWS) or [], {})
            self.raise_if_claim_lost()
            task_id = tracker.add_task_to_workflow(
                self.workflow_id, constants.RUN_WF_SCRIPT, script.VERSION,
                batch, {self.BATCH_INDEX_KEY: index,
                        self.CHILD_WORKFLOW_ID_KEY: str(child_wf_id)})
            tracker.start_task(task_id)
            children[index] = (task_id, child_wf_id)
            self.logger.info(f"Queued batch {index + 1}/{len(batches)} as "
                             f"workflow {child_wf_id}")

    @staticmethod
    def child_inputs(params: Dict[str, Any], batch: List[Any]
                     ) -> Dict[str, Any]:
        """Build the recorded inputs of one batch's child workflow.

        Args:
            params (Dict[str, Any]): The inputs recorded for the parent.
            batch (List[Any]): The IDs of the batch.

        Returns:
            Dict[str, Any]: The parent's base inputs, with this batch's IDs.
        """
        from biomero import constants

        launcher_params = constants.launcher_params
        child_params = dict(params.get(launcher_params.BASE_INPUTS) or {})
        child_params[constants.transfer.IDS] = batch
        effective_type = params.get(launcher_params.EFFECTIVE_TYPE)
        if effective_type:
            child_params[constants.transfer.DATA_TYPE] = effective_type
        # All batches share one output dataset or screen.
        child_params[constants.workflow.OUTPUT_DUPLICATES] = False
        for name in (launcher_params.SELECTED_OUTPUT, launcher_params.GROUP):
            child_params[name] = params.get(name)
        return child_params

    def record_parent_outcome(self, tracker: "WorkflowTracker",
                              batch_count: int, queued_count: int,
                              failed_count: int) -> None:
        """Complete or fail the parent, once its children have ended.

        Args:
            tracker (WorkflowTracker): Tracker to write the outcome with.
            batch_count (int): How many batches the request has.
            queued_count (int): How many of them were queued as children.
            failed_count (int): How many children failed.
        """
        not_queued = batch_count - queued_count
        if failed_count or not_queued:
            cancelled = tracker.is_workflow_cancel_requested(self.workflow_id)
            prefix = "Cancelled: " if cancelled else ""
            outcome = "ended without completing" if cancelled else "failed"
            tracker.fail_workflow(
                self.workflow_id,
                f"{prefix}{failed_count + not_queued} of {batch_count} "
                f"batches {outcome}")
        else:
            # A cancel that came too late (every batch completed) changes
            # nothing: the workflow completed.
            tracker.complete_workflow(self.workflow_id)

    def cancel_children(self, tracker: "WorkflowTracker",
                        children: Iterable[Tuple[uuid.UUID, uuid.UUID]]
                        ) -> None:
        """Pass a cancel on to the unfinished child workflows.

        Each child cancels itself. A child whose batch task already completed
        or failed is left alone.

        Args:
            tracker (WorkflowTracker): Tracker to request the cancels with.
            children (Iterable[Tuple[uuid.UUID, uuid.UUID]]): The batch task
                ID and child workflow ID of each child.
        """
        for batch_task_id, child_wf_id in children:
            batch_task = tracker.repository.get(batch_task_id)
            if batch_task.completed or batch_task.failed:
                continue
            tracker.request_workflow_cancel(
                child_wf_id, f"Parent {self.workflow_id} cancelled")

    def await_children(self, slurm_client: "SlurmClient",
                       conn: "BlitzGateway", batched_script: Any,
                       children: "ChildrenByBatch", batches: List[List[Any]],
                       base_inputs: Dict[str, Any],
                       effective_type: Optional[str]
                       ) -> Tuple[int, "ChildrenByBatch"]:
        """Follow the child workflows, annotating each batch as it lands.

        Args:
            slurm_client (SlurmClient): Active SLURM client.
            conn (BlitzGateway): The user's OMERO connection.
            batched_script (Any): The SLURM_Run_Workflow_Batched module.
            children (ChildrenByBatch): The children to follow.
            batches (List[List[Any]]): The IDs of each batch.
            base_inputs (Dict[str, Any]): The parent's base inputs.
            effective_type (Optional[str]): The data type of the batches.

        Returns:
            Tuple[int, ChildrenByBatch]: How many batches failed, and the
                batches still unfinished (non-empty only when we stopped
                following them early).

        Raises:
            ClaimLost: When another supervisor owns the parent now.
        """
        from biomero.constants import workflow_status as wfs

        tracker = slurm_client.workflowTracker
        pending = dict(children)
        failed = 0
        cancel_passed_on = False
        while pending and not self.supervisor.shutdown_event.is_set():
            # A parent that lost its claim must not write child or parent
            # state.
            self.raise_if_claim_lost()
            if not cancel_passed_on and tracker.is_workflow_cancel_requested(
                    self.workflow_id):
                # Each child workflow cancels itself (its own jobs and
                # sub-scripts); this parent then waits for them to end.
                self.logger.info(f"Workflow {self.workflow_id} was cancelled; "
                                 f"cancelling its {len(pending)} unfinished "
                                 f"batches.")
                self.cancel_children(tracker, pending.values())
                cancel_passed_on = True
            statuses = self.read_child_statuses(
                [child_wf_id for _, child_wf_id in pending.values()])
            for index, (task_id, child_wf_id) in list(pending.items()):
                # Checked per child: annotating one batch can take a while.
                self.raise_if_claim_lost()
                status = statuses.get(child_wf_id)
                if status == wfs.DONE:
                    tracker.complete_task(task_id, "Batch completed.")
                    del pending[index]
                    self.annotate_batch(
                        slurm_client, conn, batched_script, index, batches,
                        base_inputs, effective_type)
                elif status == wfs.FAILED:
                    tracker.fail_task(task_id, "Batch failed.")
                    failed += 1
                    del pending[index]
                    self.logger.warning(f"Batch {index + 1} failed "
                                        f"(workflow {child_wf_id})")
            if pending:
                try:
                    conn.keepAlive()
                except Exception as e:
                    self.logger.debug(f"Could not keep the connection "
                                      f"alive: {e}")
                time.sleep(CHILD_POLL_SECONDS)
        return failed, pending

    @staticmethod
    def read_child_statuses(child_workflow_ids: List[uuid.UUID]
                            ) -> Dict[uuid.UUID, str]:
        """Read the projected status of child workflows.

        Args:
            child_workflow_ids (List[uuid.UUID]): The children to look up.

        Returns:
            Dict[uuid.UUID, str]: The status of each child that has a
                projection yet.
        """
        from biomero.database import EngineManager, WorkflowProgressView

        with EngineManager.get_session() as session:
            rows = session.query(WorkflowProgressView).filter(
                WorkflowProgressView.workflow_id.in_(
                    child_workflow_ids)).all()
            return {row.workflow_id: row.status for row in rows}

    def annotate_batch(self, slurm_client: "SlurmClient",
                       conn: "BlitzGateway", batched_script: Any, index: int,
                       batches: List[List[Any]], base_inputs: Dict[str, Any],
                       effective_type: Optional[str]) -> None:
        """Annotate a completed batch; a failure is logged, not raised.

        Args:
            slurm_client (SlurmClient): Active SLURM client.
            conn (BlitzGateway): The user's OMERO connection.
            batched_script (Any): The SLURM_Run_Workflow_Batched module.
            index (int): Index of the batch that completed.
            batches (List[List[Any]]): The IDs of each batch.
            base_inputs (Dict[str, Any]): The parent's base inputs.
            effective_type (Optional[str]): The data type of the batches.
        """
        try:
            batched_script.add_batch_supervisor_metadata_for_batch(
                conn, slurm_client, self.workflow_id, index,
                batches[index], len(batches), base_inputs, effective_type)
        except Exception as e:
            self.logger.warning(f"Could not annotate batch {index + 1}: {e}")


class MaintenanceWorker(WorkflowWorker):
    """Execute a durable admin request using an independently owned session."""

    # The refresh request is read from a tracker whose tables already exist.
    TRACKER_ENV = {"CREATE_TABLE": "no", "WORKFLOWTRACKER_CREATE_TABLE": "no"}
    DEFAULT_WORKERS = 4
    DEFAULT_VIEW_VERSION = "v0"
    # What a finished request keeps of the sweep report.
    REPORT_KEYS = ("discovered", "counts", "backup_directory")

    def __init__(self, request_id: uuid.UUID,
                 supervisor: "WorkflowSupervisor") -> None:
        """Prepare a worker for one metadata refresh request.

        Args:
            request_id (uuid.UUID): The refresh request to run.
            supervisor (WorkflowSupervisor): The supervisor that owns this
                worker.
        """
        Thread.__init__(self, name=f"MetadataRefresh-{request_id}")
        self.daemon = True
        # Reuse user_connection(), not analysis submission or workflow events.
        self.workflow_id = request_id
        self.supervisor = supervisor
        self.logger = logging.getLogger(
            f"biomero.detached.maintenance.{request_id}")

    def run(self) -> None:
        """Run the metadata refresh request, then free the maintenance lane."""
        try:
            from biomero import WorkflowTracker
            with WorkflowTracker(env=self.TRACKER_ENV) as tracker:
                self.run_request(tracker)
        except Exception:
            # A persistence outage leaves QUEUED/RUNNING recoverable, not lost.
            self.logger.exception(f"Cannot persist metadata request "
                                  f"{self.workflow_id} outcome")
        finally:
            self.supervisor.remove_maintenance_worker(self.workflow_id)

    def run_request(self, tracker: "WorkflowTracker") -> None:
        """Run the request if it is still active, and record its outcome.

        A request that is no longer QUEUED or RUNNING is left alone. A failure
        finishes the request with the error, so the request does not stay
        active forever.

        Args:
            tracker (WorkflowTracker): Tracker holding the request.
        """
        from biomero.constants import metadata_refresh_status as refresh_status

        request = None
        try:
            request = tracker.repository.get(self.workflow_id)
            if request.status not in refresh_status.ACTIVE:
                return
            self.refresh_metadata(tracker, request)
        except Exception as error:
            self.logger.exception(f"Metadata refresh request "
                                  f"{self.workflow_id} failed")
            if (request is not None
                    and request.status in refresh_status.ACTIVE):
                request.finished(request.report,
                                 str(error) or type(error).__name__)
                tracker.save(request)
        finally:
            tracker.release_database_connections()

    def refresh_metadata(self, tracker: "WorkflowTracker",
                         request: Any) -> None:
        """Sweep the metadata of all workflows, as the request asks.

        Args:
            tracker (WorkflowTracker): Tracker holding the request.
            request (Any): The metadata refresh request aggregate.

        Raises:
            ValueError: When the request's user is not an administrator.
        """
        from functools import partial
        from biomero.constants import metadata_refresh_status as refresh_status

        resuming = request.status == refresh_status.RUNNING
        script = load_metadata_script()
        with self.user_connection(request) as conn:
            if not conn.isAdmin():
                raise ValueError("Metadata refresh requires an administrator")
            self.logger.info(
                f"Metadata refresh request {self.workflow_id}: "
                f"{'resuming interrupted sweep' if resuming else 'starting'}")
            request.started()
            tracker.save(request)
            options = request.options
            backup_directory = options.get("backup_directory")
            if (resuming and backup_directory
                    and options.get("backup_enabled")):
                # Previous files must never be overwritten on recovery.
                backup_directory = f"{backup_directory}-resume-{uuid.uuid4()}"

            workers = options.get("workers", self.DEFAULT_WORKERS)
            worker_factory = None
            if workers > 1:
                worker_factory = partial(script.metadata_refresh_worker, conn,
                                         tracker, conn.c.getSessionId())
            report = script.refresh_all_metadata(
                conn, tracker,
                view_version=options.get("view_version",
                                         self.DEFAULT_VIEW_VERSION),
                dry_run=False, backup_directory=backup_directory,
                backup_enabled=options.get("backup_enabled", False),
                workflow_ids=options.get("workflow_ids"), workers=workers,
                worker_factory=worker_factory,
                progress_callback=partial(self.record_progress, tracker,
                                          request))
            compact = {key: report[key] for key in self.REPORT_KEYS
                       if key in report}
            request.finished(compact)
            tracker.save(request)
            backups = report.get("backup_directory") or "not requested"
            self.logger.info(
                f"Metadata refresh request {self.workflow_id}: "
                f"{request.status}; pairs={report.get('discovered', 0)}; "
                f"{self.counts_summary(report)}; backups={backups}")

    def record_progress(self, tracker: "WorkflowTracker", request: Any,
                        report: Dict[str, Any]) -> None:
        """Save and log the progress of the sweep.

        Args:
            tracker (WorkflowTracker): Tracker holding the request.
            request (Any): The metadata refresh request aggregate.
            report (Dict[str, Any]): The sweep's progress report.
        """
        request.progressed(report)
        tracker.save(request)
        self.logger.info(
            f"Metadata refresh request {self.workflow_id}: "
            f"{report['processed']}/{report['discovered']}; "
            f"{self.counts_summary(report)}")

    @staticmethod
    def counts_summary(report: Dict[str, Any]) -> str:
        """Summarize the counts of a sweep report for the logs.

        Args:
            report (Dict[str, Any]): A sweep report with a ``counts`` mapping.

        Returns:
            str: The counts as ``key=value`` pairs, separated by commas.
        """
        return ", ".join(f"{key}={value}"
                         for key, value in report["counts"].items())


class WorkflowSupervisor(Thread):
    """Finds queued workflows and runs each of them in a worker thread."""

    def __init__(self) -> None:
        """Prepare a supervisor; it supervises once its thread is started."""
        super(WorkflowSupervisor, self).__init__(name="WorkflowSupervisor")
        self.daemon = True
        self.shutdown_event = Event()
        self.active_workers: Dict[uuid.UUID, WorkflowWorker] = {}
        self.maintenance_workers = {}
        self.maintenance_pending = set()
        self.maintenance_cursor = 1
        # Workflows that are not ours to run.
        self.ignored: Set[uuid.UUID] = set()
        # Monotonic time at which the worker of a workflow last ended.
        self.ended_at: Dict[uuid.UUID, float] = {}
        # Launcher task of each workflow whose worker ended during the
        # shutdown, still to be released by the supervisor thread: the tracker
        # belongs to that thread, so the workers never use it.
        self.pending_release: Dict[uuid.UUID, uuid.UUID] = {}
        # Names this supervisor in the claims it holds, so that a replacement
        # process (which has a new name) recognizes a claim as not its own.
        self.owner = f"supervisor-{socket.gethostname()}-{uuid.uuid4()}"
        self.next_claim_renewal = 0.0
        self.tracker = None
        self.lock = Lock()
        self.logger = logging.getLogger("biomero.detached.supervisor")

    def run(self) -> None:
        """Supervise queued workflows until stopped, then release claims."""
        self.logger.info(f"Starting the BIOMERO workflow supervisor "
                         f"{self.owner}")
        if not self.set_up():
            return

        if SUPERVISOR_STARTUP_GRACE_SECONDS:
            self.logger.info(f"Waiting {SUPERVISOR_STARTUP_GRACE_SECONDS}s "
                             f"for this processor to start taking work")
            self.shutdown_event.wait(SUPERVISOR_STARTUP_GRACE_SECONDS)

        polls = 0
        while not self.shutdown_event.is_set():
            self.poll(polls)
            polls += 1
            self.shutdown_event.wait(SUPERVISOR_POLL_SECONDS)
        self.release_claims()
        self.logger.info("Workflow supervisor shutting down")

    def set_up(self) -> bool:
        """Open the tracking database session and tracker, retrying while
        the database cannot be reached.

        The processor can start before the database does, so a database
        error is logged and retried with a growing wait, from
        ``SUPERVISOR_POLL_SECONDS`` up to ``SUPERVISOR_SETUP_RETRY_MAX_SECONDS``
        (never below ``SUPERVISOR_SETUP_RETRY_MIN_SECONDS``). Any other error
        is a defect that waiting does not fix, so it ends the supervisor.

        Returns:
            bool: True when ready to supervise; False when the shutdown came
            first or the set-up failed for a reason other than the database.
        """
        from biomero.database import backoff_delay
        from biomero.views import LOOKUP_ERRORS
        attempt = 0
        while not self.shutdown_event.is_set():
            try:
                self.open_tracker()
            except LOOKUP_ERRORS as e:
                delay = max(
                    backoff_delay(attempt, SUPERVISOR_POLL_SECONDS,
                                  SUPERVISOR_SETUP_RETRY_MAX_SECONDS),
                    SUPERVISOR_SETUP_RETRY_MIN_SECONDS)
                attempt += 1
                self.logger.warning(
                    f"Cannot supervise workflows yet: cannot reach the "
                    f"database, retrying in {delay:.0f}s "
                    f"(attempt {attempt}): {e}")
                self.shutdown_event.wait(delay)
            except Exception as e:
                self.logger.error(f"Cannot supervise workflows: {e}",
                                  exc_info=True)
                return False
            else:
                if attempt:
                    self.logger.info(f"Supervisor set-up succeeded after "
                                     f"{attempt} failed attempts")
                return True
        self.logger.info("Workflow supervisor stopped before it could "
                         "set up")
        return False

    def open_tracker(self) -> None:
        """Open the database session and tracker, and route sub-scripts."""
        from biomero import WorkflowTracker
        from biomero.database import EngineManager
        run_workflow_script, _ = load_biomero_scripts()
        EngineManager.create_scoped_session()
        self.tracker = WorkflowTracker()
        # Sub-scripts cannot be waited on with a script callback here, so
        # the workflow scripts use our polling runner instead.
        run_workflow_script.SCRIPT_RUNNER = polling_script_runner

    def poll(self, polls: int) -> None:
        """Look once for work; a failure is logged and the next poll retries.

        Args:
            polls (int): How many polls were made before this one.
        """
        try:
            self.prune_workers()
            if polls % IGNORE_CACHE_POLLS == 0:
                with self.lock:
                    self.ignored.clear()
            self.renew_claims()
            self.spawn_workers()
            self.spawn_maintenance()
        except Exception as e:
            self.logger.error(f"Supervisor poll failed: {e}", exc_info=True)

    def unfinished_workflows(self) -> List[Tuple[uuid.UUID, float]]:
        """Every workflow that has not reached a final state, with its age.

        The task execution view does not record which workflow a task belongs
        to, so candidates cannot be narrowed down to queued runs in SQL; that
        is what the launcher lookup below is for.

        Returns:
            List[Tuple[uuid.UUID, float]]: ``(workflow_id, age_in_seconds)``
                pairs.
        """
        from biomero.constants import workflow_status as wfs
        from biomero.database import EngineManager, WorkflowProgressView

        now = datetime.now(timezone.utc)
        with EngineManager.get_session() as session:
            rows = session.query(
                WorkflowProgressView.workflow_id,
                WorkflowProgressView.start_time).filter(
                    WorkflowProgressView.status.notin_(wfs.FINAL)).all()
        workflows = []
        for workflow_id, start_time in rows:
            if start_time is None:
                age = 0.0
            else:
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone.utc)
                age = (now - start_time).total_seconds()
            workflows.append((workflow_id, age))
        return workflows

    def spawn_workers(self) -> None:
        """Claim each queued workflow that has no worker yet, and start one."""
        for wf_id, age in self.unfinished_workflows():
            with self.lock:
                if wf_id in self.active_workers or wf_id in self.ignored:
                    continue
                busy = self.slots_in_use()
            if busy >= MAX_ACTIVE_WORKFLOWS:
                self.logger.debug(
                    f"Running {busy} workflows already; {wf_id} waits.")
                return
            if self.recently_ended(wf_id):
                continue
            launcher = self.find_launcher(wf_id, age)
            if launcher is None:
                continue
            if not self.still_to_run(wf_id):
                continue
            if not self.claim_workflow(wf_id, launcher):
                continue
            self.start_worker(wf_id, launcher)

    def slots_in_use(self) -> int:
        """Count the running workers that take up an execution slot.

        The caller holds ``self.lock``.

        Returns:
            int: The number of workers holding a slot.
        """
        return sum(1 for worker in self.active_workers.values()
                   if worker.holds_slot)

    def find_launcher(self, wf_id: uuid.UUID, age: float) -> Optional[Any]:
        """Find the launcher task that queued a workflow for this processor.

        Args:
            wf_id (uuid.UUID): The workflow to look at.
            age (float): Seconds since the workflow started.

        Returns:
            Optional[Any]: The launcher task, or None when the workflow is not
                (yet) one that this supervisor runs.
        """
        try:
            launcher = self.tracker.find_launcher_task(wf_id)
        except Exception as e:
            # An unreadable workflow is not one that is not ours: look
            # again on the next poll instead of ignoring it.
            self.logger.warning(f"Could not read workflow {wf_id}; "
                                f"trying again next poll: {e}")
            return None
        if launcher is not None:
            return launcher
        if age < IGNORE_MIN_AGE_SECONDS:
            # Possibly still being set up by the script that started
            # it; look again next time.
            return None
        # Started by a script that runs its own pipeline, so it is not
        # ours to run. Remembered until the cache is next dropped.
        self.logger.debug(f"Workflow {wf_id} was not queued for us; "
                          f"leaving it alone.")
        self.ignore(wf_id)
        return None

    def still_to_run(self, wf_id: uuid.UUID) -> bool:
        """Check the event store that a workflow has not reached a final state.

        The progress view is only a projection: while it is rebuilt, a row can
        be non-final although the workflow already ended. The workflow
        aggregate is the source of truth, so it is read before claiming.

        Args:
            wf_id (uuid.UUID): The workflow to look at.

        Returns:
            bool: False when the workflow is final and must not be run again,
                or cannot be read (looked at again on the next poll).
        """
        try:
            ended = self.tracker.is_workflow_finished(wf_id)
        except Exception as e:
            self.logger.warning(f"Could not read workflow {wf_id}; "
                                f"trying again next poll: {e}")
            return False
        if ended:
            self.logger.debug(f"Workflow {wf_id} is final in the event "
                              f"store; not running it again.")
        return not ended

    def claim_workflow(self, wf_id: uuid.UUID, launcher: Any) -> bool:
        """Claim a workflow's launcher task for this supervisor.

        Args:
            wf_id (uuid.UUID): The workflow to claim.
            launcher (Any): Its launcher task.

        Returns:
            bool: Whether the claim is held by this supervisor now.
        """
        if not self.tracker.claim_launcher_task(launcher.id, self.owner):
            self.logger.debug(f"Workflow {wf_id} is claimed by another "
                              f"supervisor; leaving it to them.")
            return False
        self.logger.info(f"Claimed workflow {wf_id}; starting its worker.")
        return True

    def start_worker(self, wf_id: uuid.UUID, launcher: Any) -> None:
        """Start the worker that runs a claimed workflow.

        Args:
            wf_id (uuid.UUID): The workflow to run.
            launcher (Any): Its launcher task, which says whether the
                workflow is a batched parent.
        """
        from biomero import constants

        batched = launcher.task_name == constants.RUN_WF_BATCHED_SCRIPT
        with self.lock:
            worker = WorkflowWorker(wf_id, launcher.id, batched, self)
            self.active_workers[wf_id] = worker
        worker.start()

    def running_workers(self) -> List["WorkflowWorker"]:
        """Take a snapshot of the running workers.

        Returns:
            List[WorkflowWorker]: The workers of the claimed workflows.
        """
        with self.lock:
            return list(self.active_workers.values())

    def recently_ended(self, wf_id: uuid.UUID) -> bool:
        """Tell whether a workflow's worker ended too recently to run again.

        A worker that ends without its workflow reaching a final state is not
        started again at once, so a persistent problem is retried at a calm
        pace instead of on every poll.

        Args:
            wf_id (uuid.UUID): The workflow to check.

        Returns:
            bool: True while the workflow's restart delay runs.
        """
        ended_at = self.ended_at.get(wf_id)
        if ended_at is None:
            return False
        waiting = ended_at + WORKER_RESTART_DELAY_SECONDS - time.monotonic()
        if waiting <= 0:
            return False
        self.logger.debug(f"Worker of workflow {wf_id} ended recently; "
                          f"running it again in {waiting:.0f}s.")
        return True

    def renew_claims(self) -> None:
        """Keep the claims on the launchers of running workflows alive."""
        now = time.monotonic()
        if now < self.next_claim_renewal:
            return
        self.next_claim_renewal = now + CLAIM_RENEW_SECONDS
        for worker in self.running_workers():
            try:
                self.renew_claim(worker)
            except Exception as e:
                # The claim is renewed again on the next renewal, well within
                # its lease; one unreadable workflow must not skip the others.
                self.logger.warning(f"Could not renew the claim on workflow "
                                    f"{worker.workflow_id}; trying again: {e}")

    def renew_claim(self, worker: "WorkflowWorker") -> None:
        """Renew one claim; when it is lost, tell the worker to stop.

        Args:
            worker (WorkflowWorker): The worker whose launcher task claim to
                renew.
        """
        if self.tracker.claim_launcher_task(worker.launcher_task_id,
                                            self.owner):
            return
        launcher = self.tracker.repository.get(worker.launcher_task_id)
        if launcher.claimed_by is None:
            self.logger.info(f"The claim on workflow {worker.workflow_id} "
                             f"was released; stopping its worker.")
            worker.claim_lost.set()
            return
        if launcher.claimed_by == self.owner:
            # A concurrent write to the task made the renewal conflict; the
            # claim is still ours and the next renewal retries.
            self.logger.debug(f"Renewal of the claim on workflow "
                              f"{worker.workflow_id} conflicted with another "
                              f"write; still ours.")
            return
        self.logger.error(
            f"Lost the claim on workflow {worker.workflow_id} to "
            f"{launcher.claimed_by}; stopping this supervisor's worker.")
        worker.taken_over = True
        worker.claim_lost.set()

    def release_claims(self) -> None:
        """On a clean shutdown, hand the running workflows back at once.

        Runs in the supervisor thread, which owns the tracker: it releases the
        claims of the running workers and of the workers that ended during the
        shutdown (``remove_worker`` only notes those).
        """
        running = self.running_workers()
        with self.lock:
            ended = dict(self.pending_release)
            self.pending_release.clear()
        for worker in running:
            # Stop the worker first: once the claim is released another
            # supervisor may take the workflow over, and this worker must not
            # write to it any more. It stops whether or not the release works
            # (a claim that is not released runs out on its own).
            worker.claim_lost.set()
            self.release_claim(worker.workflow_id, worker.launcher_task_id)
        running_ids = {worker.workflow_id for worker in running}
        for wf_id, launcher_task_id in ended.items():
            if wf_id not in running_ids:
                self.release_claim(wf_id, launcher_task_id)

    def release_claim(self, wf_id: uuid.UUID,
                      launcher_task_id: uuid.UUID) -> bool:
        """Give up this supervisor's claim on a workflow's launcher task.

        Args:
            wf_id (uuid.UUID): The workflow, for the logs.
            launcher_task_id (uuid.UUID): The launcher task holding the claim.

        Returns:
            bool: Whether the claim was released; when it was not (not held
                any more, or the task changed meanwhile), it is left to its
                new owner or runs out on its own.
        """
        try:
            released = self.tracker.release_launcher_task(launcher_task_id,
                                                          self.owner)
        except Exception as e:
            self.logger.warning(f"Could not release workflow {wf_id}; "
                                f"its claim runs out on its own: {e}")
            return False
        if released:
            self.logger.info(f"Released the claim on workflow {wf_id}.")
        else:
            self.logger.debug(f"The claim on workflow {wf_id} is not held "
                              f"by this supervisor, or changed meanwhile; "
                              f"nothing released.")
        return released

    def prune_workers(self) -> None:
        """Forget the workers that ended, and restart delays that ran out."""
        with self.lock:
            for wf_id, worker in list(self.active_workers.items()):
                if not worker.is_alive():
                    self.active_workers.pop(wf_id)
            # Only recent endings matter for the restart delay.
            now = time.monotonic()
            for wf_id, ended_at in list(self.ended_at.items()):
                if now - ended_at > WORKER_RESTART_DELAY_SECONDS:
                    self.ended_at.pop(wf_id)

    def spawn_maintenance(self) -> None:
        """Start one metadata sweep, if one is pending and none is running.

        Sweeps run one at a time, independent of the analysis concurrency
        slots.
        """
        from biomero import maintenance
        self.maintenance_cursor, self.maintenance_pending = (
            maintenance.pending_metadata_refreshes(
                self.tracker, self.maintenance_cursor,
                self.maintenance_pending))
        with self.lock:
            for request_id, worker in list(self.maintenance_workers.items()):
                if not worker.is_alive():
                    self.maintenance_workers.pop(request_id)
            if self.maintenance_workers or not self.maintenance_pending:
                return
            request_id = sorted(self.maintenance_pending, key=str)[0]
            worker = MaintenanceWorker(request_id, self)
            self.maintenance_workers[request_id] = worker
        worker.start()

    def remove_maintenance_worker(self, request_id: uuid.UUID) -> None:
        """Forget a maintenance worker that ended.

        Args:
            request_id (uuid.UUID): The metadata refresh request it ran.
        """
        with self.lock:
            self.maintenance_workers.pop(request_id, None)

    def remove_worker(self, wf_id: uuid.UUID,
                      launcher_task_id: uuid.UUID) -> None:
        """Forget a worker that ended; note its claim for release on shutdown.

        Called from the worker thread, so it does not use the tracker: during
        a shutdown the supervisor thread releases the claim
        (``release_claims``).

        Args:
            wf_id (uuid.UUID): The workflow the worker ran.
            launcher_task_id (uuid.UUID): Its launcher task, whose claim is
                released when this supervisor is shutting down.
        """
        with self.lock:
            self.active_workers.pop(wf_id, None)
            self.ended_at[wf_id] = time.monotonic()
            if self.shutdown_event.is_set():
                self.pending_release[wf_id] = launcher_task_id
        self.logger.info(f"Worker of workflow {wf_id} ended; the workflow is "
                         f"run again if it did not reach a final state.")

    def ignore(self, wf_id: uuid.UUID) -> None:
        """Stop inspecting a workflow that is not ours to run.

        Args:
            wf_id (uuid.UUID): The workflow to leave alone until the ignore
                list is next cleared.
        """
        with self.lock:
            self.ignored.add(wf_id)

    def stop(self, timeout: float = SUPERVISOR_STOP_TIMEOUT_SECONDS) -> None:
        """Stop the supervisor, and wait for it to release its claims.

        Args:
            timeout (float): How long to wait for the supervisor thread, in
                seconds; claims it did not release run out on their own.
        """
        self.shutdown_event.set()
        if not self.is_alive() or self is current_thread():
            return
        self.join(timeout)
        if self.is_alive():
            self.logger.warning(f"The supervisor did not stop within "
                                f"{timeout}s; unreleased claims run out on "
                                f"their own.")
        else:
            self.logger.info("The supervisor stopped.")


class ProcessorI(omero.grid.Processor, omero.util.Servant):

    def __init__(self, ctx, needs_session=True, use_session=None,
                 accepts_list=None, cfg=None, omero_home=path.getcwd(),
                 category=None):

        # Run queued BIOMERO workflows alongside this processor, if this
        # deployment asked for detached runs. A failure to start the
        # supervisor never stops the processor itself from starting.
        self.supervisor = None
        try:
            from biomero.detached import detached_mode_enabled
            if detached_mode_enabled():
                self.supervisor = WorkflowSupervisor()
                self.supervisor.start()
            else:
                biomero_logger.info(
                    "BIOMERO_DETACHED_WORKFLOWS is not enabled; workflows "
                    "run inside the calling session.")
        except Exception as e:
            biomero_logger.error(f"Could not start the workflow supervisor: "
                                 f"{e}", exc_info=True)

        if accepts_list is None:
            accepts_list = []

        self.category = category  #: Category to be used w/ ProcessI
        self.omero_home = omero_home

        # Extensions for user-mode processors (ticket:1672)

        self.use_session = use_session
        """
        If set, this session will be returned from internal_session and
        the "needs_session" setting ignored.
        """

        if self.use_session:
            needs_session = False

        self.accepts_list = accepts_list
        """
        A list of contexts which will be accepted by this user-mode
        processor.
        """

        omero.util.Servant.__init__(self, ctx, needs_session=needs_session)
        if cfg is None:
            self.cfg = os.path.join(omero_home, "etc", "ice.config")
            self.cfg = os.path.abspath(self.cfg)
        else:
            self.cfg = cfg

        # Keep this session alive until the processor is finished
        self.resources.add(UseSessionHolder(use_session))

    def cleanup(self) -> None:
        """Stop the workflow supervisor, then clean up the servant.

        ``omero.util.Server.run`` calls this when the node stops (after
        SIGTERM or a shutdown request), and the servant's ``__del__`` calls it
        again, so it is safe to repeat. The supervisor hands its claims back
        before it stops, so another supervisor takes over at once instead of
        after the lease.
        """
        supervisor = getattr(self, "supervisor", None)
        if supervisor is not None:
            self.supervisor = None
            supervisor.stop()
        omero.util.Servant.cleanup(self)

    def setProxy(self, prx):
        """
        Overrides the default action in order to register this proxy
        with the session's sharedResources to register for callbacks.
        The on_newsession handler will also keep new sessions informed.

        See ticket:2304
        """
        omero.util.Servant.setProxy(self, prx)
        session = self.internal_session()
        self.register_session(session)

        # Keep other session informed
        self.ctx.on_newsession = self.register_session

    def user_client(self, agent):
        """
        Creates an omero.client instance for use by
        users.
        """
        args = ["--Ice.Config=%s" % (self.cfg)]
        rtr = self.internal_session().ice_getRouter()
        if rtr:
            # FIXME : How do we find an internal router?
            args.insert(0, "--Ice.Default.Router=%s" % rtr)
        client = omero.client(args)
        client.setAgent(agent)
        return client

    def internal_session(self):
        """
        Returns the session which should be used for lookups by this instance.
        Some methods will create a session based on the session parameter.
        In these cases, the session will belong to the user who is running a
        script.
        """
        if self.use_session:
            return self.use_session
        else:
            return self.ctx.getSession()

    def register_session(self, session):
        self.logger.info("Registering processor %s", self.prx)
        prx = omero.grid.ProcessorPrx.uncheckedCast(self.prx)
        session.sharedResources().addProcessor(prx)

    def lookup(self, job):
        sf = self.internal_session()
        gid = job.details.group.id.val
        handle = WithGroup(sf.createJobHandle(), gid)
        try:
            handle.attach(job.id.val)
            if handle.jobFinished():
                handle.close()
                raise omero.ApiUsageException("Job already finished.")

            prx = WithGroup(sf.getScriptService(), gid)
            file = prx.validateScript(job, self.accepts_list)

        except omero.SecurityViolation:
            self.logger.debug(
                "SecurityViolation on validate job %s from group %s",
                job.id.val, gid)
            file = None

        return file, handle

    @remoted
    def willAccept(self, userContext, groupContext, scriptContext, cb,
                   current=None):

        userID = None
        if userContext is not None:
            userID = userContext.id.val

        groupID = None
        if groupContext is not None:
            groupID = groupContext.id.val

        scriptID = None
        if scriptContext is not None:
            scriptID = scriptContext.id.val

        if scriptID:
            try:
                file, handle = self.lookup(scriptContext)
                handle.close()
                valid = (file is not None)
            except:
                self.logger.error(
                    "File lookup failed: user=%s, group=%s, script=%s",
                    userID, groupID, scriptID, exc_info=1)
                return  # EARlY EXIT !
        else:
            valid = False
            for x in self.accepts_list:
                if isinstance(x, omero.model.Experimenter) and \
                        x.id.val == userID:
                    valid = True
                elif isinstance(x, omero.model.ExperimenterGroup) and \
                        x.id.val == groupID:
                    valid = True

        self.logger.debug(
            "Accepts called on: user:%s group:%s scriptjob:%s - Valid: %s",
            userID, groupID, scriptID, valid)

        try:
            id = self.internal_session().ice_getIdentity().name
            cb = cb.ice_oneway()
            cb = omero.grid.ProcessorCallbackPrx.uncheckedCast(cb)
            prx = omero.grid.ProcessorPrx.uncheckedCast(self.prx)
            cb.isProxyAccepted(valid, id, prx)
        except Exception as e:
            self.logger.warn(
                "callback failed on willAccept: %s Exception:%s", cb, e)

        return valid

    @remoted
    def requestRunning(self, cb, current=None):

        try:
            cb = cb.ice_oneway()
            cb = omero.grid.ProcessorCallbackPrx.uncheckedCast(cb)
            servants = list(self.ctx.servant_map.values())
            rv = []

            for x in servants:
                try:
                    rv.append(int(x.properties["omero.job"]))
                except:
                    pass
            cb.responseRunning(rv)
        except Exception as e:
            self.logger.warn(
                "callback failed on requestRunning: %s Exception:%s", cb, e)

    @remoted
    def parseJob(self, session, job, current=None):
        self.logger.info(
            "parseJob: Session = %s, JobId = %s" % (session, job.id.val))
        client = self.user_client("OMERO.parseJob")

        try:
            iskill = False
            client.joinSession(session).detachOnDestroy()
            properties = {}
            properties["omero.scripts.parse"] = "true"
            prx, process = self.process(
                client, session, job, current, None, properties, iskill)
            process.wait()
            rv = client.getOutput("omero.scripts.parse")
            if rv is not None:
                return rv.val
            else:
                self.logger.warning(
                    "No output found for omero.scripts.parse. Keys: %s"
                    % client.getOutputKeys())
                return None
        finally:
            client.closeSession()
            del client

    @remoted
    def processJob(self, session, params, job, current=None):
        """
        """
        self.logger.info("processJob: Session = %s, JobId = %s"
                         % (session, job.id.val))
        client = self.user_client("OMERO.processJob")
        try:
            client.joinSession(session).detachOnDestroy()
            prx, process = self.process(
                client, session, job, current, params, iskill=True)
            return prx
        finally:
            client.closeSession()
            del client

    @perf
    def process(self, client, session, job, current, params, properties=None,
                iskill=True):
        """
        session: session uuid, used primarily if client is None
        client: an omero.client object which should be attached to a session
        """

        if properties is None:
            properties = {}

        if not session or not job or not job.id:
            raise omero.ApiUsageException("No null arguments")

        file, handle = self.lookup(job)

        try:
            if not file:
                raise omero.ApiUsageException(
                    None, None,
                    "Job should have one executable file attached.")

            sf = self.internal_session()
            if params:
                self.logger.debug("Checking params for job %s" % job.id.val)
                svc = sf.getSessionService()
                inputs = svc.getInputs(session)
                errors = omero.scripts.validate_inputs(
                    params, inputs, svc, session)
                if errors:
                    errors = "Invalid parameters:\n%s" % errors
                    raise omero.ValidationException(None, None, errors)

            properties["omero.job"] = str(job.id.val)
            properties["omero.user"] = session
            properties["omero.pass"] = session
            properties["Ice.Default.Router"] = \
                client.getProperty("Ice.Default.Router")

            launcher, ProcessClass = self.find_launcher(current)
            process = ProcessClass(self.ctx, launcher, properties, params,
                                   iskill, omero_home=self.omero_home)
            self.resources.add(process)

            # client.download(file, str(process.script_path))
            scriptText = sf.getScriptService().getScriptText(file.id.val)
            process.script_path.write_bytes(scriptText.encode('utf-8'))

            self.logger.info("Downloaded file: %s" % file.id.val)
            s = client.sha1(str(process.script_path))
            if not s == file.hash.val:
                msg = "Sha1s don't match! expected %s, found %s" \
                    % (file.hash.val, s)
                self.logger.error(msg)
                process.cleanup()
                raise omero.InternalException(None, None, msg)
            else:
                process.activate()
                handle.setStatus("Running")

            id = None
            if self.category:
                id = Ice.Identity()
                id.name = "Process-%s" % uuid.uuid4()
                id.category = self.category
            prx = self.ctx.add_servant(current, process, ice_identity=id)
            return omero.grid.ProcessPrx.uncheckedCast(prx), process

        finally:
            handle.close()

    def find_launcher(self, current):
        launcher = ""
        process_class = ""
        if current.ctx:
            launcher = current.ctx.get("omero.launcher", "")
            process_class = current.ctx.get(
                "omero.process", "omero.process.ProcessI")

        if not launcher:
            launcher = sys.executable

        self.logger.info("Using launcher: %s", launcher)
        self.logger.info("Using process: %s", process_class)

        # Imports in omero.util don't work well for this class
        # Handling classes from this module specially.
        internal = False
        parts = process_class.split(".")
        if len(parts) == 3:
            if parts[0:2] == ("omero", "processor"):
                internal = True

        if not process_class:
            ProcessClass = ProcessI
        elif internal:
            ProcessClass = globals()[parts[-1]]
        else:
            ProcessClass = load_dotted_class(process_class)
        return launcher, ProcessClass


def usermode_processor(client, serverid="UsermodeProcessor", cfg=None,
                       accepts_list=None, stop_event=None,
                       omero_home=path.getcwd()):
    """
    Creates and activates a usermode processor for the given client.
    It is the responsibility of the client to call "cleanup()" on
    the ProcessorI implementation which is returned.

    cfg is the path to an --Ice.Config-valid file or files. If none
    is given, the value of ICE_CONFIG will be taken from the environment
    if available. Otherwise, all properties will be taken from the client
    instance.

    accepts_list is the list of IObject instances which will be passed to
    omero.api.IScripts.validateScript. If none is given, only the current
    Experimenter's own object will be passed.

    stop_event is an threading.Event. One will be acquired from
    omero.util.concurrency.get_event if none is provided.
    """

    if cfg is None:
        cfg = os.environ.get("ICE_CONFIG")

    if accepts_list is None:
        uid = client.sf.getAdminService().getEventContext().userId
        accepts_list = [omero.model.ExperimenterI(uid, False)]

    if stop_event is None:
        stop_event = omero.util.concurrency.get_event(name="UsermodeProcessor")

    id = Ice.Identity()
    id.name = "%s-%s" % (serverid, uuid.uuid4())
    id.category = client.getCategory()

    ctx = omero.util.ServerContext(serverid, client.ic, stop_event)
    impl = omero.processor.ProcessorI(
        ctx, use_session=client.sf, accepts_list=accepts_list, cfg=cfg,
        omero_home=omero_home, category=id.category)
    ctx.add_servant(client.adapter, impl, ice_identity=id)
    return impl
