# tools/process/proc.py
"""tmux-backed persistent sessions inside the sandbox container.

Design:
- every command is wrapped as ONE shell line:
    printf BEGIN; eval '<quoted command>'; printf EXIT:<code>
  so the typed echo always precedes BEGIN and output is cut deterministically
  between the BEGIN and EXIT lines (no echo/wrap/heredoc/comment leaks).
- capture uses -J (joined wrapped lines) and is bounded.
- one non-blocking I/O lock per session (no waiting -> no deadlock),
  one tiny state lock shared with proc_output.
- every output path goes through _view/_clean, so markers never reach the caller.
"""

from __future__ import annotations

import re
import shlex
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from threading import Lock

from pydantic import BaseModel, Field, field_validator, model_validator

from greth.runtime.docker import COMPOSE_FILE, PROJECT_ROOT, service_name

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MIN_POLL_INTERVAL = 0.10
MAX_POLL_INTERVAL = 0.75
STALL_SECONDS = 2.0
MAX_REPEAT = 3
CAPTURE_LINES = 200
SUBPROCESS_TIMEOUT = 20

CONTROL_KEYS = {"C-c", "C-z", "C-d", "C-l"}

DEFAULT_SESSION = "main"
_SESSION_NAME_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,63}")


def _norm_session(value: object) -> str:
    """Trim padding; blank falls back to the default session."""
    return str(value or "").strip() or DEFAULT_SESSION


def _norm_command(command: object, is_input: bool) -> str:
    text = str(command or "")
    stripped = text.strip()

    if stripped or not is_input:
        return stripped

    # Whitespace-only *input* (e.g. a single space) is meaningful; only drop newlines.
    return text.strip("\r\n")


def _valid_session_name(name: str) -> bool:
    return _SESSION_NAME_RE.fullmatch(name) is not None


# ---------------------------------------------------------------------------
# Regex
# ---------------------------------------------------------------------------

_PROMPT_TAIL_RE = re.compile(r"[$#>:?]\s*$|\[[yYnN/]+\]\s*$|^\(Pdb\)\s*$")

# Any line that mentions a marker (echo of wrapper, stale BEGIN/EXIT lines).
_MARKER_LINE_RE = re.compile(r"^.*__GRETH_[0-9a-f]{10}__.*(?:\n|\Z)", re.MULTILINE)

# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


@dataclass
class _Session:
    busy: bool = False
    marker: str = ""
    last_command: str = ""
    last_output: str = ""
    last_exit_code: int | None = None

    io: Lock = field(default_factory=Lock)  # serializes send/wait (non-blocking acquire)
    state: Lock = field(default_factory=Lock)  # guards busy/marker/last_* (microseconds)


_SESSIONS: dict[str, _Session] = {}
_REGISTRY_LOCK = Lock()
_service_checked = False
_container_id = ""


def _list_names() -> list[str] | None:
    """Live tmux session names, or None when the tmux server is unreachable.

    tmux exits non-zero both when the server is down and when no session exists,
    so an empty server is reported as [] only if stderr says so.
    """
    result = _tmux("list-sessions", "-F", "#{session_name}")

    if result.returncode == 0:
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    err = (result.stderr or "").lower()
    if "no server running" in err or "no sessions" in err or "error connecting" in err:
        return []

    return None


# ---------------------------------------------------------------------------
# Tool schemas (shared by proc_kill.py / proc_output.py to avoid duplication)
# ---------------------------------------------------------------------------


class SessionArgs(BaseModel):
    """Identify a session by name; used by proc_kill and proc_output."""

    session: str = Field(..., description="Session name previously used with proc.")

    @field_validator("session", mode="before")
    @classmethod
    def _clean_session(cls, v: object) -> str:
        return _norm_session(v)


class ProcArgs(BaseModel):
    """Run a command, send input to a waiting prompt, or peek at a session's screen."""

    command: str = Field(
        "",
        description=(
            "Shell command to run, or text to send if is_input=True. "
            "A control sequence (C-c, C-z, C-d, C-l) is sent as a key, "
            "not typed text. Empty string just reads the current screen."
        ),
    )
    session: str = Field(
        DEFAULT_SESSION,
        description="Session name: letters, digits, '_' or '-' (max 64). Created automatically if new.",
    )
    timeout: int = Field(60, ge=1, le=3600, description="Seconds to wait for completion before giving up.")
    background: bool = Field(
        False,
        description="Start the command and return immediately; check later with proc_output.",
    )
    is_input: bool = Field(
        False,
        description="True when this session is already waiting on an interactive prompt.",
    )
    description: str = Field("", description="One short phrase: why this call is being made.")

    @field_validator("session", mode="before")
    @classmethod
    def _clean_session(cls, v: object) -> str:
        return _norm_session(v)

    @field_validator("description", mode="before")
    @classmethod
    def _clean_description(cls, v: object) -> str:
        return str(v or "").strip()

    @model_validator(mode="after")
    def _clean_command(self) -> "ProcArgs":
        self.command = _norm_command(self.command, self.is_input)
        return self


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def _compress(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    i = 0

    while i < len(lines):
        j = i
        while j < len(lines) and lines[j] == lines[i]:
            j += 1

        run = j - i
        if run > MAX_REPEAT:
            out.append(lines[i])
            out.append(f"  ... (line repeated {run - 1} more times)")
        else:
            out.extend(lines[i:j])

        i = j

    return "\n".join(out)


def _clean(text: str) -> str:
    """Drop every marker-bearing line."""
    return _MARKER_LINE_RE.sub("", text)


def _report(body: str, *, note: str) -> str:
    body = _compress(body.strip())

    if not body:
        if note.startswith("[Exit"):
            return f"[Command completed with no output.] {note}"
        return note

    return f"{body}\n{note}" if note else body


# ---------------------------------------------------------------------------
# Docker / tmux
# ---------------------------------------------------------------------------


def _sh(*args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=SUBPROCESS_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"command timed out after {SUBPROCESS_TIMEOUT}s: {' '.join(args[-3:])}") from exc


def _container() -> str:
    global _container_id
    if not _container_id:
        out = _sh("docker", "compose", "-f", str(COMPOSE_FILE), "ps", "-q", service_name()).stdout.split()
        if not out:
            raise RuntimeError(f"Sandbox service '{service_name()}' is not running.")
        _container_id = out[0]
    return _container_id


def _tmux(*args: str) -> subprocess.CompletedProcess[str]:
    result = _sh("docker", "exec", _container(), "tmux", *args)
    if result.returncode != 0 and "No such container" in result.stderr:
        global _container_id
        _container_id = ""  # container was recreated; resolve again next call
    return result


def _tmux_checked(*args: str) -> subprocess.CompletedProcess[str]:
    result = _tmux(*args)

    if result.returncode != 0:
        reason = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"tmux {' '.join(args)} failed: {reason}")

    return result


def _send_line(session_name: str, line: str) -> None:
    """Send one complete shell line atomically."""
    _tmux_checked("send-keys", "-t", session_name, "-l", f"{line}\n")


def _send_key(session_name: str, key: str) -> None:
    _tmux_checked("send-keys", "-t", session_name, key)


# ---------------------------------------------------------------------------
# Service / session management
# ---------------------------------------------------------------------------


def _ensure_service_running() -> None:
    global _service_checked

    if _service_checked:
        return

    service = service_name()
    result = _sh(
        "docker",
        "compose",
        "-f",
        str(COMPOSE_FILE),
        "ps",
        "--status",
        "running",
        "--services",
    )
    running = {line.strip() for line in result.stdout.splitlines() if line.strip()}

    if service not in running:
        raise RuntimeError(
            f"Sandbox service '{service}' is not running under {COMPOSE_FILE}. Running services: {sorted(running) or '(none)'}."
        )

    _service_checked = True


def _ensure(session_name: str) -> _Session:
    with _REGISTRY_LOCK:
        session = _SESSIONS.get(session_name)
        if session is not None:
            return session

        _ensure_service_running()

        if _tmux("has-session", "-t", session_name).returncode != 0:
            _tmux_checked("new-session", "-d", "-s", session_name, "-x", "220", "-y", "50")
            _tmux_checked("set-option", "-t", session_name, "remain-on-exit", "on")

        # Register only after tmux is known-good: no stale entries on failure.
        session = _Session()
        _SESSIONS[session_name] = session
        return session


def _drop(session_name: str) -> None:
    with _REGISTRY_LOCK:
        _SESSIONS.pop(session_name, None)


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------


def _capture(session_name: str) -> str:
    """Capture recent screen/history; -J joins wrapped lines (no split markers)."""
    result = _tmux("capture-pane", "-t", session_name, "-p", "-J", "-S", f"-{CAPTURE_LINES}")

    if result.returncode != 0:
        reason = result.stderr.strip() or result.stdout.strip() or "unknown tmux error"
        raise RuntimeError(f"Unable to capture session '{session_name}': {reason}")

    return result.stdout


# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------


def _make_marker() -> str:
    return f"__GRETH_{uuid.uuid4().hex[:10]}__"


@lru_cache(maxsize=128)
def _patterns(marker: str) -> tuple[re.Pattern[str], re.Pattern[str]]:
    m = re.escape(marker)
    return (
        re.compile(rf"(?m)^{m}:BEGIN[ \t]*$"),
        re.compile(rf"(?m)^{m}:EXIT:(\d+)[ \t]*$"),
    )


def _wrap(command: str, marker: str) -> str:
    """One logical line: echo always precedes BEGIN; safe for heredocs/comments."""
    return f"printf '%s:BEGIN\\n' '{marker}'; eval {shlex.quote(command)}; printf '\\n%s:EXIT:%s\\n' '{marker}' \"$?\""


def _extract(screen: str, marker: str) -> tuple[int, str, bool] | None:
    """Return (exit_code, body, truncated) once EXIT is on screen, else None."""
    begin_re, exit_re = _patterns(marker)

    last_exit = None
    for last_exit in exit_re.finditer(screen):
        pass
    if last_exit is None:
        return None

    head = screen[: last_exit.start()]

    last_begin = None
    for last_begin in begin_re.finditer(head):
        pass

    start = last_begin.end() if last_begin else 0  # no BEGIN => scrolled out of capture
    return int(last_exit.group(1)), _clean(head[start:]), last_begin is None


def _view(screen: str, marker: str) -> str:
    """Marker-free view of a (possibly in-progress) screen."""
    if marker:
        begin_re, _ = _patterns(marker)
        last_begin = None
        for last_begin in begin_re.finditer(screen):
            pass
        if last_begin is not None:
            screen = screen[last_begin.end() :]

    return _clean(screen)


def _poll_done(sess: _Session, screen: str) -> tuple[int, str, bool] | None:
    """Idempotently finalize the active command if its EXIT marker is visible."""
    with sess.state:
        if not (sess.busy and sess.marker):
            return None

        parsed = _extract(screen, sess.marker)
        if parsed is None:
            return None

        code, body, _ = parsed
        sess.busy = False
        sess.marker = ""
        sess.last_output = body
        sess.last_exit_code = code
        return parsed


def _done_report(done: tuple[int, str, bool], started: float | None = None) -> str:
    code, body, truncated = done

    note = f"[Exit code: {code}]"
    if started is not None:
        note += f" [{round((time.monotonic() - started) * 1000, 2)} ms]"
    if truncated:
        note += f" [output truncated to last {CAPTURE_LINES} lines]"

    return _report(body, note=note)


# ---------------------------------------------------------------------------
# Interactive detection
# ---------------------------------------------------------------------------


def _looks_interactive(screen: str) -> bool:
    for line in reversed(screen.splitlines()):
        if line.strip():
            return bool(_PROMPT_TAIL_RE.search(line))
    return False


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def proc(
    command: str = "",
    session: str = DEFAULT_SESSION,
    timeout: int = 60,
    background: bool = False,
    is_input: bool = False,
    description: str = "",  # noqa: ARG001 - part of the tool schema
) -> str:
    """Execute command inside a persistent tmux session."""
    session = _norm_session(session)
    command = _norm_command(command, is_input)
    timeout = max(1, min(int(timeout), 3600))

    if not _valid_session_name(session):
        return f"[ERROR] Invalid session name {session!r}. Use letters, digits, '_' or '-' (max 64, not starting with '-')."

    try:
        sess = _ensure(session)

        # Never wait on a lock: a second caller gets an immediate answer.
        if not sess.io.acquire(blocking=False):
            return f"[BUSY] Session '{session}' is handling another call. Retry shortly or use another session."

        try:
            return _run(sess, command, session, timeout, background, is_input)
        finally:
            sess.io.release()
    except RuntimeError as exc:
        _drop(session)  # tmux session may be gone; next call re-creates it
        return f"[ERROR] {exc}"


def _snapshot(sess: _Session, session: str, note: str) -> str:
    screen = _capture(session)

    done = _poll_done(sess, screen)
    if done is not None:
        return _done_report(done)

    return _report(_view(screen, sess.marker), note=note)


def _wait(sess: _Session, session: str, started: float, timeout: int) -> str:
    prev: str | None = None
    last_change = time.monotonic()
    interval = MIN_POLL_INTERVAL

    while True:
        screen = _capture(session)

        done = _poll_done(sess, screen)
        if done is not None:
            return _done_report(done, started)

        now = time.monotonic()

        if screen != prev:
            prev, last_change, interval = screen, now, MIN_POLL_INTERVAL
        else:
            interval = min(interval * 1.5, MAX_POLL_INTERVAL)

        remaining = timeout - (now - started)

        if remaining <= 0:
            return _report(
                _view(screen, sess.marker),
                note=(
                    f"[TIMEOUT after {timeout}s] session '{session}' is still busy. "
                    f"Use proc_output(session='{session}') to keep checking, or proc_kill to stop it."
                ),
            )

        if now - last_change >= STALL_SECONDS and _looks_interactive(screen):
            return _report(
                _view(screen, sess.marker),
                note=(f"[session: {session} — interactive, screen looks like a prompt. Send the next input with is_input=True.]"),
            )

        time.sleep(min(interval, remaining))


def _run(
    sess: _Session,
    command: str,
    session: str,
    timeout: int,
    background: bool,
    is_input: bool,
) -> str:
    started = time.monotonic()

    # Peek
    if not command:
        with sess.state:
            busy = sess.busy

        if busy:
            return _wait(sess, session, started, timeout)  # blocks until done / prompt / timeout

        return _snapshot(
            sess,
            session,
            note="[IDLE] No command is running in this session; nothing to wait for. Run a command or call finish.",
        )

    # Control key: aborts whatever is running, so stop tracking it.
    if command in CONTROL_KEYS:
        _send_key(session, command)
        time.sleep(MIN_POLL_INTERVAL)

        with sess.state:
            sess.busy = False
            sess.marker = ""
            sess.last_command = command

        return _report(_clean(_capture(session)), note=f"(sent {command})")

    # Interactive input: keep tracking the SAME marker until the command ends.
    if is_input:
        _send_line(session, command)
        time.sleep(MIN_POLL_INTERVAL)

        if sess.busy:
            return _wait(sess, session, started, timeout)

        return _snapshot(sess, session, note="(input sent)")

    # Normal command: refuse to type into a still-running one.
    if sess.busy:
        _poll_done(sess, _capture(session))

    if sess.busy:
        return f"[BUSY] Session '{session}' still has a running command. Use proc_output, is_input=True, C-c, or another session."

    marker = _make_marker()

    with sess.state:
        sess.busy = True
        sess.marker = marker

    _send_line(session, _wrap(command, marker))

    if background:
        return f"[BACKGROUND] Command started in session '{session}'. Check with proc_output(session='{session}')."

    return _wait(sess, session, started, timeout)
