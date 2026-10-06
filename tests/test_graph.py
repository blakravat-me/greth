from langgraph.types import Command

import greth.agent.core as core
from greth.agent.state import new_state


def test_graph_ends_immediately_after_tool_error(monkeypatch):
    monkeypatch.setattr(core, "planner", lambda state: {})
    monkeypatch.setattr(core, "observe", lambda state: {})
    monkeypatch.setattr(core, "orient", lambda state: {})
    monkeypatch.setattr(core, "decide", lambda state: Command(goto="act"))
    monkeypatch.setattr(core, "act", lambda state: {"tool_error": True, "last_result": "failed"})
    monkeypatch.setattr(core, "checkpoint", lambda state: (_ for _ in ()).throw(AssertionError("must stop before checkpoint")))

    updates = list(
        core.build_graph().stream(
            new_state("test.local", "test", ""),
            {"recursion_limit": 20},
            stream_mode="updates",
        )
    )
    node_names = [node_name for update in updates for node_name in update]

    assert node_names[-1] == "act"
    assert "checkpoint" not in node_names
