# greth/nodes.py
"""Graph nodes: plan -> observe -> orient -> decide -> act -> observe ... decide -> checkpoint."""

import functools
import json
from typing import Literal

from langgraph.types import Command

from config import ARTIFACT_LINES, GLOBAL, LIMITS, PREVIEW_CHARS
from greth.artifact import remember, save_artifact
from greth.context import clip
from greth.dispatch import dispatch
from greth.model import request
from greth.plans import complete_steps, replace_pending
from greth.routing import route
from greth.state import CLEARED, AgentState
from greth.validation import parse_checkpoint, parse_decision, parse_observation, parse_orientation, parse_plan, texts


def planner(state: AgentState) -> dict:
    """Create or replan the global plan; done steps stay, pending steps are replaced."""
    steps = request(state, GLOBAL, "plan", parse_plan)[0]
    plan = replace_pending(state["global_plan"], steps)
    line = f"global plan v{plan['version']}: {state['replan_reason']}"
    return {"global_plan": plan, "replan_reason": "", "journal": remember(state["journal"], [line])}


def observe(state: AgentState) -> dict:
    """Record verified facts from the latest result."""
    return {"observation": request(state, state["phase"], "observe", parse_observation)[0]}


def orient(state: AgentState) -> dict:
    """Record the assessment of the situation."""
    return {"orientation": request(state, state["phase"], "orient", parse_orientation)[0]}


def decide(state: AgentState) -> Command[Literal["act", "observe", "checkpoint", "plan"]]:
    """Dispatch one decide call: act, update the operator plan, or finish the phase."""
    phase = state["phase"]
    call = request(state, phase, "decide", functools.partial(parse_decision, state))[0]
    name, arguments = call["name"], call["arguments"]
    if name == "choose_action":
        criteria = arguments["success_criteria"]
        decision = f"- Intent: {arguments['intent']}\n- Success criteria: {criteria}"
        return Command(goto="act", update={"decision": decision})
    summary = str(arguments.get("summary", "")).strip()
    if name == "update_plan":
        plan = complete_steps(state["operator_plan"], texts(arguments, "completed_steps"), summary)
        plan = replace_pending(plan, texts(arguments, "steps"))
        line = f"operator plan v{plan['version']}"
        update = {"operator_plan": plan, "journal": remember(state["journal"], [line])}
        return Command(goto="observe", update=update)
    if phase == "operator":
        objective, target = str(arguments["objective"]).strip(), arguments["next_phase"]
        line = f"operator done -> {target}, objective: {objective}"
        update = {
            "objective": objective,
            "phase": target,
            "handoff": summary,
            **CLEARED,
            "global_plan": {**state["global_plan"], "steps": []},  # a new objective, a fresh plan
            "replan_reason": f"new objective from the operator: {objective}",
            "journal": remember(state["journal"], [line]),
        }
        return Command(goto="plan", update=update)
    line = f"{phase} done -> checkpoint (wants {arguments['next_phase']})"
    update = {"chosen_phase": arguments["next_phase"], "handoff": summary, "journal": remember(state["journal"], [line])}
    return Command(goto="checkpoint", update=update)


def checkpoint(state: AgentState) -> Command[Literal["plan", "observe"]]:
    """Judge scout/striker progress; only a done objective at striker can lead to the operator."""
    parse = functools.partial(parse_checkpoint, state)
    arguments = request(state, GLOBAL, "checkpoint", parse)[0]
    done = arguments["objective_done"]
    plan = complete_steps(state["global_plan"], texts(arguments, "completed_steps"), state["handoff"])
    target = route(state["phase"], state["chosen_phase"], done)
    reason = "" if done else str(arguments.get("replan_reason", "")).strip()
    if not done and not reason and all(step["done"] for step in plan["steps"]):
        reason = "all plan steps are done but the objective is not done"
    line = f"checkpoint {state['phase']}: objective_done={done}, next={target}"
    update = {
        "global_plan": plan,
        "phase": target,
        "replan_reason": reason,
        **CLEARED,
        "reached": state["reached"] or target == "operator",
        "handoff": str(arguments["evidence"]) if target == "operator" else state["handoff"],
        "journal": remember(state["journal"], [line]),
    }
    return Command(goto="plan" if reason else "observe", update=update)


def act(state: AgentState) -> dict:
    """Dispatch the model's tool calls; keep full outputs as artifacts, a preview in state."""
    phase = state["phase"]
    calls = request(state, phase, "act", many=True)
    share = max(LIMITS["last_result"] // len(calls) - 100, 100)  # every call keeps a visible slice
    blocks, index, lines = [], [], []
    for call in calls:
        try:
            output, status = str(dispatch(phase, call)), "ok"
        except Exception as problem:  # a failing tool is an observation, not a crash
            output, status = f"ERROR {type(problem).__name__}: {problem}", "error"
        reference = save_artifact(phase, output)
        preview = clip(json.dumps(call["arguments"], ensure_ascii=False), PREVIEW_CHARS)
        blocks.append(f"### {call['name']} [{reference}]\n```\n{clip(output, share)}\n```")
        index.append(f"{reference}: {call['name']} {' '.join(output[:PREVIEW_CHARS].split())}")
        lines.append(f"{phase} {call['name']}({preview}): {status} [{reference}]")
    return {
        "last_result": "\n\n".join(blocks),
        "artifacts": (state["artifacts"] + index)[-ARTIFACT_LINES:],
        "journal": remember(state["journal"], lines),
    }
