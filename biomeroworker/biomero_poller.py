#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time
import logging
import omero
from uuid import UUID
from typing import Dict, Any, List
from omero.gateway import BlitzGateway
from omero.rtypes import rstring, rbool, rlist, rlong, unwrap, wrap
from omero.sys import Parameters

# Add OMERO python libraries to path if needed (though they should be in PYTHONPATH)
from biomero import SlurmClient, constants
from biomero.database import EngineManager, TaskExecution, JobView, JobProgressView

# Configure logger
logger = logging.getLogger("biomero.poller")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] (%(name)s) %(message)s")

# Log to stdout and a file
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(formatter)
logger.addHandler(stdout_handler)

log_dir = "/opt/omero/server/OMERO.server/var/log"
if os.path.exists(log_dir):
    file_handler = logging.FileHandler(os.path.join(log_dir, "biomero_poller.log"))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

# Silence noisy loggers
logging.getLogger('omero.gateway').setLevel(logging.WARNING)
logging.getLogger('omero.client').setLevel(logging.WARNING)
logging.getLogger('paramiko').setLevel(logging.WARNING)

# Check if importer is enabled via environment variable
IMPORTER_ENABLED = os.getenv("IMPORTER_ENABLED", "false").lower() == "true"
if IMPORTER_ENABLED:
    IMPORT_SCRIPTS = ["SLURM_Import_Results.py"]
else:
    IMPORT_SCRIPTS = ["SLURM_Get_Results.py"]


def get_admin_connection() -> BlitzGateway:
    omero_host = os.getenv("CONFIG_omero_master_host", "omeroserver")
    omero_port = int(os.getenv("OMERO_PORT", "4064"))
    omero_user = os.getenv("OMERO_USER", "root")
    omero_password = os.getenv("OMERO_PASSWORD", "omero")

    client = omero.client(host=omero_host, port=omero_port)
    client.createSession(omero_user, omero_password)
    conn = BlitzGateway(client_obj=client)
    return conn


def get_project_name_ids(conn, parent_id):
    return [rstring('%d: %s' % (d.id, d.getName()))
            for d in conn.getObjects(constants.transfer.DATA_TYPE_PROJECT,
                                     opts={'dataset': parent_id})]


def get_dataset_name_ids(conn, parent_id):
    return [rstring('%d: %s' % (d.id, d.getName()))
            for d in conn.getObjects(constants.transfer.DATA_TYPE_DATASET,
                                     [parent_id])]


def get_plate_name_ids(conn, parent_id):
    return [rstring('%d: %s' % (d.id, d.getName()))
            for d in conn.getObjects(constants.transfer.DATA_TYPE_PLATE,
                                     [parent_id])]


def run_omero_script(conn, svc, script_id, inputs, slurmClient=None):
    proc = svc.runScript(script_id, inputs, None)
    try:
        cb = omero.scripts.ProcessCallbackI(conn.c, proc)
        next_position = 1
        if slurmClient is not None and slurmClient.wfProgress is not None:
            try:
                next_position = slurmClient.wfProgress.recorder.max_tracking_id(
                    application_name='WorkflowTracker'
                ) + 1
            except Exception:
                next_position = 1
        while not cb.block(1000):  # ms
            if slurmClient is not None and slurmClient.wfProgress is not None:
                try:
                    slurmClient.bring_listener_uptodate(
                        slurmClient.wfProgress, start=next_position
                    )
                except Exception as e:
                    logger.debug(f"wfProgress poll skipped: {e}")
                finally:
                    try:
                        new_position = slurmClient.wfProgress.recorder.max_tracking_id(
                            application_name='WorkflowTracker'
                        ) + 1
                        next_position = new_position
                    except Exception:
                        pass
        cb.close()
        rv = proc.getResults(0)
        job = proc.getJob()
    finally:
        proc.close(False)
    return rv, job


def upload_job_log_to_omero(conn, user_conn, slurmClient, slurm_job_id, wf_id):
    try:
        if slurm_job_id is None or int(slurm_job_id) < 0:
            return ""
        _, local_path, _ = slurmClient.get_logfile_from_slurm(str(slurm_job_id))
        mimetype = "text/plain"
        namespace = omero.constants.namespaces.NSCREATED + "/SLURM/SLURM_RUN_WORKFLOW"
        description = f"Log from SLURM job {slurm_job_id} (Workflow {wf_id})"
        
        annotation = user_conn.createFileAnnfromLocalFile(
            local_path, mimetype=mimetype, ns=namespace, desc=description)
        obj_id = annotation.getFile().getId()
        logger.info(f"Uploaded log for failed job {slurm_job_id} to OMERO (file {obj_id})")
        return f" Uploaded log for SLURM job {slurm_job_id}."
    except Exception as e:
        logger.warning(f"Failed to upload job log {slurm_job_id} to OMERO: {e}")
        return f" (failed to upload log for job {slurm_job_id}: {e})"


def import_results(conn, slurmClient, slurm_job_id, user_id, group_id, wf_id, output_settings):
    # impersonate user
    user_obj = conn.getObject("Experimenter", user_id)
    username = user_obj.getName()
    
    logger.info(f"Impersonating user {username} for import of job {slurm_job_id} in group {group_id}")
    user_conn = conn.suConn(username)
    user_conn.SERVICE_OPTS.setOmeroGroup(group_id)
    
    svc = user_conn.getScriptService()
    scripts = svc.getScripts()
    
    script_matches = [s for s in scripts if s.name.val in IMPORT_SCRIPTS]
    if not script_matches:
        raise RuntimeError(f"Import script not found: {IMPORT_SCRIPTS}")
        
    script_id = script_matches[0].id.val
    script_name = script_matches[0].name.val
    
    first_id = output_settings["IDS"][0]
    data_type = output_settings["DATA_TYPE"]
    
    inputs = {
        constants.results.OUTPUT_COMPLETED_JOB: rbool(True),
        constants.results.OUTPUT_SLURM_JOB_ID: rstring(str(slurm_job_id)),
        constants.CLEANUP: rbool(output_settings.get("CLEANUP", True)),
        constants.results.WORKFLOW_UUID: rstring(str(wf_id))
    }
    
    # Get a 'parent' dataset or plate of input images
    parent_id = first_id
    parent_data_type = data_type
    if data_type == constants.transfer.DATA_TYPE_IMAGE:
        q = user_conn.getQueryService()
        params = Parameters()
        params.map = {"image_id": rlong(first_id)}
        resultPlates = q.projection(
            "SELECT DISTINCT p.id FROM Plate p "
            " JOIN p.wells w "
            " JOIN w.wellSamples ws "
            " JOIN ws.image i "
            " WHERE i.id = :image_id",
            params,
            user_conn.SERVICE_OPTS
        )
        resultDatasets = q.projection(
            "SELECT DISTINCT d.id FROM Dataset d "
            " JOIN d.imageLinks dil "
            " JOIN dil.child i "
            " WHERE i.id = :image_id",
            params,
            user_conn.SERVICE_OPTS
        )
        if len(resultPlates) > len(resultDatasets):
            parent_id = resultPlates[0][0]
            parent_data_type = constants.transfer.DATA_TYPE_PLATE
        else:
            parent_id = resultDatasets[0][0]
            parent_data_type = constants.transfer.DATA_TYPE_DATASET
            
    _fallback_parent_id = unwrap(parent_id)
    inputs[constants.results.LOG_FALLBACK_TARGET] = rstring(
        f"{parent_data_type}:{_fallback_parent_id}")
        
    if output_settings.get("OUTPUT_PARENT"):
        if parent_data_type in (constants.transfer.DATA_TYPE_DATASET, constants.transfer.DATA_TYPE_PROJECT):
            projects = get_project_name_ids(user_conn, parent_id)
            if projects:
                inputs[constants.results.OUTPUT_ATTACH_PROJECT] = rbool(True)
                inputs[constants.results.OUTPUT_ATTACH_PROJECT_ID] = rlist(projects)
                inputs[constants.results.OUTPUT_ATTACH_DATASET] = rbool(False)
            else:
                datasets = get_dataset_name_ids(user_conn, parent_id)
                inputs[constants.results.OUTPUT_ATTACH_PROJECT] = rbool(False)
                inputs[constants.results.OUTPUT_ATTACH_DATASET] = rbool(True)
                inputs[constants.results.OUTPUT_ATTACH_DATASET_ID] = rlist(datasets)
            inputs[constants.results.OUTPUT_ATTACH_PLATE] = rbool(False)
        elif parent_data_type == constants.transfer.DATA_TYPE_PLATE:
            plates = get_plate_name_ids(user_conn, parent_id)
            inputs[constants.results.OUTPUT_ATTACH_PROJECT] = rbool(False)
            inputs[constants.results.OUTPUT_ATTACH_PLATE] = rbool(True)
            inputs[constants.results.OUTPUT_ATTACH_PLATE_ID] = rlist(plates)
    else:
        inputs[constants.results.OUTPUT_ATTACH_PROJECT] = rbool(False)
        inputs[constants.results.OUTPUT_ATTACH_PLATE] = rbool(False)

    if output_settings.get("OUTPUT_RENAME") and output_settings.get("OUTPUT_RENAME") != constants.workflow.NO:
        inputs[constants.results.OUTPUT_ATTACH_NEW_DATASET_RENAME] = rbool(True)
        inputs[constants.results.OUTPUT_ATTACH_NEW_DATASET_RENAME_NAME] = rstring(output_settings["OUTPUT_RENAME"])
    else:
        inputs[constants.results.OUTPUT_ATTACH_NEW_DATASET_RENAME] = rbool(False)
        
    if output_settings.get("OUTPUT_NEW_DATASET") and output_settings.get("OUTPUT_NEW_DATASET") != constants.workflow.NO:
        inputs[constants.results.OUTPUT_ATTACH_NEW_DATASET] = rbool(True)
        inputs[constants.results.OUTPUT_ATTACH_NEW_DATASET_NAME] = rstring(output_settings["OUTPUT_NEW_DATASET"])
        inputs[constants.results.OUTPUT_ATTACH_NEW_DATASET_DUPLICATE] = rbool(output_settings.get("OUTPUT_DUPLICATES", False))
        if output_settings.get("OUTPUT_ATTACH_NEW_DATASET_ID") is not None:
            inputs[constants.results.OUTPUT_ATTACH_NEW_DATASET_ID] = rlong(output_settings["OUTPUT_ATTACH_NEW_DATASET_ID"])
    else:
        inputs[constants.results.OUTPUT_ATTACH_NEW_DATASET] = rbool(False)

    if output_settings.get("OUTPUT_NEW_SCREEN") and output_settings.get("OUTPUT_NEW_SCREEN") != constants.workflow.NO:
        inputs[constants.results.OUTPUT_ATTACH_NEW_SCREEN] = rbool(True)
        inputs[constants.results.OUTPUT_ATTACH_NEW_SCREEN_NAME] = rstring(output_settings["OUTPUT_NEW_SCREEN"])
        inputs[constants.results.OUTPUT_ATTACH_NEW_SCREEN_DUPLICATE] = rbool(output_settings.get("OUTPUT_DUPLICATES", False))
        if output_settings.get("OUTPUT_ATTACH_NEW_SCREEN_ID") is not None:
            inputs[constants.results.OUTPUT_ATTACH_NEW_SCREEN_ID] = rlong(output_settings["OUTPUT_ATTACH_NEW_SCREEN_ID"])
    else:
        inputs[constants.results.OUTPUT_ATTACH_NEW_SCREEN] = rbool(False)

    if output_settings.get("OUTPUT_ATTACH"):
        inputs[constants.results.OUTPUT_ATTACH_OG_IMAGES] = rbool(True)
    else:
        inputs[constants.results.OUTPUT_ATTACH_OG_IMAGES] = rbool(False)

    if output_settings.get("OUTPUT_CSV_TABLE"):
        inputs[constants.results.OUTPUT_ATTACH_TABLE] = rbool(True)
        if parent_data_type == constants.transfer.DATA_TYPE_DATASET:
            inputs[constants.results.OUTPUT_ATTACH_TABLE_DATASET] = rbool(True)
            inputs[constants.results.OUTPUT_ATTACH_TABLE_DATASET_ID] = rlist(get_dataset_name_ids(user_conn, parent_id))
        else:
            inputs[constants.results.OUTPUT_ATTACH_TABLE_DATASET] = rbool(False)
        if parent_data_type == constants.transfer.DATA_TYPE_PLATE:
            inputs[constants.results.OUTPUT_ATTACH_TABLE_PLATE] = rbool(True)
            inputs[constants.results.OUTPUT_ATTACH_TABLE_PLATE_ID] = rlist(get_plate_name_ids(user_conn, parent_id))
        else:
            inputs[constants.results.OUTPUT_ATTACH_TABLE_PLATE] = rbool(False)
    else:
        inputs[constants.results.OUTPUT_ATTACH_TABLE] = rbool(False)

    inputs[constants.results.IMPORT_LABEL_ZARRS] = rbool(True)
    inputs[constants.results.IMPORT_ONLY_LABELS] = rbool(True)
    inputs[constants.results.TEST_WRITE_PERMISSIONS_ONLY] = rbool(False)

    if output_settings.get("OUTPUT_ATTACH_FILE_OUTPUTS"):
        inputs[constants.results.OUTPUT_ATTACH_FILE_OUTPUTS] = rbool(True)
        if parent_data_type == constants.transfer.DATA_TYPE_DATASET:
            inputs[constants.results.OUTPUT_ATTACH_FILE_OUTPUTS_DATASET] = rbool(True)
            inputs[constants.results.OUTPUT_ATTACH_FILE_OUTPUTS_DATASET_ID] = rlist(get_dataset_name_ids(user_conn, parent_id))
        else:
            inputs[constants.results.OUTPUT_ATTACH_FILE_OUTPUTS_DATASET] = rbool(False)
        if parent_data_type == constants.transfer.DATA_TYPE_PLATE:
            inputs[constants.results.OUTPUT_ATTACH_FILE_OUTPUTS_PLATE] = rbool(True)
            inputs[constants.results.OUTPUT_ATTACH_FILE_OUTPUTS_PLATE_ID] = rlist(get_plate_name_ids(user_conn, parent_id))
        else:
            inputs[constants.results.OUTPUT_ATTACH_FILE_OUTPUTS_PLATE] = rbool(False)
    else:
        inputs[constants.results.OUTPUT_ATTACH_FILE_OUTPUTS] = rbool(False)

    # Wait for Slurm Accounting to update (max 5 minutes)
    start_time = time.time()
    while str(slurm_job_id) not in slurmClient.list_completed_jobs():
        if time.time() - start_time > 300:
            logger.warning(f"Slurm job {slurm_job_id} not in accounting after 5 minutes, proceeding anyway")
            break
        time.sleep(15)

    logger.info(f"Running import script {script_name} ({script_id}) with inputs: {inputs}")
    
    # Track task
    task_id = slurmClient.workflowTracker.add_task_to_workflow(
        wf_id,
        script_name,
        "2.8.0",
        {"IDs": output_settings["IDS"]},
        {k: unwrap(v) for k, v in inputs.items()}
    )
    inputs["Task_ID"] = rstring(str(task_id))
    slurmClient.workflowTracker.start_task(task_id)
    
    # Run the import script
    rv, job = run_omero_script(user_conn, svc, script_id, inputs, slurmClient=slurmClient)
    
    job_status_id = None
    script_failed = False
    if job:
        try:
            job_status = job.getStatus()
            job_status_id = unwrap(job_status.getId())
            script_failed = job_status_id in (6, 9)  # Error (6) or Cancel (9)
        except Exception as e:
            logger.warning(f"Could not get import job status: {e}")
            script_failed = True
            
    try:
        msg = unwrap(rv['Message'])
        msg_str = str(msg) if msg is not None else ""
        message_failed = msg_str.startswith("FAILED:")
        if script_failed or message_failed:
            logger.error(f"Import script failed (status={job_status_id}): {msg_str}")
            slurmClient.workflowTracker.fail_task(task_id, f"Import failed: {msg_str}")
            raise RuntimeError(f"Import failed: {msg_str}")
        else:
            logger.info(f"Import script succeeded: {msg_str}")
            slurmClient.workflowTracker.complete_task(task_id, msg_str)
    except KeyError:
        error_msg = "No message returned from import script"
        logger.error(error_msg)
        slurmClient.workflowTracker.fail_task(task_id, error_msg)
        raise RuntimeError(error_msg)
        
    finally:
        user_conn.close()


def poll_loop():
    logger.info("Starting BIOMERO SLURM poller loop...")
    
    with SlurmClient.from_config() as slurmClient:
        while True:
            try:
                # Retrieve active runs from db
                session = EngineManager.get_session()
                active_runs = session.query(JobView, TaskExecution).join(
                    TaskExecution, JobView.task_id == TaskExecution.task_id
                ).filter(
                    TaskExecution.status.in_(['RUNNING', 'PENDING'])
                ).all()
                
                job_ids = [run.JobView.slurm_job_id for run in active_runs]
                
                if job_ids:
                    logger.info(f"Checking status for active SLURM jobs: {job_ids}")
                    job_status_dict, poll_result = slurmClient.check_job_status(job_ids)
                    
                    if not poll_result.ok:
                        logger.warning(f"Error checking job status: {poll_result.stderr}")
                        time.sleep(30)
                        continue
                        
                    # Process each job status
                    conn = None
                    try:
                        for run in active_runs:
                            job_id = run.JobView.slurm_job_id
                            task_id = run.TaskExecution.task_id
                            task = slurmClient.workflowTracker.repository.get(task_id)
                            wf_id = task.workflow_id
                            user_id = run.JobView.user
                            group_id = run.JobView.group
                            
                            job_state = job_status_dict.get(job_id)
                            if not job_state:
                                logger.warning(f"Job {job_id} not found in SLURM status dict")
                                continue
                                
                            progress = slurmClient.get_active_job_progress(job_id)
                            logger.info(f"Job {job_id} status is {job_state}, progress: {progress}")
                            
                            # Update status in db
                            slurmClient.workflowTracker.update_task_status(task_id, job_state)
                            slurmClient.workflowTracker.update_task_progress(task_id, progress)
                            
                            if job_state == "COMPLETED":
                                logger.info(f"Job {job_id} is COMPLETED. Starting results import.")
                                if conn is None:
                                    conn = get_admin_connection()
                                    
                                # Retrieve task details to get output settings
                                task = slurmClient.workflowTracker.repository.get(task_id)
                                output_settings = task.params.get("output_settings")
                                
                                if not output_settings:
                                    logger.error(f"No output_settings found for task {task_id}! Skipping import.")
                                    slurmClient.workflowTracker.fail_task(task_id, "No output settings found")
                                    slurmClient.workflowTracker.fail_workflow(wf_id, "Import failed: no output settings")
                                    continue
                                    
                                try:
                                    import_results(conn, slurmClient, job_id, user_id, group_id, wf_id, output_settings)
                                    slurmClient.workflowTracker.complete_workflow(wf_id)
                                    logger.info(f"Workflow {wf_id} completed successfully.")
                                except Exception as import_error:
                                    logger.error(f"Error importing results for job {job_id}: {import_error}")
                                    slurmClient.workflowTracker.fail_workflow(wf_id, f"Import failed: {import_error}")
                                    
                            elif job_state in ("FAILED", "TIMEOUT") or job_state.startswith("CANCELLED"):
                                logger.warning(f"Job {job_id} failed with state {job_state}.")
                                slurmClient.workflowTracker.fail_task(task_id, f"Slurm job state {job_state}")
                                slurmClient.workflowTracker.fail_workflow(wf_id, f"Slurm job failed: {job_state}")
                                
                                # Upload failed job log to OMERO
                                if conn is None:
                                    conn = get_admin_connection()
                                try:
                                    user_obj = conn.getObject("Experimenter", user_id)
                                    username = user_obj.getName()
                                    user_conn = conn.suConn(username)
                                    user_conn.SERVICE_OPTS.setOmeroGroup(group_id)
                                    upload_job_log_to_omero(conn, user_conn, slurmClient, job_id, wf_id)
                                    user_conn.close()
                                except Exception as log_error:
                                    logger.error(f"Failed to upload log for failed job {job_id}: {log_error}")
                                    
                    finally:
                        if conn:
                            conn.close()
                            
            except Exception as e:
                logger.error(f"Error in poller loop: {e}", exc_info=True)
                
            time.sleep(30)


if __name__ == '__main__':
    # Initialize database tables and run polling loop
    try:
        poll_loop()
    except Exception as ex:
        logger.critical(f"Poller crashed: {ex}", exc_info=True)
        sys.exit(1)
