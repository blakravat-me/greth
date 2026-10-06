# tools/filesystem/list_dir.py
"""List the entries of a directory."""

from pydantic import BaseModel, Field

from ._path import resolve

MAX_ENTRIES = 500


class ListDirArgs(BaseModel):
    """List a directory in the workspace; directories end with '/'."""

    path: str = Field(".", description="Directory path relative to the workspace.")


def list_dir(path: str = ".") -> str:
    """Return sorted entry names, directories first marked with a trailing slash."""
    try:
        target = resolve(path)
        entries = sorted(
            (entry.name + "/" if entry.is_dir() else entry.name for entry in target.iterdir()),
            key=lambda name: (not name.endswith("/"), name),
        )
    except (OSError, ValueError) as exc:
        return f"[ERROR] {exc}"

    if not entries:
        return "[Empty directory.]"

    shown = "\n".join(entries[:MAX_ENTRIES])
    extra = len(entries) - MAX_ENTRIES
    return f"{shown}\n[{extra} more entries not shown]" if extra > 0 else shown
