"""Smoke-test the pinned DataQueryWorker release and its persistent caches."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "tests" / "data-query-worker-smoke.compose.yml"
SERVICE = "data-query-worker"


def compose(*arguments: str, capture: bool = False) -> str:
    result = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *arguments],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=capture,
    )
    return result.stdout.strip() if capture else ""


def wait_ready(timeout_seconds: int = 120) -> None:
    container_id = compose("ps", "--quiet", SERVICE, capture=True)
    if not container_id:
        raise RuntimeError("DataQueryWorker container was not created")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", container_id],
            check=False,
            text=True,
            capture_output=True,
        )
        if result.returncode == 0 and result.stdout.strip() == "healthy":
            return
        time.sleep(1)
    compose("logs", SERVICE)
    raise RuntimeError("DataQueryWorker did not become healthy")


def exec_smoke(phase: str) -> None:
    compose(
        "exec",
        "--no-TTY",
        SERVICE,
        "python",
        "/app/scripts/smoke_inside.py",
        phase,
    )


def main() -> None:
    try:
        compose("up", "--detach")
        wait_ready()
        exec_smoke("initial")
        compose("restart", SERVICE)
        wait_ready()
        exec_smoke("restart")
        print("Pinned DataQueryWorker release smoke passed")
    finally:
        compose("down", "--volumes", "--remove-orphans")


if __name__ == "__main__":
    main()
