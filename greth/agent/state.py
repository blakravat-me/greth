# greth/state.py
"""Loop memory shared by every node."""

from typing import TypedDict

from greth.config import START_PHASE


class AgentState(TypedDict, total=False):
    """Loop memory; every field reaches the prompt only as bounded, overwritten or rolling text."""

    target: str
    objective: str
    instruction: str
    phase: str
    reached: bool
    chosen_phase: str
    global_plan: dict
    operator_plan: dict
    replan_reason: str
    handoff: str
    observation: str
    orientation: str
    decision: str
    last_result: str
    tool_results: list[dict]
    tool_error: bool
    error_message: str
    journal: list[str]
    artifacts: list[str]


CLEARED = {"observation": "", "orientation": "", "decision": "", "last_result": "", "tool_results": []}


def new_state(target: str, objective: str, instruction: str) -> AgentState:
    """Initial state: scout phase, objective not reached, empty plans."""
    return {
        "target": target,
        "objective": objective,
        "instruction": instruction,
        "phase": START_PHASE,
        "reached": False,
        "tool_error": False,
        "error_message": "",
        "tool_results": [],
        "global_plan": {"version": 0, "steps": []},
        "operator_plan": {"version": 0, "steps": []},
        "replan_reason": "initial plan",
        "journal": [],
        "artifacts": [],
    }
