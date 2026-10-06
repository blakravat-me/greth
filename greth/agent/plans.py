# greth/plans.py
"""Versioned plans: done steps are immutable, pending steps are replaced on replan."""


def complete_steps(plan: dict, ids: list[str], result: str) -> dict:
    """Mark pending steps done; steps that are already done are never changed."""
    steps = [
        {**step, "done": True, "result": result} if step["id"] in ids and not step["done"] else step for step in plan["steps"]
    ]
    return {**plan, "steps": steps}


def replace_pending(plan: dict, texts: list[str]) -> dict:
    """Start a new plan version: keep done steps and replace every pending step."""
    version = plan["version"] + 1
    kept = [step for step in plan["steps"] if step["done"]]
    fresh = [
        {"id": f"v{version}.{number}", "text": text, "done": False, "result": ""} for number, text in enumerate(texts, start=1)
    ]
    return {"version": version, "steps": kept + fresh}
