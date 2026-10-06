# greth/context.py
"""Bounded markdown context: bounded text in, tool call out."""

from config import LIMITS, PLAN_VIEW_DONE, SECTION_CHARS
from greth.routing import allowed
from greth.state import AgentState

HEADER_KEYS = ("target", "objective", "instruction", "plan", "phase", "handoff")
STATE_KEYS = {
    "observe": ("last_result", "journal", "artifacts"),
    "orient": ("observation", "journal"),
    "decide": ("orientation", "observation", "journal", "artifacts"),
    "act": ("decision", "artifacts"),
    "plan": ("replan_reason", "journal", "artifacts"),
    "checkpoint": ("journal", "artifacts"),
}


def bullets(items: list[str]) -> str:
    """Render items as a markdown list."""
    return "\n".join(f"- {item}" for item in items)


def subsection(title: str, items: list[str]) -> str:
    """Render a markdown sub-heading with a list, or nothing when the list is empty."""
    return f"\n\n### {title}\n{bullets(items)}" if items else ""


def clip(text: str, limit: int = SECTION_CHARS) -> str:
    """Cut text to the limit and say how long it was."""
    return text if len(text) <= limit else f"{text[:limit]}\n... [{len(text)} chars total]"


def section(title: str, text: str | None, limit: int = SECTION_CHARS) -> str:
    """Render one markdown section, or nothing when it is empty."""
    return f"## {title}\n{clip(text, limit)}\n\n" if text else ""


def plan_markdown(plan: dict) -> str:
    """Render pending steps first (clipping never hides them), then the recent done steps."""
    if not plan["steps"]:
        return ""
    done = [step for step in plan["steps"] if step["done"]]
    lines = [f"- [ ] {step['id']} {clip(step['text'], 160)}" for step in plan["steps"] if not step["done"]]
    lines += [f"- [x] {step['id']} {clip(step['text'], 80)} ({clip(step['result'], 120)})" for step in done[-PLAN_VIEW_DONE:]]
    if len(done) > PLAN_VIEW_DONE:
        lines.append(f"({len(done) - PLAN_VIEW_DONE} earlier steps done)")
    return f"Version {plan['version']}\n" + "\n".join(lines)


def render(state: AgentState, state_name: str) -> str:
    """Build the markdown context; the operator sees only its own plan, the rest the global one."""
    phase = state["phase"]
    plan = state["operator_plan"] if phase == "operator" else state["global_plan"]
    values = {
        **state,
        "plan": plan_markdown(plan),
        "phase": f"{phase}\n\nAllowed next phases: {', '.join(allowed(state))}",
    }
    sections = []
    for key in HEADER_KEYS + STATE_KEYS[state_name]:
        value = values.get(key)
        text = bullets(value) if isinstance(value, list) else value
        title = key.replace("_", " ").capitalize()
        sections.append(section(title, text, LIMITS.get(key, SECTION_CHARS)))
    return "".join(sections)
