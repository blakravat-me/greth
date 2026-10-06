# tools/filesystem/_path.py
"""Workspace root and the one rule shared by every filesystem tool: stay inside it."""

import os
from pathlib import Path

WORKSPACE = Path(os.getenv("AGENT_WORKSPACE", "./workspace")).resolve()


def resolve(path: str) -> Path:
    """Map a path into the workspace; reject anything that resolves outside it."""
    target = (WORKSPACE / (path.strip() or ".")).resolve()
    if not target.is_relative_to(WORKSPACE):
        raise ValueError(f"path is outside the workspace: {path}")
    return target
