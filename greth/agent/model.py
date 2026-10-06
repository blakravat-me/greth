# greth/model.py
"""Model I/O: ask for tool calls, parse them, retry with an Error section when invalid."""

# Assumed contracts:
#   ChatOllama.invoke(prompt=[{"role", "content"}], tools=[schema]) -> [{"name", "arguments"}]
#       and it raises ValueError on malformed model output
#   policy.schemas(phase, state) -> [{"name", "description", "parameters"}]
#       phases: scout, striker, operator, and global (states plan, checkpoint)
import time

from config import MAX_WAIT, PROMPT_DIR
from greth.context import render, section
from greth.state import AgentState
from greth.validation import validate
from greth_logging.logger import error
from llm.ollama import ChatOllama
from tools import policy

_llm: ChatOllama | None = None  # set once by main() from the CLI args


def configure(llm: ChatOllama) -> None:
    """Set the model client used by every request."""
    global _llm
    _llm = llm


def ask(prompt: list[dict], schemas: list[dict]) -> list[dict]:
    """Call the model; outages are waited out so that only Ctrl+C stops the loop."""
    wait = 0.5
    while True:
        try:
            return _llm.invoke(prompt=prompt, tools=schemas)
        except ValueError:  # malformed output: the caller retries with an Error section
            raise
        except Exception as problem:  # server down, out of memory, timeout
            error(f"llm {type(problem).__name__}: {str(problem)[:120]}")
            time.sleep(wait)
            wait = min(wait * 2, MAX_WAIT)


def request(state: AgentState, prompt_phase: str, state_name: str, parse=None, many: bool = False) -> list:
    """Ask the model for tool calls and retry with an Error section until they parse."""
    schemas = policy.schemas(prompt_phase, state_name)

    if not schemas:  # configuration bug, retrying cannot fix it
        raise RuntimeError(f"no tools offered for {prompt_phase}/{state_name}")

    system = (PROMPT_DIR / prompt_phase / f"{state_name}.md").read_text(encoding="utf-8")
    context = render(state, state_name)
    by_name = {schema["name"]: schema for schema in schemas}
    problem_text = ""
    while True:
        prompt = [
            {"role": "system", "content": system},
            {"role": "user", "content": context + section("Error", problem_text)},
        ]
        try:
            calls = ask(prompt, schemas)
            if not calls:
                raise ValueError("the response had no tool call")
            if not many and len(calls) != 1:
                raise ValueError("exactly one tool call is required")
            for call in calls:
                validate(call, by_name)
            return [parse(call) for call in calls] if parse else calls
        except (ValueError, KeyError, TypeError) as problem:  # bad calls or missing arguments
            problem_text = f"{type(problem).__name__}: {problem}"[:300]
            error(f"retry {prompt_phase}/{state_name}: {problem_text}")
