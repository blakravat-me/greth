# greth/artifact.py
"""Full outputs live on disk, the context only holds references."""

import uuid
from pathlib import Path

from greth.agent.context import clip
from greth.config import ARTIFACT_DIR, JOURNAL_LINES, LINE_CHARS, READ_CHARS


def save_artifact(name: str, text: str) -> str:
    """Store a long output on disk and return its reference."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    reference = f"{name}-{uuid.uuid4().hex[:8]}"
    (ARTIFACT_DIR / f"{reference}.txt").write_text(text, encoding="utf-8")
    return reference


def read_artifact(reference: str, start: int = 0, length: int = READ_CHARS) -> str:
    """Read a slice of a stored output; raise explicitly when it does not exist."""
    path = ARTIFACT_DIR / f"{Path(reference).name}.txt"
    if not path.is_file():
        raise FileNotFoundError(f"artifact '{Path(reference).name}' was not found")
    return path.read_text(encoding="utf-8")[start : start + length]


def remember(journal: list[str], lines: list[str]) -> list[str]:
    """Append whole lines to the journal file, return the clipped recent ones for the context."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [" ".join(line.split()) for line in lines]
    with (ARTIFACT_DIR / "journal.txt").open("a", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")
    return (journal + [clip(line, LINE_CHARS) for line in lines])[-JOURNAL_LINES:]
