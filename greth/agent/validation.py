# greth/validation.py
"""Validate and parse tool calls; any ValueError makes the model retry with an Error section."""

# Control tools, parsed here and never dispatched:
#   record_observation(facts, gaps)          record_orientation(assessment, risks, options)
#   choose_action(intent, success_criteria)
#   phase_done(summary, next_phase, objective)    objective: operator only, replaces the objective
#   update_plan(steps, completed_steps, summary)  operator decide only
#   set_plan(steps)                               global/plan
#   checkpoint(objective_done, evidence, completed_steps, replan_reason)   global/checkpoint
from greth.context import subsection
from greth.routing import allowed
from greth.state import AgentState


def validate(call: dict, by_name: dict) -> None:
    """Check that the tool was offered by the policy and that required arguments are present."""
    schema = by_name.get(call["name"])
    if schema is None:
        raise ValueError(f"tool {call['name']} is not available")
    required = schema.get("parameters", {}).get("required", [])
    missing = [key for key in required if key not in call["arguments"]]
    if missing:
        raise ValueError(f"tool {call['name']} is missing arguments {missing}")


def expect(call: dict, name: str) -> dict:
    """Return the arguments of a call after checking it is the expected control tool."""
    if call["name"] != name:
        raise ValueError(f"expected tool {name}, got {call['name']}")
    return call["arguments"]


def texts(arguments: dict, key: str) -> list[str]:
    """Read an optional list of strings from tool arguments."""
    value = arguments.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{key} must be a list of strings")
    return value


def check_steps(arguments: dict, allow_empty: bool) -> list[str]:
    """Read the plan step texts; a new global plan must not be empty."""
    steps = texts(arguments, "steps")
    if (not steps and not allow_empty) or not all(step.strip() for step in steps):
        raise ValueError("steps must be a list of non-empty strings")
    return steps


def check_ids(plan: dict, ids: list[str]) -> None:
    """Reject step ids that do not exist in the plan."""
    unknown = set(ids) - {step["id"] for step in plan["steps"]}
    if unknown:
        raise ValueError(f"unknown step ids {sorted(unknown)}")


def parse_observation(call: dict) -> str:
    """Turn a record_observation call into a markdown observation."""
    arguments = expect(call, "record_observation")
    facts = subsection("Facts", texts(arguments, "facts"))
    return (facts + subsection("Gaps", texts(arguments, "gaps"))).strip()


def parse_orientation(call: dict) -> str:
    """Turn a record_orientation call into a markdown orientation."""
    arguments = expect(call, "record_orientation")
    risks = subsection("Risks", texts(arguments, "risks"))
    return str(arguments["assessment"]) + risks + subsection("Options", texts(arguments, "options"))


def parse_plan(call: dict) -> list[str]:
    """Return the step texts of a set_plan call."""
    return check_steps(expect(call, "set_plan"), allow_empty=False)


def parse_decision(state: AgentState, call: dict) -> dict:
    """Accept only decide calls that respect transitions and operator plan isolation."""
    phase, name, arguments = state["phase"], call["name"], call["arguments"]
    if name == "phase_done":
        options = allowed(state)
        if arguments["next_phase"] not in options:
            raise ValueError(f"next_phase must be one of {list(options)}")
        if phase == "operator" and not str(arguments.get("objective", "")).strip():
            raise ValueError("the operator must give the new objective")
    elif name == "update_plan":
        if phase != "operator":
            raise ValueError("update_plan is only for the operator phase")
        check_steps(arguments, allow_empty=True)
        check_ids(state["operator_plan"], texts(arguments, "completed_steps"))
    elif name != "choose_action":
        raise ValueError(f"tool {name} is not a decide tool")
    return call


def parse_checkpoint(state: AgentState, call: dict) -> dict:
    """Accept only well-formed checkpoint arguments: strict boolean, known ids, evidence."""
    arguments = expect(call, "checkpoint")
    if not isinstance(arguments["objective_done"], bool):
        raise ValueError("objective_done must be true or false")
    if arguments["objective_done"] and not str(arguments.get("evidence", "")).strip():
        raise ValueError("evidence is required when the objective is done")
    check_ids(state["global_plan"], texts(arguments, "completed_steps"))
    return arguments
