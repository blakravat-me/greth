# greth/core.py
"""Graph wiring: the loop ends on failure and otherwise runs until interrupted."""

from langgraph.graph import END, START, StateGraph

from greth.agent.nodes import act, checkpoint, decide, observe, orient, planner
from greth.agent.state import AgentState


def after_act(state: AgentState) -> str:
    """Stop after the act node when any tool reported an error."""
    return "stop" if state.get("tool_error", False) else "observe"


def build_graph():
    """Wire plan, OODA nodes, and checkpoint; route tool failures to END."""
    graph = StateGraph(AgentState)
    for name, function in (
        ("plan", planner),
        ("observe", observe),
        ("orient", orient),
        ("decide", decide),
        ("act", act),
        ("checkpoint", checkpoint),
    ):
        graph.add_node(name, function)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "observe")
    graph.add_edge("observe", "orient")
    graph.add_edge("orient", "decide")
    graph.add_conditional_edges(
        "act",
        after_act,
        {"stop": END, "observe": "observe"},
    )
    return graph.compile()
