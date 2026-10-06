# tools/filesystem/write_file.py
"""Create or overwrite a text file."""

from pydantic import BaseModel, Field

from ._path import WORKSPACE, resolve


class WriteFileArgs(BaseModel):
    """Create or overwrite a text file in the workspace; parent directories are created."""

    path: str = Field(..., description="File path relative to the workspace.")
    content: str = Field(..., description="Full new content of the file.")


def write_file(path: str, content: str) -> str:
    """Write the file and report what was written."""
    try:
        target = resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except (OSError, ValueError) as exc:
        return f"[ERROR] {exc}"
    return f"[Wrote {len(content)} chars to {target.relative_to(WORKSPACE)}]"
