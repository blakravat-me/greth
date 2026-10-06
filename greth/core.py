# greth/core.py
"""Graph wiring: the loop has no END, so it runs until the process is interrupted."""

from langgraph.graph import START, StateGraph

from greth.nodes import act, checkpoint, decide, observe, orient, planner
from greth.state import AgentState


def build_graph():
    """Wire plan, OODA nodes, and checkpoint into one endless loop."""
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
    graph.add_edge("act", "observe")
    return graph.compile()
