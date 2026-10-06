# helpers/docker.py
"""Docker Compose helpers for the OffSec sandbox."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from greth.ui.console import console

PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yml"

TAIL_LINES = 40
QUICK_TIMEOUT = 20  # only for fast, bounded operations: info, config, down

_SERVICE_CACHE: str | None = None


def _check_prereqs() -> None:
    if shutil.which("docker") is None:
        raise RuntimeError("Docker is not installed or not on PATH.")

    if not COMPOSE_FILE.exists():
        raise RuntimeError(f"Compose file not found: {COMPOSE_FILE}")

    result = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
        timeout=QUICK_TIMEOUT,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Docker daemon is not reachable. Start Docker Desktop (or the docker service) and retry.\n"
            f"{_tail(result.stderr or result.stdout)}"
        )


def _compose(*args: str, capture: bool = True, timeout: int | None = QUICK_TIMEOUT) -> subprocess.CompletedProcess[str]:
    """timeout=None means wait indefinitely — used for build/up, which has no
    predictable upper bound (image size, network speed, package installs)."""
    console.print(f"[+] docker compose {' '.join(args)}")

    try:
        return subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
            cwd=PROJECT_ROOT,
            capture_output=capture,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"docker compose {' '.join(args)} timed out after {timeout}s.") from exc


def _tail(text: str) -> str:
    lines = text.strip().splitlines()
    return "\n".join(lines[-TAIL_LINES:]) if lines else "(no output)"


def _service_name() -> str:
    result = _compose("config", "--services", timeout=QUICK_TIMEOUT)

    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(
            f"Failed to read Docker Compose services — check docker-compose.yml syntax.\n{_tail(result.stderr or result.stdout)}"
        )

    return result.stdout.strip().splitlines()[0]


def service_name() -> str:
    """Public, cached accessor — resolves once per process, not once per call."""
    global _SERVICE_CACHE

    if _SERVICE_CACHE is None:
        _SERVICE_CACHE = _service_name()

    return _SERVICE_CACHE


def exec_in_container(*args: str) -> subprocess.CompletedProcess[str]:
    """Run an argument-safe, non-interactive command in the sandbox container."""
    if not args:
        raise ValueError("container command cannot be empty")
    result = _compose("exec", "-T", service_name(), *args, timeout=QUICK_TIMEOUT)
    if result.returncode != 0:
        raise RuntimeError(_tail(result.stderr or result.stdout))
    return result


def ensure_container() -> None:
    """Build and start the OffSec sandbox. No timeout on the build itself: a cold
    pull + apt/pip install can legitimately take longer than any fixed guess, and
    killing it mid-build wastes the work and leaves a half-built image. Output
    streams live to the terminal (capture=False) so a failing step is visible
    immediately, and Ctrl+C still works normally to abort by hand."""
    _check_prereqs()
    service = service_name()

    console.print(f"[+] Starting Docker Compose service: {service}")

    result = _compose("up", "-d", "--build", service, capture=False, timeout=None)

    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to start the OffSec sandbox (exit code {result.returncode}). See the build log above for the failing step."
        )


def remove_container() -> None:
    """Stop and remove the OffSec sandbox. Never raises: this runs in `finally`."""
    try:
        service = service_name()
    except RuntimeError:
        service = "(unknown)"

    console.print(f"[+] Removing Docker Compose service: {service}")

    try:
        result = _compose("down", timeout=QUICK_TIMEOUT)
        if result.returncode != 0:
            console.print(f"[!] Failed to remove sandbox: {_tail(result.stderr or result.stdout)}")
    except RuntimeError as exc:
        console.print(f"[!] Failed to remove sandbox: {exc}")
