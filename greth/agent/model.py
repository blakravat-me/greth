# greth/model.py
"""Model I/O: ask for tool calls, parse them, retry with an Error section when invalid."""

# Assumed contracts:
#   ChatOllama.invoke(prompt=[{"role", "content"}], tools=[schema]) -> [{"name", "arguments"}]
#       and it raises ValueError on malformed model output
#   policy.schemas(phase, state) -> [{"name", "description", "parameters"}]
#       phases: scout, striker, operator, and global (states plan, checkpoint)
import time

from greth.agent.context import render, section
from greth.agent.state import AgentState
from greth.agent.validation import validate
from greth.config import MAX_CONNECTION_ATTEMPTS, MAX_TOOL_CALL_ATTEMPTS, MAX_WAIT, PROMPT_DIR
from greth.llm.ollama import ChatOllama, LLMConnectionError
from greth.logging.logger import error
from greth.tools import policy

_llm: ChatOllama | None = None  # set once by main() from the CLI args


def configure(llm: ChatOllama) -> None:
    """Set the model client used by every request."""
    global _llm
    _llm = llm


def ask(prompt: list[dict], schemas: list[dict]) -> list[dict]:
    """Call the model; outages are waited out so that only Ctrl+C stops the loop."""
    if _llm is None:
        raise RuntimeError("model client is not configured; call configure() before requesting a model response")

    wait = 0.5
    for attempt in range(1, MAX_CONNECTION_ATTEMPTS + 1):
        try:
            return _llm.invoke(prompt=prompt, tools=schemas)
        except ValueError:  # malformed output: the caller retries with an Error section
            raise
        except LLMConnectionError as problem:  # server down, overloaded, or timed out
            error(f"llm attempt {attempt}/{MAX_CONNECTION_ATTEMPTS} {type(problem).__name__}: {str(problem)[:120]}")
            if attempt == MAX_CONNECTION_ATTEMPTS:
                raise RuntimeError(f"model connection failed after {attempt} attempts: {problem}") from problem
            time.sleep(wait)
            wait = min(wait * 2, MAX_WAIT)
    raise RuntimeError("model connection retry loop exited unexpectedly")


def request(state: AgentState, prompt_phase: str, state_name: str, parse=None, many: bool = False) -> list:
    """Ask the model for tool calls and retry with an Error section until they parse."""
    schemas = policy.schemas(prompt_phase, state_name)

    if not schemas:  # configuration bug, retrying cannot fix it
        raise RuntimeError(f"no tools offered for {prompt_phase}/{state_name}")

    system = (PROMPT_DIR / prompt_phase / f"{state_name}.md").read_text(encoding="utf-8")
    context = render(state, state_name)
    by_name = {schema["name"]: schema for schema in schemas}
    problem_text = ""
    attempts = 0
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
            attempts += 1
            problem_text = f"{type(problem).__name__}: {problem}"
            response_text = getattr(problem, "response_text", "")
            if response_text:
                problem_text += f"\nResponse text (not a tool call): {response_text}"
            problem_text = problem_text[:900]
            error(f"retry {prompt_phase}/{state_name} ({attempts}/{MAX_TOOL_CALL_ATTEMPTS}): {type(problem).__name__}")
            if attempts >= MAX_TOOL_CALL_ATTEMPTS:
                raise RuntimeError(
                    f"model failed to return a valid tool call for {prompt_phase}/{state_name} "
                    f"after {attempts} attempts: {problem}"
                ) from problem
