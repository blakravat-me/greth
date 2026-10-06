# helpers/console.py
from __future__ import annotations

from rich.console import Console

__all__ = ["console", "clear_scrollback"]

console: Console = Console()


def clear_scrollback() -> None:
    """Clear the terminal's scrollback buffer, through the shared console."""
    console.file.write("\x1b[3J")
    console.file.flush()
