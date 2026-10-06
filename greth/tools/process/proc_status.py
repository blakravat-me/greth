# tools/process/proc_status.py
"""List every active session with its last command and busy/idle state."""

from pydantic import BaseModel

from .proc import _REGISTRY_LOCK, _SESSIONS, _capture, _drop, _list_names, _poll_done


class ProcStatusArgs(BaseModel):
    pass  # no arguments


def _refresh(name: str) -> None:
    """Finalize a finished background command so status is never stale."""
    sess = _SESSIONS.get(name)

    if sess is None:
        return

    with sess.state:
        busy = sess.busy

    if not busy:
        return

    try:
        _poll_done(sess, _capture(name))
    except RuntimeError:
        pass  # session vanished mid-call; handled by the next status call


def proc_status() -> str:
    names = _list_names()

    if names is None:
        return "[ERROR] Unable to list tmux sessions."

    # Drop registry entries whose tmux session no longer exists.
    with _REGISTRY_LOCK:
        stale = [n for n in _SESSIONS if n not in names]
    for name in stale:
        _drop(name)

    if not names:
        return "[No active sessions.]"

    lines = []
    for name in names:
        _refresh(name)

        sess = _SESSIONS.get(name)

        if sess is None:
            lines.append(f"- {name} [unknown]: (untracked — created outside proc)")
            continue

        with sess.state:
            status = "busy" if sess.busy else "idle"
            command = sess.last_command or "(none yet)"
            code = sess.last_exit_code

        suffix = f" (last exit: {code})" if status == "idle" and code is not None else ""
        lines.append(f"- {name} [{status}]: {command}{suffix}")

    return "\n".join(lines)
