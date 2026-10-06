# tools/policy.py
"""Tool registry: schemas offered per phase/state, and dispatch of domain tools.

Control tools (record_*, choose_action, phase_done, update_plan, set_plan, checkpoint)
are only offered here; greth/validation.py parses them and they are never dispatched.
read_artifact is offered here and served by greth/dispatch.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

from greth.tools.filesystem.list_dir import ListDirArgs, list_dir
from greth.tools.filesystem.read_file import ReadFileArgs, read_file
from greth.tools.filesystem.write_file import WriteFileArgs, write_file
from greth.tools.process.proc import ProcArgs, proc
from greth.tools.process.proc_kill import ProcKillArgs, proc_kill
from greth.tools.process.proc_output import ProcOutputArgs, proc_output
from greth.tools.process.proc_status import ProcStatusArgs, proc_status

Phase = str  # "scout" | "striker" | "operator" | "global"


# --- Control tool schemas ---
class RecordObservation(BaseModel):
    """Record verified facts and the remaining knowledge gaps."""

    facts: list[str] = Field(..., description="Verified facts, each with an artifact reference.")
    gaps: list[str] = Field(default_factory=list, description="What is still unknown.")


class RecordOrientation(BaseModel):
    """Record the assessment of the situation."""

    assessment: str
    risks: list[str] = Field(default_factory=list)
    options: list[str] = Field(default_factory=list)


class ChooseAction(BaseModel):
    """Choose the next concrete action."""

    intent: str
    success_criteria: str


class PhaseDone(BaseModel):
    """Close the current phase."""

    summary: str
    next_phase: Literal["scout", "striker", "operator"]
    objective: str = Field("", description="Operator only: the new objective that replaces the current one.")


class UpdatePlan(BaseModel):
    """Operator only: replace all pending steps and mark finished ones."""

    summary: str = ""
    steps: list[str] = Field(default_factory=list, description="Every step that is still pending.")
    completed_steps: list[str] = Field(default_factory=list, description="Ids of finished steps.")


class SetPlan(BaseModel):
    """Set the pending steps of the global plan."""

    steps: list[str] = Field(..., min_length=1)


class Checkpoint(BaseModel):
    """Judge whether the objective is reached."""

    objective_done: bool
    evidence: str = ""
    completed_steps: list[str] = Field(default_factory=list)
    replan_reason: str = ""


class ReadArtifact(BaseModel):
    """Reopen a stored tool output by reference."""

    reference: str
    start: int = Field(0, ge=0)
    length: int = Field(2000, ge=1, le=20000)


_OBSERVE = ("record_observation", "Record verified facts and gaps.", RecordObservation)
_ORIENT = ("record_orientation", "Record the assessment of the situation.", RecordOrientation)
_ACTION = ("choose_action", "Choose one concrete next action.", ChooseAction)
_DONE = ("phase_done", "Close this phase and hand off.", PhaseDone)
_UPDATE = ("update_plan", "Update the operator's own plan.", UpdatePlan)
_PLAN = ("set_plan", "Set the pending global plan steps.", SetPlan)
_CHECK = ("checkpoint", "Judge whether the objective is reached.", Checkpoint)
_READ = ("read_artifact", "Reopen a stored tool output.", ReadArtifact)


# --- Domain tools ---
@dataclass(frozen=True)
class Tool:
    """One dispatchable tool: its schema, its function, and who may call it."""

    name: str
    description: str
    args: type[BaseModel]
    fn: Callable[..., str]
    phases: frozenset[Phase]


READ_ONLY = frozenset({"scout", "striker", "operator"})
MUTATES = frozenset({"striker", "operator"})

TOOLS: tuple[Tool, ...] = (
    Tool("list_dir", "List entries in a directory.", ListDirArgs, list_dir, READ_ONLY),
    Tool("read_file", "Read a file's contents.", ReadFileArgs, read_file, READ_ONLY),
    Tool("write_file", "Create or overwrite a file.", WriteFileArgs, write_file, MUTATES),
    Tool("proc", "Run a command, send input, or peek at a tmux session.", ProcArgs, proc, MUTATES),
    Tool("proc_output", "Fetch a tmux session's current screen.", ProcOutputArgs, proc_output, MUTATES),
    Tool("proc_kill", "Terminate a tmux session.", ProcKillArgs, proc_kill, MUTATES),
    Tool("proc_status", "List every active tmux session.", ProcStatusArgs, proc_status, MUTATES),
)
BY_NAME = {tool.name: tool for tool in TOOLS}


def _control(phase: Phase, state: str) -> list[tuple[str, str, type[BaseModel]]]:
    """Control tools offered for this phase and state."""
    if phase == "global":
        return {"plan": [_PLAN], "checkpoint": [_CHECK]}[state]
    if state == "decide":
        return [_ACTION, _DONE, *([_UPDATE] if phase == "operator" else [])]
    return {"observe": [_OBSERVE], "orient": [_ORIENT], "act": [_READ]}[state]


def schemas(phase: Phase, state: str) -> list[dict[str, Any]]:
    """Tool specs for this phase and state: control tools, plus domain tools in act."""
    specs = _control(phase, state)
    if state == "act":
        specs = specs + [(t.name, t.description, t.args) for t in TOOLS if phase in t.phases]
    return [{"name": n, "description": d, "parameters": a.model_json_schema()} for n, d, a in specs]


def dispatch(phase: Phase, state: str, name: str, arguments: dict[str, Any]) -> str:
    """Run one domain tool call after checking it is allowed in this phase."""
    tool = BY_NAME.get(name)
    if tool is None:
        raise ValueError(f"unknown tool '{name}'")
    if state != "act":
        raise ValueError(f"tool '{name}' can only be dispatched in the act state")
    if phase not in tool.phases:
        raise ValueError(f"tool '{name}' is not allowed in phase '{phase}'")
    validated = tool.args.model_validate(arguments)
    return tool.fn(**validated.model_dump())
