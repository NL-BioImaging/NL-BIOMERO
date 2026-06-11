'''Post-process a freshly cloned BIOMERO Slurm script repository.

This file is kept as normal Python so Ruff and editors can parse it. During the
worker image build, ``patch_biomero_runtime.py`` renders concrete values into
``CONVERT_JOB_ARRAY`` and ``GENERATED_JOBS`` and embeds the result in a heredoc
that BIOMERO executes on the Slurm login node after ``git clone``.

Keep this self-contained and conservative: it runs with the remote ``python3``,
not the container venv used by the BIOMERO worker.
'''

from pathlib import Path
import re
import sys


CONVERT_JOB_ARRAY = ""
GENERATED_JOBS = {}


def _insert_env_loader(source: str) -> str:
    if "BIOMERO_ENV_FILE" in source:
        return source

    env_loader = (
        "\n"
        'BIOMERO_ENV_FILE="${1:-}"\n'
        'if [ -n "$BIOMERO_ENV_FILE" ] && [ -f "$BIOMERO_ENV_FILE" ]; then\n'
        '    . "$BIOMERO_ENV_FILE"\n'
        "fi\n"
    )
    lines = source.splitlines(keepends=True)
    insert_at = 0
    for idx, line in enumerate(lines):
        if line.startswith("#SBATCH"):
            insert_at = idx + 1
    lines.insert(insert_at, env_loader)
    return "".join(lines)


def _insert_strict_mode(source: str) -> str:
    if "set -eo pipefail" in source:
        return source

    lines = source.splitlines(keepends=True)
    insert_at = 1 if lines and lines[0].startswith("#!") else 0
    for idx, line in enumerate(lines):
        if line.startswith("#SBATCH"):
            insert_at = idx + 1
    lines.insert(insert_at, "set -eo pipefail\n")
    return "".join(lines)


def _make_gpu_optional(source: str) -> str:
    if "GPU_FLAG=" in source:
        return source

    singularity_call = "singularity run --nv "
    if singularity_call not in source:
        return source

    gpu_flag = (
        'GPU_FLAG=""\n'
        'case "${USE_GPU:-}" in\n'
        '  true|True|TRUE|1|yes|Yes|YES|y|Y|on|On|ON) GPU_FLAG="--nv" ;;\n'
        "esac\n\n"
    )
    return source.replace(
        singularity_call,
        gpu_flag + "singularity run $GPU_FLAG ",
        1,
    )


def _append_output_check(source: str) -> str:
    if 'nl_biomero_verify_outputs' in source:
        return source

    source = source.rstrip()
    success_echo = 'echo "Job completed successfully."'
    has_success_echo = source.endswith(success_echo)
    if has_success_echo:
        source = source[: -len(success_echo)].rstrip()

    output_check = (
        "\n"
        '. "${SCRIPT_PATH:-$(dirname "$0")}/jobs/biomero_job_helpers.sh"\n'
        "nl_biomero_verify_outputs\n"
    )
    if has_success_echo:
        output_check += success_echo + "\n"

    return source + output_check


def _normalize_job_script(source: str) -> str:
    '''Apply remote Slurm compatibility edits to one repository-provided job script.'''
    source = re.sub(r"^#SBATCH --gres=.*\n", "", source, flags=re.MULTILINE)
    source = _insert_strict_mode(source)
    source = _insert_env_loader(source)
    source = _make_gpu_optional(source)
    source = re.sub(
        r'echo "Running ([^"]*?)(?<! Job) w/',
        r'echo "Running \1 Job w/',
        source,
    )
    return _append_output_check(source)


def _ensure_local_scripts(repo: Path) -> Path:
    jobs_dir = repo / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)

    conversion_script = repo / "convert_job_array.sh"
    if not conversion_script.exists():
        conversion_script.write_text(CONVERT_JOB_ARRAY)
        conversion_script.chmod(0o755)

    for name, contents in GENERATED_JOBS.items():
        # Add local job scripts for configured workflows that upstream
        # slurm-scripts does not currently ship.
        script = jobs_dir / name
        if not script.exists():
            script.write_text(contents)
            script.chmod(0o755)

    return jobs_dir


def main() -> None:
    repo = Path(sys.argv[1])
    jobs_dir = _ensure_local_scripts(repo)

    jobs = sorted(
        script
        for script in jobs_dir.glob("*.sh")
        if script.name != "biomero_job_helpers.sh"
    )
    if not jobs:
        raise SystemExit(0)

    for script in jobs:
        script.write_text(_normalize_job_script(script.read_text()))


if __name__ == "__main__":
    main()
