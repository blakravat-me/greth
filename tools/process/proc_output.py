# tools/process/proc_output.py
"""Fetch the current screen of a session — poll a background job or a timed-out command."""

from .proc import (
    _SESSIONS,
    SessionArgs,
    _capture,
    _clean,
    _done_report,
    _drop,
    _norm_session,
    _poll_done,
    _report,
    _view,
)

ProcOutputArgs = SessionArgs  # same shape: {"session": str}


def proc_output(session: str = "") -> str:
    session = _norm_session(session)
    sess = _SESSIONS.get(session)

    if sess is None:
        return f"[ERROR] Session '{session}' does not exist or is not tracked."

    try:
        screen = _capture(session)
    except RuntimeError as exc:
        _drop(session)
        return f"[ERROR] {exc}"

    done = _poll_done(sess, screen)
    if done is not None:
        return _done_report(done)

    with sess.state:
        busy, marker = sess.busy, sess.marker
        last_code, last_output = sess.last_exit_code, sess.last_output

    if busy:
        return _report(_view(screen, marker), note="[Still running — no completion marker yet.]")

    if last_code is not None:
        return _report(last_output, note=f"[Last command exit code: {last_code}]")

    return _report(_clean(screen), note="") or "[No output.]"
