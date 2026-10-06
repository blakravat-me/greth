# greth/nodes.py
"""Graph nodes: plan -> observe -> orient -> decide -> act -> observe ... decide -> checkpoint."""

import functools
import json
import re
from typing import Literal

from langgraph.types import Command

from greth.agent.artifact import remember, save_artifact
from greth.agent.context import clip
from greth.agent.dispatch import dispatch
from greth.agent.model import request
from greth.agent.plans import complete_steps, replace_pending
from greth.agent.routing import route
from greth.agent.state import CLEARED, AgentState
from greth.agent.validation import parse_checkpoint, parse_decision, parse_observation, parse_orientation, parse_plan, texts
from greth.config import ARTIFACT_LINES, GLOBAL, PREVIEW_CHARS

_EXIT_CODE_RE = re.compile(r"\[(?:Exit code|Last command exit code):\s*(-?\d+)\]")


def _tool_output_error(output: str) -> bool:
    """Recognize explicit tool failures and failed shell-command exit statuses."""
    stripped = output.lstrip()
    if stripped.startswith(("[ERROR]", "ERROR ", "[BUSY]", "[TIMEOUT")):
        return True

    exit_match = _EXIT_CODE_RE.search(output)
    return exit_match is not None and int(exit_match.group(1)) != 0


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
    """Run tool calls in order, persist full results, and stop immediately on failure."""
    phase = state["phase"]
    calls = request(state, phase, "act", many=True)
    blocks, index, lines, results = [], [], [], []
    error_message = ""
    for call in calls:
        try:
            output = str(dispatch(phase, call))
            failed = _tool_output_error(output)
            status = "error" if failed else "ok"
        except Exception as problem:  # a failing tool is an observation, not a crash
            output, status = f"ERROR {type(problem).__name__}: {problem}", "error"
            failed = True
        reference = save_artifact(phase, output)
        preview = clip(json.dumps(call["arguments"], ensure_ascii=False), PREVIEW_CHARS)
        blocks.append(f"### {call['name']} [{reference}]\n```\n{output}\n```")
        results.append({"name": call["name"], "reference": reference, "output": output, "status": status})
        index.append(f"{reference}: {call['name']} {' '.join(output[:PREVIEW_CHARS].split())}")
        lines.append(f"{phase} {call['name']}({preview}): {status} [{reference}]")
        if failed:
            error_message = f"{call['name']} failed [{reference}]: {output[:500]}"
            break

    return {
        "last_result": "\n\n".join(blocks),
        "tool_results": results,
        "artifacts": (state["artifacts"] + index)[-ARTIFACT_LINES:],
        "journal": remember(state["journal"], lines),
        "tool_error": bool(error_message),
        "error_message": error_message,
    }
