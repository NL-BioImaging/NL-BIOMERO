"""
Compatibility patch for the BIOMERO version pinned by this deployment.

Why this exists:
- BIOMERO's remote unpack and result packaging commands assume the Slurm login
  node has `7z`. Some SURF clusters expose `7za`, so exports appeared to succeed but
  left data/in empty, and result imports could fail after successful workflows.
  The fallback keeps the same behavior on systems with `7z` while supporting
  Slurm clusters.
- `mkdir -p` makes retries idempotent after a partially created workflow
  directory.
- Workflows can expose a `use_gpu` parameter, but BIOMERO's config can only add
  static sbatch parameters. This patch forces `use_gpu=true` for selected
  GPU-native generated workflow scripts unless the request explicitly disables
  it, and injects the Spider GPU partition plus a Slurm GPU request only when
  the effective `use_gpu` value is true.
- `slurm_data_bind_path` is required so Apptainer can see the same
  BIOMERO data path that jobs receive. A blank value used to be exported as
  APPTAINER_BINDPATH="", which can make Apptainer complain about `/ as sandbox
  is not authorized`; now it fails early with a clear config error.
- Some Slurm clusters do not propagate ambient SSH shell environment variables into
  file-based `sbatch` jobs. Workflow submissions now write a per-job env file
  and generated Slurm job scripts source it before launching containers.
- Some workflow containers can print a Python traceback but still exit zero and
  leave `data/out` empty. Generated scripts now fail on command errors and
  verify that output files were produced before BIOMERO enters the import stage.
- BIOMERO starts all Singularity pulls in parallel and lets Apptainer use the
  login node /tmp for build work. On Spider this can exhaust /tmp and still log
  "finished" because the command is backgrounded. Pulls now run sequentially,
  use project storage for Apptainer temp/cache directories, return failures, and
  are submitted to Slurm instead of running on the login node.

Remove this when upstream BIOMERO includes these compatibility fixes.
"""

from pathlib import Path
import site
import sys


PATCH_DIR = Path(__file__).resolve().parent / "patches"


def _replace_required(source: str, old: str, new: str, description: str) -> str:
    if old not in source:
        raise RuntimeError(f"Could not patch BIOMERO slurm_client.py: {description}")
    return source.replace(old, new)


def _biomero_file(name: str) -> Path:
    # Locate BIOMERO inside the active container venv without importing it.
    # Importing can fail while the package is half-patched during image build.
    candidates = []
    for base in site.getsitepackages() + [site.getusersitepackages(), *sys.path]:
        if base:
            candidates.append(Path(base) / "biomero" / name)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Could not locate biomero/{name}")


def _read_patch(path: str) -> str:
    return (PATCH_DIR / path).read_text(encoding="utf-8")


def patch_slurm_client() -> None:
    path = _biomero_file("slurm_client.py")
    source = path.read_text(encoding="utf-8")
    generated_job_helper = _read_patch("generated_job_postprocess.py")

    if "import shlex\n" not in source:
        source = source.replace("import os\n", "import os\nimport shlex\n")

    if "_nl_biomero_normalize_generated_job_script" not in source:
        source = _replace_required(
            source,
            "\nclass SlurmJob:",
            f"\n{generated_job_helper}\n\nclass SlurmJob:",
            "generated Slurm job helper insertion",
        )

    # When slurm_script_repo is empty, BIOMERO generates scripts locally and
    # uploads them directly. Normalize that supported generated-script path.
    # If an administrator supplies a custom Git repository, BIOMERO uses it as
    # provided and NL-BIOMERO does not mutate that repository contract.
    source = _replace_required(
        source,
        """            job_script = src.safe_substitute(substitutes)
        return job_script
""",
        """            job_script = src.safe_substitute(substitutes)
        job_script = _nl_biomero_normalize_generated_job_script(job_script)
        return job_script
""",
        "generated Slurm job script env-file loader",
    )

    # Make unpacking exported image ZIPs work on Slurm systems with either
    # `7z` or `7za`, and make retries tolerate existing directories.
    source = _replace_required(
        source,
        'unzip_cmd = f"mkdir \\"{self.slurm_data_path}/{zipfile}\\" \\',
        'unzip_cmd = f"mkdir -p \\"{self.slurm_data_path}/{zipfile}\\" \\',
        "remote export directory creation",
    )
    source = _replace_required(
        source,
        '                    7z x -y -o\\"{self.slurm_data_path}/{zipfile}/data/in\\" \\',
        '                    ZIP_CMD=$(command -v 7z || command -v 7za) && \\"$ZIP_CMD\\" x -y -o\\"{self.slurm_data_path}/{zipfile}/data/in\\" \\',
        "remote export ZIP extraction",
    )
    source = _replace_required(
        source,
        '    _ZIP_CMD = "cd \\"{data_location}/data/out\\" && 7z a -y \\"{data_location}/{filename}.zip\\" -tzip ."',
        '    _ZIP_CMD = "cd \\"{data_location}/data/out\\" && ZIP_CMD=$(command -v 7z || command -v 7za) && \\"$ZIP_CMD\\" a -y \\"{data_location}/{filename}.zip\\" -tzip ."',
        "remote result ZIP packaging",
    )

    # Request Spider GPU resources only for effective GPU jobs. CPU-only jobs
    # omit --partition and use Spider's normal/default partition.
    source = _replace_required(
        source,
        """        job_params = self.slurm_model_jobs_params[workflow.lower()]
        # grab only the image name, not the group/creator
""",
        """        job_params = list(self.slurm_model_jobs_params[workflow.lower()])
        force_gpu_workflows = {
            item.strip().lower()
            for item in os.getenv(
                "BIOMERO_FORCE_GPU_WORKFLOWS",
                "cellpose,stardist,stardist5d,fractal-cellpose-sam-biaflows,deconvolve_plate",
            ).split(",")
            if item.strip()
        }
        use_gpu_value = kwargs.get("use_gpu")
        device_value = str(kwargs.get("device", "")).strip().lower()
        if (
            workflow.lower() in force_gpu_workflows
            and device_value != "cpu"
            and (
                "use_gpu" not in kwargs
                or use_gpu_value is None
                or str(use_gpu_value).strip() == ""
            )
        ):
            kwargs["use_gpu"] = "true"
            use_gpu_value = kwargs["use_gpu"]
        use_gpu = str(use_gpu_value).lower() in ("true", "1", "yes", "y", "on")
        if use_gpu:
            gpu_partition = os.getenv("BIOMERO_GPU_PARTITION", "gpu_a100_22c")
            if gpu_partition and not any(param.startswith(" --partition=") for param in job_params):
                job_params.append(f" --partition={gpu_partition}")
            gpu_count = os.getenv("BIOMERO_GPUS", "1")
            if gpu_count and not any(param.startswith(" --gpus=") for param in job_params):
                job_params.append(f" --gpus={gpu_count}")
        # grab only the image name, not the group/creator
""",
        "per-workflow GPU sbatch parameters",
    )

    # Fail loudly when the required Apptainer bind path is missing.
    # Without this, workflows can run but fail to write/import results.
    source = _replace_required(
        source,
        """        if self.slurm_data_bind_path is not None:
            sbatch_env["APPTAINER_BINDPATH"] = f"\\"{self.slurm_data_bind_path}\\""
""",
        """        if not self.slurm_data_bind_path:
            raise ValueError("slurm_data_bind_path must be set so Apptainer can access BIOMERO data paths")
        sbatch_env["APPTAINER_BINDPATH"] = f"\\"{self.slurm_data_bind_path}\\""
""",
        "required Slurm data bind path",
    )
    source = _replace_required(
        source,
        """        if self.slurm_conversion_partition is not None:
            sbatch_env["CONVERSION_PARTITION"] = f"\\"{self.slurm_conversion_partition}\\""
""",
        """        if self.slurm_conversion_partition:
            sbatch_env["CONVERSION_PARTITION"] = f"\\"{self.slurm_conversion_partition}\\""
""",
        "optional conversion partition export",
    )

    # Keep remote image initialization bounded by project storage instead of
    # Spider's small login-node /tmp. Run pulls in the foreground so failures
    # propagate to BIOMERO and the UI does not wait on orphaned background work.
    source = _replace_required(
        source,
        '''                    pull_template = "echo 'starting $path $version' >> sing.log\\nnohup sh -c \\"singularity pull --disable-cache --dir $path docker://$image:$version; echo 'finished $path $version'\\" >> sing.log 2>&1 & disown"
''',
        '''                    pull_template = "echo 'starting $path $version' >> sing.log\\nmkdir -p .apptainer_tmp .apptainer_cache $path\\nimage_name=$$(basename \\"$image\\")\\noutput=\\"$path/$${image_name}_$version.sif\\"\\nif [ -s \\"$$output\\" ]; then echo 'skipping $path $version; SIF already exists' >> sing.log; else APPTAINER_TMPDIR=$$PWD/.apptainer_tmp SINGULARITY_TMPDIR=$$PWD/.apptainer_tmp APPTAINER_CACHEDIR=$$PWD/.apptainer_cache SINGULARITY_CACHEDIR=$$PWD/.apptainer_cache singularity build --force --disable-cache --mksquashfs-args \\"-processors $${BIOMERO_PULL_CPUS:-8}\\" \\"$$output\\" docker://$image:$version >> sing.log 2>&1; fi\\nrc=$$?\\nif [ $$rc -eq 0 ]; then echo 'finished $path $version' >> sing.log; else echo 'failed $path $version exit='$$rc >> sing.log; exit $$rc; fi"
''',
        "foreground workflow Singularity pull using project storage",
    )
    source = _replace_required(
        source,
        '''                    pull_template = "echo 'starting $path $version' >> sing.log\\nnohup sh -c \\"singularity pull --force --disable-cache $conv_name docker://$image:$version; echo 'finished $path $version'\\" >> sing.log 2>&1 & disown"
''',
        '''                    pull_template = "echo 'starting $path $version' >> sing.log\\nmkdir -p .apptainer_tmp .apptainer_cache\\nif [ -s \\"$conv_name\\" ]; then echo 'skipping $path $version; SIF already exists' >> sing.log; else APPTAINER_TMPDIR=$$PWD/.apptainer_tmp SINGULARITY_TMPDIR=$$PWD/.apptainer_tmp APPTAINER_CACHEDIR=$$PWD/.apptainer_cache SINGULARITY_CACHEDIR=$$PWD/.apptainer_cache singularity build --force --disable-cache --mksquashfs-args \\"-processors $${BIOMERO_PULL_CPUS:-8}\\" $conv_name docker://$image:$version >> sing.log 2>&1; fi\\nrc=$$?\\nif [ $$rc -eq 0 ]; then echo 'finished $path $version' >> sing.log; else echo 'failed $path $version exit='$$rc >> sing.log; exit $$rc; fi"
''',
        "foreground converter Singularity pull using project storage",
    )
    source = _replace_required(
        source,
        '''                cmd = f"time sh {script_name}"
                r = self.run_commands([cmd])
''',
        '''                pull_cpus = os.getenv("BIOMERO_PULL_CPUS", "8")
                pull_mem = os.getenv("BIOMERO_PULL_MEM", "32G")
                resource_params = f" --cpus-per-task={pull_cpus} --mem={pull_mem} --export=ALL,BIOMERO_PULL_CPUS={pull_cpus}"
                cmd = f"sbatch --parsable --job-name=biomero-pull-images{resource_params} --output=pull_images-%j.log {script_name}"
                r = self.run_commands([cmd])
''',
        "submit workflow image initialization through Slurm",
    )
    source = _replace_required(
        source,
        '''            cmd = f"time sh {script_name}"
            with self.cd(self.slurm_converters_path):
                r = self.run_commands([cmd])
''',
        '''            pull_cpus = os.getenv("BIOMERO_PULL_CPUS", "8")
            pull_mem = os.getenv("BIOMERO_PULL_MEM", "32G")
            resource_params = f" --cpus-per-task={pull_cpus} --mem={pull_mem} --export=ALL,BIOMERO_PULL_CPUS={pull_cpus}"
            cmd = f"sbatch --parsable --job-name=biomero-pull-converters{resource_params} --output=pull_converters-%j.log {script_name}"
            with self.cd(self.slurm_converters_path):
                r = self.run_commands([cmd])
''',
        "submit configured converter image initialization through Slurm",
    )
    source = _replace_required(
        source,
        """        workflow_env = self.workflow_params_to_envvars(**kwargs)
        env = {**sbatch_env, **workflow_env}

        email_param = "" if email is None else f" --mail-user={email}"
        time_param = "" if time is None else f" --time={time}"
        job_params.append(time_param)
        job_params.append(email_param)
        job_param = "".join(job_params)
        sbatch_cmd = f"sbatch{job_param} --output=omero-%j.log \\
            \\"{self.slurm_script_path}/{job_script}\\""

        return sbatch_cmd, env
""",
        """        workflow_env = self.workflow_params_to_envvars(**kwargs)
        env = {**sbatch_env, **workflow_env}
        env_file = f"{self.slurm_data_path}/{input_data}/biomero_job_env.sh"
        env_lines = "\\n".join(
            f"export {key}={shlex.quote(str(value).strip(chr(34)))}"
            for key, value in env.items()
        )
        write_env_cmd = (
            f"cat > {shlex.quote(env_file)} <<'BIOMERO_ENV'\\n"
            f"{env_lines}\\n"
            "BIOMERO_ENV\\n"
        )

        email_param = "" if email is None else f" --mail-user={email}"
        time_param = "" if time is None else f" --time={time}"
        job_params.append(time_param)
        job_params.append(email_param)
        job_param = "".join(job_params)
        sbatch_cmd = f"{write_env_cmd}sbatch{job_param} --output=omero-%j.log \\
            \\"{self.slurm_script_path}/{job_script}\\" {shlex.quote(env_file)}"

        return sbatch_cmd, {}
""",
        "per-job Slurm environment file submission",
    )
    path.write_text(source, encoding="utf-8")


if __name__ == "__main__":
    patch_slurm_client()
