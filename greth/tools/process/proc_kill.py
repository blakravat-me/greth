# tools/process/proc_kill.py
"""Terminate a session."""

from .proc import _SESSIONS, SessionArgs, _drop, _norm_session, _tmux, _valid_session_name

ProcKillArgs = SessionArgs  # same shape: {"session": str}


def proc_kill(session: str = "") -> str:
    session = _norm_session(session)

    if not _valid_session_name(session):
        return f"[ERROR] Invalid session name {session!r}."

    # Reset tracking first so a concurrent proc() loop stops cleanly
    # instead of polling a session that is about to disappear.
    sess = _SESSIONS.get(session)
    if sess is not None:
        with sess.state:
            sess.busy = False
            sess.marker = ""

    try:
        result = _tmux("kill-session", "-t", session)
    except RuntimeError as exc:
        return f"[ERROR] {exc}"

    if result.returncode != 0:
        _drop(session)  # tmux says it's gone; keep registry consistent
        reason = (result.stderr or result.stdout).strip() or f"exit code {result.returncode}"
        return f"[ERROR] Session '{session}' could not be killed: {reason}"

    _drop(session)
    return f"[Session '{session}' killed.]"
