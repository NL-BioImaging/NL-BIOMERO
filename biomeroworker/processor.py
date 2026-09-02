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
import os
import time
import signal
import uuid
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
    _BIOMERO_ENV_VARS = []

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
from threading import Thread, Lock, Event

# How many workflows to drive at once. Batched parents do not count: they only
# wait for their children, and counting them could starve those children.
MAX_ACTIVE_WORKFLOWS = int(os.environ.get("BIOMERO_MAX_ACTIVE_WORKFLOWS", "4"))
# How often to look for newly queued workflows.
SUPERVISOR_POLL_SECONDS = int(
    os.environ.get("BIOMERO_SUPERVISOR_POLL_SECONDS", "10"))
# How often a batched parent checks on its children.
CHILD_POLL_SECONDS = 15
# Workflows found not to be ours are remembered so we do not keep inspecting
# them, but the memory is dropped periodically so that a transient database
# error cannot sideline a workflow until the next restart.
IGNORE_CACHE_POLLS = 90

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


def wrap_value(value):
    """Wrap a recorded input value back into the OMERO rtype a script expects."""
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
    that is carried here so the runner can reach it.
    """

    def __init__(self, params, conn=None):
        self.params = params or {}
        self.conn = conn
        self.outputs = {}

    def getInput(self, key):
        return wrap_value(self.params.get(key))

    def getInputs(self, unwrap=False):
        if unwrap:
            return dict(self.params)
        return {key: wrap_value(value) for key, value in self.params.items()}

    def setOutput(self, key, value):
        self.outputs[key] = value

    def closeSession(self):
        # The connection belongs to the worker, which closes it when done.
        pass


def polling_script_runner(client, svc, script_id, inputs,
                          slurmClient=None):
    """Run an OMERO sub-script and wait for it, without a script session.

    omero.scripts.ProcessCallbackI needs a script session to receive the
    process callback on, which a detached run does not have. Poll the process
    instead, keeping the user's connection alive and pumping the workflow
    progress listener so that the UI keeps moving while the sub-script runs.

    Args:
        client: The stand-in client for this run (carries the connection).
        svc: OMERO script service.
        script_id: ID of the sub-script to run.
        inputs: Sub-script inputs.
        slurmClient: Active SLURM client, for its progress listener.

    Returns:
        tuple: (results, job) exactly as runOMEROScript() returns them.
    """
    logger = logging.getLogger("biomero.detached.script")
    proc = svc.runScript(int(script_id), inputs, None)
    conn = getattr(client, "conn", None)
    try:
        next_position = 0
        if slurmClient is not None and slurmClient.wfProgress is not None:
            try:
                next_position = slurmClient.wfProgress.recorder.max_tracking_id(
                    application_name='WorkflowTracker') or 0
            except Exception:
                next_position = 0
        while proc.poll() is None:
            if conn is not None:
                try:
                    conn.keepAlive()
                except Exception as e:
                    logger.debug(f"Could not keep the connection alive: {e}")
            if slurmClient is not None and slurmClient.wfProgress is not None:
                try:
                    slurmClient.bring_listener_uptodate(
                        slurmClient.wfProgress, start=next_position)
                except Exception as e:
                    logger.debug(f"Progress poll skipped: {e}")
                finally:
                    try:
                        next_position = (
                            slurmClient.wfProgress.recorder.max_tracking_id(
                                application_name='WorkflowTracker') or 0)
                    except Exception:
                        pass
            time.sleep(2)
        return proc.getResults(0), proc.getJob()
    finally:
        proc.close(False)


class WorkflowWorker(Thread):
    """Runs one queued workflow to completion, in the background."""

    def __init__(self, workflow_id, launcher_task_id, batched, supervisor):
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
        self.logger = logging.getLogger(f"biomero.detached.{workflow_id}")

    def run(self):
        self.logger.info(f"Executing queued workflow {self.workflow_id}")
        try:
            self.execute()
            self.logger.info(f"Finished workflow {self.workflow_id}")
        except Exception as e:
            self.logger.error(f"Workflow {self.workflow_id} failed: {e}",
                              exc_info=True)
            self.fail_workflow(str(e))
        finally:
            self.supervisor.remove_worker(self.workflow_id)

    def fail_workflow(self, error):
        """Record the failure, so the workflow does not sit unfinished."""
        try:
            from biomero.database import EngineManager
            from biomero.slurm_client import SlurmClient
            EngineManager.create_scoped_session()
            with SlurmClient.from_config() as slurmClient:
                slurmClient.workflowTracker.fail_workflow(
                    self.workflow_id, error)
        except Exception as e:
            self.logger.error(f"Could not record the failure of workflow "
                              f"{self.workflow_id}: {e}")

    def execute(self):
        """Find this workflow's launcher task and run what it asks for."""
        from biomero import detached
        from biomero.database import EngineManager
        from biomero.slurm_client import SlurmClient

        run_workflow_script, batched_script = load_biomero_scripts()
        EngineManager.create_scoped_session()

        with SlurmClient.from_config() as slurmClient:
            tracker = slurmClient.workflowTracker
            launcher = tracker.repository.get(self.launcher_task_id)
            if not detached.is_launcher_task(launcher):
                raise ValueError(f"Task {self.launcher_task_id} is not a "
                                 f"launcher for workflow {self.workflow_id}")
            if detached.is_claimed(launcher):
                # Left behind by a previous processor. The pipeline resumes
                # from what already happened, so pick it back up.
                self.logger.info(f"Workflow {self.workflow_id} was already "
                                 f"claimed; resuming it.")
            detached.claim_launcher_task(tracker, launcher.id)

            workflow = tracker.repository.get(self.workflow_id)
            params = launcher.params or {}
            with self.user_connection(workflow) as conn:
                client = RecordedInputsClient(params, conn)
                if self.batched:
                    self.run_batches(run_workflow_script, batched_script,
                                     slurmClient, client, conn, workflow,
                                     params)
                else:
                    self.run_single(run_workflow_script, slurmClient, client,
                                    conn, params)

    @contextlib.contextmanager
    def user_connection(self, workflow):
        """Connect to OMERO as the user whose workflow this is.

        The run has no session of its own, so the processor's own credentials
        are used to sudo into the requesting user's account and group. Results
        are then created and owned exactly as an inline run would create them.
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
            user = admin_conn.getObject("Experimenter", workflow.user)
            if not user:
                raise ValueError(f"No OMERO user with ID {workflow.user} for "
                                 f"workflow {self.workflow_id}")
            self.logger.info(f"Running as {user.getName()} in group "
                             f"{workflow.group}")
            # A day of leeway per session refresh; the runner keeps it alive
            # for as long as the run takes.
            with admin_conn.suConn(user.getName(), ttl=86400000) as user_conn:
                user_conn.keepAlive()
                user_conn.setGroupForSession(workflow.group)
                yield user_conn
        finally:
            admin_conn.close()

    def run_single(self, script, slurmClient, client, conn, params):
        """Drive the workflow pipeline, the same one an inline run drives."""
        pipeline_kwargs = script.resolve_pipeline_inputs(
            client, conn, slurmClient, params)
        self.logger.info(f"Running workflows {pipeline_kwargs['workflows']} "
                         f"for workflow {self.workflow_id}")
        messages = script.execute_workflow_pipeline(
            client, conn, slurmClient, self.workflow_id, resume=True,
            **pipeline_kwargs)
        self.logger.info(f"Workflow {self.workflow_id}: {messages}")

    def run_batches(self, script, batched_script, slurmClient, client, conn,
                    workflow, params):
        """Run a batched request as one child workflow per batch.

        Each child is queued exactly as a single run is, so it is executed by
        the same pipeline and reports its own progress. This parent only
        spawns the children it does not have yet and then follows them.
        """
        from biomero import constants, detached

        tracker = slurmClient.workflowTracker
        batches = [list(batch) for batch in (params.get("batches") or [])]
        if not batches:
            raise ValueError(f"Batched workflow {self.workflow_id} has no "
                             f"batches recorded")
        base_inputs = params.get("base_inputs") or {}
        effective_type = params.get("effective_type")
        self.logger.info(f"Batched workflow {self.workflow_id}: "
                         f"{len(batches)} batches")

        # One bookkeeping task per batch on this workflow, holding the child's
        # ID. Re-running this parent therefore adopts the children it already
        # has instead of starting the work again.
        children = {}
        for task_id in getattr(workflow, "tasks", []):
            try:
                task = tracker.repository.get(task_id)
            except Exception as e:
                self.logger.warning(f"Could not read task {task_id}: {e}")
                continue
            task_params = task.params or {}
            if "batch_index" in task_params and "child_workflow_id" in task_params:
                children[task_params["batch_index"]] = (
                    task_id, uuid.UUID(str(task_params["child_workflow_id"])))

        for index, batch in enumerate(batches):
            if index in children:
                continue
            child_params = dict(base_inputs)
            child_params[constants.transfer.IDS] = batch
            if effective_type:
                child_params[constants.transfer.DATA_TYPE] = effective_type
            # All batches share one output dataset or screen.
            child_params[constants.workflow.OUTPUT_DUPLICATES] = False
            child_params["selected_output"] = params.get("selected_output")
            child_params["group"] = params.get("group")
            child_wf_id = tracker.initiate_workflow(
                f"{workflow.name} (batch {index + 1}/{len(batches)})",
                "\n".join([workflow.description, script.VERSION]),
                workflow.user,
                workflow.group)
            detached.register_detached_launcher(
                RecordedInputsClient(child_params, conn), tracker,
                child_wf_id, constants.RUN_WF_SCRIPT, script.VERSION,
                params.get("workflows") or [], {})
            task_id = tracker.add_task_to_workflow(
                self.workflow_id, constants.RUN_WF_SCRIPT, script.VERSION,
                batch, {"batch_index": index,
                        "child_workflow_id": str(child_wf_id)})
            tracker.start_task(task_id)
            children[index] = (task_id, child_wf_id)
            self.logger.info(f"Queued batch {index + 1}/{len(batches)} as "
                             f"workflow {child_wf_id}")

        failed, pending = self.await_children(
            slurmClient, conn, batched_script, children, batches, base_inputs,
            effective_type)
        if pending:
            # Shutting down: leave the workflow unfinished so that the next
            # processor adopts the children it already has.
            self.logger.info(f"Stopped following {len(pending)} batches of "
                             f"workflow {self.workflow_id}; they will be "
                             f"picked up again.")
            return
        if failed:
            tracker.fail_workflow(self.workflow_id,
                                  f"{failed} of {len(batches)} batches failed")
        else:
            tracker.complete_workflow(self.workflow_id)

    def await_children(self, slurmClient, conn, batched_script, children,
                       batches, base_inputs, effective_type):
        """Follow the child workflows, annotating each batch as it lands.

        Returns:
            tuple: How many batches failed, and the batches still unfinished
                (non-empty only when we stopped following them early).
        """
        from biomero.constants import workflow_status as wfs
        from biomero.database import EngineManager, WorkflowProgressView

        tracker = slurmClient.workflowTracker
        pending = dict(children)
        failed = 0
        while pending and not self.supervisor.shutdown_event.is_set():
            with EngineManager.get_session() as session:
                statuses = {
                    row.workflow_id: row.status
                    for row in session.query(WorkflowProgressView).filter(
                        WorkflowProgressView.workflow_id.in_(
                            [child_wf_id for _, child_wf_id
                             in pending.values()])).all()}
            for index, (task_id, child_wf_id) in list(pending.items()):
                status = statuses.get(child_wf_id)
                if status == wfs.DONE:
                    tracker.complete_task(task_id, "Batch completed.")
                    del pending[index]
                    try:
                        batched_script.add_batch_supervisor_metadata_for_batch(
                            conn, slurmClient, self.workflow_id, index,
                            batches[index], len(batches), base_inputs,
                            effective_type)
                    except Exception as e:
                        self.logger.warning(
                            f"Could not annotate batch {index + 1}: {e}")
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


class WorkflowSupervisor(Thread):
    """Finds queued workflows and runs each of them in a worker thread."""

    def __init__(self):
        super(WorkflowSupervisor, self).__init__(name="WorkflowSupervisor")
        self.daemon = True
        self.shutdown_event = Event()
        self.active_workers = {}  # {workflow_id: worker}
        self.ignored = set()      # workflows that are not ours to run
        self.tracker = None
        self.lock = Lock()
        self.logger = logging.getLogger("biomero.detached.supervisor")

    def run(self):
        self.logger.info("Starting the BIOMERO workflow supervisor")
        try:
            from biomero import detached
            from biomero.database import EngineManager
            run_workflow_script, _ = load_biomero_scripts()
            EngineManager.create_scoped_session()
            self.tracker = detached.workflow_tracker()
            # Sub-scripts cannot be waited on with a script callback here, so
            # the workflow scripts use our polling runner instead.
            run_workflow_script.SCRIPT_RUNNER = polling_script_runner
        except Exception as e:
            self.logger.error(f"Cannot supervise workflows: {e}", exc_info=True)
            return

        polls = 0
        while not self.shutdown_event.is_set():
            try:
                self.prune_workers()
                if polls % IGNORE_CACHE_POLLS == 0:
                    with self.lock:
                        self.ignored.clear()
                self.spawn_workers()
            except Exception as e:
                self.logger.error(f"Supervisor poll failed: {e}", exc_info=True)
            polls += 1
            self.shutdown_event.wait(SUPERVISOR_POLL_SECONDS)
        self.logger.info("Workflow supervisor shutting down")

    def unfinished_workflows(self):
        """Every workflow that has not reached a final state.

        The task execution view does not record which workflow a task belongs
        to, so candidates cannot be narrowed down to queued runs in SQL; that
        is what the launcher lookup below is for.
        """
        from biomero.constants import workflow_status as wfs
        from biomero.database import EngineManager, WorkflowProgressView

        with EngineManager.get_session() as session:
            rows = session.query(WorkflowProgressView.workflow_id).filter(
                WorkflowProgressView.status.notin_(
                    [wfs.DONE, wfs.FAILED])).all()
            return [row.workflow_id for row in rows]

    def spawn_workers(self):
        """Start a worker for each queued workflow that has none yet."""
        from biomero import constants, detached

        for wf_id in self.unfinished_workflows():
            with self.lock:
                if wf_id in self.active_workers or wf_id in self.ignored:
                    continue
                busy = sum(1 for worker in self.active_workers.values()
                           if worker.holds_slot)
            if busy >= MAX_ACTIVE_WORKFLOWS:
                self.logger.debug(
                    f"Running {busy} workflows already; {wf_id} waits.")
                return
            launcher = detached.find_launcher_task(self.tracker, wf_id)
            if launcher is None:
                # Started by a script that runs its own pipeline, so it is not
                # ours to run. Remembered until the cache is next dropped.
                self.logger.debug(f"Workflow {wf_id} was not queued for us; "
                                  f"leaving it alone.")
                self.ignore(wf_id)
                continue
            batched = launcher.task_name == constants.RUN_WF_BATCHED_SCRIPT
            with self.lock:
                if wf_id in self.active_workers:
                    continue
                worker = WorkflowWorker(wf_id, launcher.id, batched, self)
                self.active_workers[wf_id] = worker
            worker.start()

    def prune_workers(self):
        with self.lock:
            for wf_id, worker in list(self.active_workers.items()):
                if not worker.is_alive():
                    self.active_workers.pop(wf_id)

    def remove_worker(self, wf_id):
        with self.lock:
            self.active_workers.pop(wf_id, None)

    def ignore(self, wf_id):
        """Stop inspecting a workflow that is not ours to run."""
        with self.lock:
            self.ignored.add(wf_id)

    def stop(self):
        self.shutdown_event.set()


class ProcessorI(omero.grid.Processor, omero.util.Servant):

    def __init__(self, ctx, needs_session=True, use_session=None,
                 accepts_list=None, cfg=None, omero_home=path.getcwd(),
                 category=None):

        # Run queued BIOMERO workflows alongside this processor, if this
        # deployment asked for detached runs and has a biomero that supports
        # them. Never let that stop the processor itself from starting.
        self.supervisor = None
        try:
            from biomero import detached
            if detached.detached_mode_enabled():
                self.supervisor = WorkflowSupervisor()
                self.supervisor.start()
            else:
                biomero_logger.info(
                    "BIOMERO_DETACHED_WORKFLOWS is not enabled; workflows "
                    "run inside the calling session.")
        except ImportError:
            biomero_logger.info("No biomero with detached support installed; "
                                "not supervising workflows.")
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