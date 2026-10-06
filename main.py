# main.py
"""CLI entry: scout/striker under the global plan, then the operator, until Ctrl+C."""

import argparse

from config import ARTIFACT_DIR, DEFAULT_API_KEY, DEFAULT_BASE_URL, DEFAULT_MODEL, RECURSION_LIMIT
from greth.core import build_graph
from greth.model import configure
from greth.state import new_state
from greth_logging.logger import info
from llm.ollama import ChatOllama


def main() -> None:
    """Parse args, start the container, and stream the loop until interrupted."""
    from helpers.docker import ensure_container, remove_container

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
                info(f"[{node_name}] {((update or {}).get('journal') or [''])[-1]}")
    except KeyboardInterrupt:
        info("Stopped.")
    finally:
        remove_container()


if __name__ == "__main__":
    main()
