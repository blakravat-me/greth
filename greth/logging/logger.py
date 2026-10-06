# logging/logger.py
from __future__ import annotations

import inspect
import json
from datetime import datetime
from pathlib import Path
from typing import Any

_DEBUG_DIRECTORY = Path("debug")


def debug(data: Any) -> None:
    _write("DEBUG", data)


def info(data: Any) -> None:
    _write("INFO", data)


def warning(data: Any) -> None:
    _write("WARNING", data)


def error(data: Any) -> None:
    _write("ERROR", data)


def critical(data: Any) -> None:
    _write("CRITICAL", data)


def _write(level: str, data: Any) -> None:
    caller = Path(inspect.stack()[2].filename).stem
    log_file = _DEBUG_DIRECTORY / f"{caller}.log"

    _DEBUG_DIRECTORY.mkdir(exist_ok=True)

    timestamp = datetime.now().isoformat(timespec="seconds")

    try:
        formatted_data = json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        )
    except (TypeError, ValueError):
        formatted_data = str(data)

    with log_file.open("a", encoding="utf-8") as file:
        file.write(f"[{level}] {timestamp}\n")
        file.write(f"{formatted_data}\n\n")
