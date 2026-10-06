# main.py
"""CLI entry: scout/striker under the global plan, then the operator, until Ctrl+C."""

import argparse

from rich.panel import Panel
from rich.text import Text

from greth.agent.core import build_graph
from greth.agent.model import configure
from greth.agent.state import new_state
from greth.config import ARTIFACT_DIR, DEFAULT_API_KEY, DEFAULT_BASE_URL, DEFAULT_MODEL, RECURSION_LIMIT
from greth.llm.ollama import ChatOllama
from greth.logging.logger import error, info
from greth.ui.console import console


def _display_update(node_name: str, update: dict) -> None:
    """Display each tool's complete output and clearly mark failures."""
    if node_name != "act":
        return
    if update.get("last_result"):
        console.print(Panel(Text(update["last_result"]), title="Tool output", border_style="cyan"))
    if update.get("tool_error"):
        console.print(f"[bold red]Stopping after tool failure:[/bold red] {update['error_message']}")


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
    ensure_container()
    info(f"Running (artifacts: {ARTIFACT_DIR}). Press Ctrl+C to stop.")
    try:
        for chunk in build_graph().stream(initial, {"recursion_limit": RECURSION_LIMIT}, stream_mode="updates"):
            for node_name, update in chunk.items():
                update = update or {}
                info(f"[{node_name}] {((update.get('journal') or [''])[-1])}")
                _display_update(node_name, update)
                if node_name == "act" and update.get("tool_error"):
                    raise SystemExit(1)
    except KeyboardInterrupt:
        info("Stopped.")
    except Exception as problem:
        error(f"stopped: {type(problem).__name__}: {problem}")
        console.print(f"[bold red]Stopped due to an error:[/bold red] {problem}")
        raise SystemExit(1) from None
    finally:
        remove_container()


if __name__ == "__main__":
    main()
