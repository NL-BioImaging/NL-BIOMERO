# Targeted SSH integration probes

These probes complement the site's normal workflow/import smoke tests. They
exercise published BIOMERO code through private SSH connections; they are not
installed by the production images. Run them only in an isolated acceptance
deployment against allocations and data owned by that test.

| Entry point | Evidence supplied | Not established by this probe |
| --- | --- | --- |
| `check_monitor.py` | Silent channel-open fault, bounded observation, recovery timeout and callback count | Full workflow, OMERO heartbeat success or a universal bound on all SSH phases |
| `check_allocation.py` | A fixture is RUNNING before the private outage; the same allocation completes, its exact result downloads, and accounting contains one allocation | Image analysis, ZIP recovery or OMERO import |
| `workflow_hook.py` | A private relay interrupts monitoring of one supplied workflow/task/job while RUNNING, with the real pipeline's recovery state and callbacks | Final workflow/import outcome; the selected execution mode must be corroborated separately |
| `audit_workflow.py` | Persisted workflow/task membership and one matching Slurm allocation | Exactly-once import, mandatory provenance or tracking/projection consistency |

The relay stops forwarding without dropping queued TCP bytes. It never changes a
firewall, kills an SSH daemon, or pauses a container. Authentication comes from
the existing runtime configuration, not command-line passwords. The private
proxy pins the host key from the established connection and rejects unknown
keys. Standalone connections require the target in the configured known-hosts
store; the probes do not add keys to known-hosts files. Gateways are deliberately
unsupported by the relay: provide a reviewed site adapter rather than bypassing
a configured gateway.

## Prerequisites and scope

- Use the candidate's Python environment with BIOMERO, Fabric and Paramiko.
  `audit_workflow.py` also needs the existing acceptance tracking configuration.
  Live probes refuse optimized Python (`-O`/`PYTHONOPTIMIZE`), because acceptance
  assertions must remain enabled.
- Supply site paths, credentials and SSH configuration through the deployment's
  normal configuration. `--config-file` is optional; an existing
  `BIOMERO_SLURM_CONFIG_FILE` environment value retains authoritative precedence.
- Each live fault requires `--enable-faults`. Installing or arming the workflow
  hook also requires `--ack-isolated-worker`. Help and `--dry-run` make no SSH
  connection and do not import BIOMERO or modify files.
- Evidence directories must already exist and be private. Standalone probes
  refuse an existing output file. Keep all runtime reports/control files outside
  the repository. Publish only reviewed structured reports, never configuration,
  environment dumps, raw activity logs, subprocess output or tracebacks.
- The default **0.5-second channel timeout is a test-only override on the private
  proxy**. Record the candidate's unmodified production settings separately.
  Native detection time and the subsequent recovery window are different bounds.
- The allocation fixture creates one new child directory under `--remote-parent`,
  submits one bounded sleep/result job, and retains its remote evidence. Failure
  cleanup may cancel **only that generated job ID**. It never retries submission.
- The workflow hook changes no mode or recovery setting. A site adapter selects
  inline/detached mode, saves any temporary setting changes, and restores them
  afterward. The hook's `mode` field is the requested test label, not independent
  proof of which processor executed the workflow.
- The audit uses the normal configured client with `init_slurm=False`, because
  a config-only client has no tracker. Initialization may create missing tracking
  tables; subsequent queries are read-only. Use the existing isolated acceptance
  event store. It never resets tables, catches up projections, repairs tracking,
  or changes workflow events. The client's normal context closes its sessions.

## Docker Compose execution

NL-BIOMERO's examples use Docker Compose. Set `TEST_PROJECT` to your isolated
project, `BUNDLE_PARENT` to an existing directory in its worker, `CONTROL_DIR` to
a new private worker directory, and `EVIDENCE_DIR` to an existing private worker
directory. `WORKER_UID`/`WORKER_GID` must identify the actual script user.

```sh
docker compose -p "$TEST_PROJECT" cp scripts/acceptance/ssh "biomeroworker:$BUNDLE_PARENT"
BUNDLE_IN_WORKER="$BUNDLE_PARENT/ssh"
docker compose -p "$TEST_PROJECT" exec -T biomeroworker \
  python "$BUNDLE_IN_WORKER/check_monitor.py" --help
```

ACC uses Podman: translate only the surrounding `exec`/copy/restart commands to
its established Podman deployment adapter. The Python test logic is unchanged;
there is no container-engine abstraction in this bundle.

### Shared monitor boundary and original allocation

`JOB_ID` below must be an existing owned integration allocation, normally one
already completed. The first command does not submit or cancel anything.

```sh
docker compose -p "$TEST_PROJECT" exec -T --user "$WORKER_UID:$WORKER_GID" biomeroworker \
  python "$BUNDLE_IN_WORKER/check_monitor.py" --job-id "$JOB_ID" \
  --output "$EVIDENCE_DIR/monitor.json" --enable-faults

docker compose -p "$TEST_PROJECT" exec -T --user "$WORKER_UID:$WORKER_GID" biomeroworker \
  python "$BUNDLE_IN_WORKER/check_allocation.py" --remote-parent "$REMOTE_TEST_PARENT" \
  --output "$EVIDENCE_DIR/allocation.json" --enable-faults
```

Exit 0 means that probe's assertions passed; 2 means failure, and 130 means it
was interrupted. Reports contain IDs, booleans, timings and error classes.
Underlying exception messages, commands, remote output and configuration are
suppressed. Relay sockets/timers are closed in `finally` paths. Standalone
callback counts do **not** prove an OMERO heartbeat succeeded.

### Actual inline and detached workflows

Install once in the isolated worker before launching either test. The temporary
`.pth` hook registers a dormant wrapper even before the control file/IDs exist.
It affects new Python processes in that worker environment only. Installation
refuses existing hook/control paths; it does not overwrite a previous setup.

```sh
docker compose -p "$TEST_PROJECT" exec -T --user 0 biomeroworker \
  python "$BUNDLE_IN_WORKER/workflow_hook.py" install --control-dir "$CONTROL_DIR" \
  --owner-uid "$WORKER_UID" --owner-gid "$WORKER_GID" \
  --enable-faults --ack-isolated-worker
docker compose -p "$TEST_PROJECT" restart biomeroworker
```

For **each mode**, use the site's normal smoke launcher/UI to start one dedicated
workflow. It must stay RUNNING long enough to discover its workflow UUID, analysis
task UUID and Slurm ID, then arm the next monitor call. A fixture-only delay before
the ordinary workflow command is acceptable: record that adaptation and restore
its job script afterward. Do not change production component code or slow a
shared job. A completed job cannot satisfy this test.

```sh
docker compose -p "$TEST_PROJECT" exec -T --user "$WORKER_UID:$WORKER_GID" biomeroworker \
  python "$BUNDLE_IN_WORKER/workflow_hook.py" arm --control-dir "$CONTROL_DIR" \
  --mode "$EXECUTION_MODE" --workflow-id "$WORKFLOW_ID" --task-id "$TASK_ID" --job-id "$JOB_ID" \
  --expect recovered --pause-seconds 2 --detection-timeout .5 \
  --enable-faults --ack-isolated-worker

docker compose -p "$TEST_PROJECT" exec -T --user "$WORKER_UID:$WORKER_GID" biomeroworker \
  python "$BUNDLE_IN_WORKER/workflow_hook.py" status --control-dir "$CONTROL_DIR"
```

Set `EXECUTION_MODE` to `inline` or `detached` to match the actual launch. The
hook verifies exact persisted workflow/task/job membership, a positive recovery
scope and registered callbacks; it checks RUNNING again on its private connection
before pausing. It never faults a different job or a multi-job monitor request.
One exclusive claim prevents repeated faults for the same armed case.

Status exit 3 means not yet armed/observed, not a pass. Exit 0 means the **monitor
phase** matched `--expect`, callbacks succeeded more than once, and cleanup was
recorded. An explicit `False` from a heartbeat (such as OMERO `keepAlive`) is
recorded as failure and prevents a phase pass; the callback's original return
value or exception is preserved. An arbitrary exception cannot pass a timeout case. `--expect timeout`
requires a deliberately short positive window in the isolated deployment and a
pause exceeding that window plus detection/retry overhead. The pipeline's native
timeout/cancellation exception propagates unchanged; terminal state is not reset.

After the normal workflow finishes, run the identity audit and the site's existing
checks for one import, mandatory provenance, usable results, final outcome and
OMERO session health. Hook callback success alone is not that acceptance verdict.

```sh
docker compose -p "$TEST_PROJECT" exec -T --user "$WORKER_UID:$WORKER_GID" biomeroworker \
  python "$BUNDLE_IN_WORKER/audit_workflow.py" --workflow-id "$WORKFLOW_ID" \
  --task-id "$TASK_ID" --job-id "$JOB_ID" --output "$EVIDENCE_DIR/identity.json"
docker compose -p "$TEST_PROJECT" exec -T --user "$WORKER_UID:$WORKER_GID" biomeroworker \
  python "$BUNDLE_IN_WORKER/workflow_hook.py" disarm --control-dir "$CONTROL_DIR"
```

Disarm between cases. In an operator `finally`/shell trap, disarm and uninstall;
the latter removes only the exact generated `.pth` content and retains reports.
Do not reuse a control directory with another installation. After both modes,
restore the site's mode/recovery settings and any fixture script, uninstall, then
restart only the isolated worker and run a clean ordinary workflow.

```sh
docker compose -p "$TEST_PROJECT" exec -T --user 0 biomeroworker \
  python "$BUNDLE_IN_WORKER/workflow_hook.py" uninstall --control-dir "$CONTROL_DIR"
docker compose -p "$TEST_PROJECT" restart biomeroworker
```

## Coverage limits and source provenance

The original private helpers and their hashes are recorded in
`SOURCE_PROVENANCE.json`; no original runtime logs/configuration/reports are
included. Record `git rev-parse HEAD` alongside each new acceptance result so the
executed bundle commit is unambiguous, including after a coordinator cherry-pick.

The original workflow hook could claim already-completed allocations; this
adaptation deliberately rejects that case. Fresh published-candidate live runs
are required. Offline checks do not replace them.

This bundle does **not** supply submission-response-loss, ZIP interruption,
zero-window/permanent-error, processor restart/cancellation, converter/image-init
or full import/provenance fixtures. Those require the site's existing phase
adapters and separate assertions. Do not mark those acceptance criteria complete
from these reports. No complete worker-restart test is claimed.

Offline validation (installed core required for the real temporary-SQLite tracker
test; only SSH validation/descriptor lookup are replaced there):

```sh
python -m unittest discover -s scripts/acceptance/ssh/tests -v
python -m compileall -q scripts/acceptance/ssh
```
