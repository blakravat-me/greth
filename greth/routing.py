# greth/routing.py
"""Phase transition rules, before and after the objective is reached."""

from config import AFTER, BEFORE
from greth.state import AgentState


def allowed(state: AgentState) -> tuple[str, ...]:
    """Next phases allowed from the current phase, before or after the objective is reached."""
    return (AFTER if state["reached"] else BEFORE)[state["phase"]]


def route(phase: str, chosen: str, done: bool) -> str:
    """Next phase: only a done objective at striker leads to the operator, never anything else."""
    if done and phase == "striker":
        return "operator"
    return phase if chosen == "operator" else chosen
