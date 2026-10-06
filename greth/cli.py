# main.py
"""CLI entry: scout/striker under the global plan, then the operator, until Ctrl+C."""

import argparse

from greth.agent.core import build_graph
from greth.agent.model import configure
from greth.agent.state import new_state
from greth.config import ARTIFACT_DIR, DEFAULT_API_KEY, DEFAULT_BASE_URL, DEFAULT_MODEL, RECURSION_LIMIT
from greth.llm.ollama import ChatOllama
from greth.logging.logger import error, info
from greth.ui.console import console
from greth.ui.output import out_error, out_tool_result


def _display_update(node_name: str, update: dict) -> None:
    """Display each tool's complete output and clearly mark failures."""
    if node_name != "act":
        return
    for result in update.get("tool_results", []):
        out_tool_result(result["name"], result["reference"], result["output"], failed=result["status"] == "error")
    if update.get("tool_error"):
        out_error(f"Stopping after tool failure: {update['error_message']}")


def main() -> None:
    """Parse args, start the container, and stream the loop until interrupted."""
    from greth.runtime.docker import ensure_container, remove_container

    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--objective", required=True)
    parser.add_argument("--instruction", default="")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    args = parser.parse_args()

    configure(ChatOllama(model=args.model, base_url=args.base_url, api_key=args.api_key))
    initial = new_state(args.target, args.objective, args.instruction)
    console.print(f"[bold cyan]GRETH[/bold cyan]  Artifacts: [dim]{ARTIFACT_DIR}[/dim]")
    console.print("[dim]Press Ctrl+C to stop.[/dim]")
    try:
        ensure_container()
        for chunk in build_graph().stream(initial, {"recursion_limit": RECURSION_LIMIT}, stream_mode="updates"):
            for node_name, update in chunk.items():
                update = update or {}
                message = (update.get("journal") or [""])[-1]
                info(f"[{node_name}] {message}")
                if node_name != "act" and message:
                    console.print(f"[dim][{node_name}][/dim] {message}")
                _display_update(node_name, update)
                if node_name == "act" and update.get("tool_error"):
                    raise SystemExit(1)
    except KeyboardInterrupt:
        info("Stopped.")
    except Exception as problem:
        error(f"stopped: {type(problem).__name__}: {problem}")
        out_error(str(problem))
        raise SystemExit(1) from None
    finally:
        remove_container()


if __name__ == "__main__":
    main()
