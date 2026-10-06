# tools/filesystem/read_file.py
"""Read a slice of a text file."""

from pydantic import BaseModel, Field

from ._path import resolve


class ReadFileArgs(BaseModel):
    """Read a text file in the workspace; use start/length to page through large files."""

    path: str = Field(..., description="File path relative to the workspace.")
    start: int = Field(0, ge=0, description="Character offset to start reading from.")
    length: int = Field(4000, ge=1, le=20000, description="Maximum characters to return.")


def read_file(path: str, start: int = 0, length: int = 4000) -> str:
    """Return up to `length` characters from `start`, with a note when more remains."""
    try:
        text = resolve(path).read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError) as exc:
        return f"[ERROR] {exc}"

    chunk = text[start : start + length]
    end = start + len(chunk)
    if end < len(text):
        return f"{chunk}\n[chars {start}-{end} of {len(text)}; continue with start={end}]"
    return chunk if chunk else f"[No content at start={start}; file has {len(text)} chars.]"
