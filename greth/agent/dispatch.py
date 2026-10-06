# greth/dispatch.py
"""Tool execution: read_artifact is served locally, every other tool goes to tools.policy."""

from greth.agent.artifact import read_artifact
from greth.tools import policy


def dispatch(phase: str, call: dict) -> object:
    """Serve read_artifact locally; send every other tool call to tools.policy."""
    if call["name"] == "read_artifact":
        return read_artifact(**call["arguments"])
    return policy.dispatch(phase, "act", call["name"], call["arguments"])
