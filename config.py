# config.py
"""Static settings: phases, transitions, context limits, and CLI defaults."""

import os
import time
from pathlib import Path

START_PHASE = "scout"
GLOBAL = "global"
BEFORE = {"scout": ("striker",), "striker": ("scout", "operator"), "operator": ()}
AFTER = {**BEFORE, "operator": ("scout", "striker")}  # once the objective is reached
PROMPT_DIR = Path(__file__).parent / "prompts"
RUN_ID = time.strftime("%Y%m%d-%H%M%S")  # one artifact folder per run keeps the journal clean
ARTIFACT_DIR = Path(os.getenv("AGENT_ARTIFACT_DIR", "artifacts")) / RUN_ID

SECTION_CHARS = 1200  # default cap per markdown section
LIMITS = {
    "target": 500,
    "objective": 800,
    "instruction": 800,
    "handoff": 800,
    "plan": 2000,
    "last_result": 2500,
}  # per-section caps: a prompt stays under ~10k chars
READ_CHARS = 2000  # default slice served by read_artifact
LINE_CHARS = 160  # one journal line in the context (the file keeps it whole)
PREVIEW_CHARS = 80  # characters of tool arguments kept in a journal line
PLAN_VIEW_DONE = 6  # done steps shown per plan; earlier ones are only counted
JOURNAL_LINES = 6  # recent journal lines shown; the full journal lives in an artifact
ARTIFACT_LINES = 8  # recent artifacts shown in the index
MAX_WAIT = 15  # seconds, ceiling of the wait while the model server is down
RECURSION_LIMIT = 2**31 - 1  # LangGraph step cap, raised so the loop runs until Ctrl+C

DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
DEFAULT_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_API_KEY = os.getenv("OLLAMA_API_KEY", "")
