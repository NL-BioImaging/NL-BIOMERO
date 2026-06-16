def _nl_biomero_normalize_generated_job_script(job_script: str) -> str:
    """Normalize BIOMERO descriptor-generated Slurm scripts for remote Slurm.

    This helper is injected into ``biomero.slurm_client`` and handles the path
    where BIOMERO builds a Slurm script directly from workflow descriptors
    instead of cloning ``slurm_script_repo``. Keep it small: custom Git
    repositories are used as provided and are not modified by NL-BIOMERO.
    """
    if "set -eo pipefail" not in job_script:
        lines = job_script.splitlines(keepends=True)
        insert_at = 1 if lines and lines[0].startswith("#!") else 0
        for idx, line in enumerate(lines):
            if line.startswith("#SBATCH"):
                insert_at = idx + 1
        lines.insert(insert_at, "set -eo pipefail\n")
        job_script = "".join(lines)

    if "BIOMERO_ENV_FILE" not in job_script:
        env_loader = (
            "\n"
            'BIOMERO_ENV_FILE="${1:-}"\n'
            'if [ -n "$BIOMERO_ENV_FILE" ] && [ -f "$BIOMERO_ENV_FILE" ]; then\n'
            '    . "$BIOMERO_ENV_FILE"\n'
            "fi\n"
        )
        lines = job_script.splitlines(keepends=True)
        insert_at = 0
        for idx, line in enumerate(lines):
            if line.startswith("#SBATCH"):
                insert_at = idx + 1
        lines.insert(insert_at, env_loader)
        job_script = "".join(lines)

    if "GPU_FLAG=" not in job_script:
        singularity_call = "singularity run --nv "
        if singularity_call in job_script:
            gpu_flag = (
                'GPU_FLAG=""\n'
                'case "${USE_GPU:-}" in\n'
                '  true|True|TRUE|1|yes|Yes|YES|y|Y|on|On|ON) GPU_FLAG="--nv" ;;\n'
                "esac\n\n"
            )
            job_script = job_script.replace(
                singularity_call,
                gpu_flag + "singularity run $GPU_FLAG ",
                1,
            )

    if "_nl_biomero_verify_outputs" not in job_script:
        output_check = (
            "\n"
            "_nl_biomero_verify_outputs() {\n"
            '    if [ -z "${DATA_PATH:-}" ]; then\n'
            "        return 0\n"
            "    fi\n"
            '    output_dir="$DATA_PATH/data/out"\n'
            '    if [ ! -d "$output_dir" ]; then\n'
            '        echo "ERROR: Workflow output directory does not exist: $output_dir" >&2\n'
            "        return 2\n"
            "    fi\n"
            '    if [ -z "$(find "$output_dir" -mindepth 1 -print -quit)" ]; then\n'
            '        echo "ERROR: Workflow completed without producing files in $output_dir" >&2\n'
            "        return 2\n"
            "    fi\n"
            "}\n"
            "_nl_biomero_verify_outputs\n"
        )
        job_script = job_script.rstrip() + output_check

    return job_script
