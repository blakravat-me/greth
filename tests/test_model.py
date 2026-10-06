import pytest

import greth.agent.model as model
from greth.config import MAX_TOOL_CALL_ATTEMPTS
from greth.llm.ollama import LLMConnectionError, LLMRequestError, LLMResponseError
from greth.tools import policy


def test_ask_fails_fast_when_model_is_not_configured(monkeypatch):
    monkeypatch.setattr(model, "_llm", None)

    with pytest.raises(RuntimeError, match="model client is not configured"):
        model.ask([], [])


def test_ask_does_not_retry_permanent_request_errors(monkeypatch):
    class RejectedClient:
        calls = 0

        def invoke(self, **kwargs):
            self.calls += 1
            raise LLMRequestError("HTTP 401: unauthorized")

    client = RejectedClient()
    monkeypatch.setattr(model, "_llm", client)

    with pytest.raises(LLMRequestError, match="HTTP 401"):
        model.ask([], [])

    assert client.calls == 1


def test_ask_stops_after_connection_retries(monkeypatch):
    monkeypatch.setattr(model, "MAX_CONNECTION_ATTEMPTS", 3)
    monkeypatch.setattr(model, "error", lambda message: None)
    monkeypatch.setattr(model.time, "sleep", lambda seconds: None)

    class OfflineClient:
        calls = 0

        def invoke(self, **kwargs):
            self.calls += 1
            raise LLMConnectionError("server unavailable")

    client = OfflineClient()
    monkeypatch.setattr(model, "_llm", client)

    with pytest.raises(RuntimeError, match="connection failed after 3 attempts"):
        model.ask([], [])

    assert client.calls == 3


def test_act_dispatches_a_model_tool_call(monkeypatch):
    import greth.agent.nodes as nodes

    call = {"name": "list_dir", "arguments": {"path": "."}}
    dispatched = []
    monkeypatch.setattr(nodes, "request", lambda *args, **kwargs: [call])
    monkeypatch.setattr(
        policy,
        "dispatch",
        lambda phase, state, name, arguments: dispatched.append((phase, state, name, arguments)) or "executed",
    )
    monkeypatch.setattr(nodes, "save_artifact", lambda phase, output: "artifact-1")
    monkeypatch.setattr(nodes, "remember", lambda journal, lines: journal + lines)

    result = nodes.act({"phase": "scout", "artifacts": [], "journal": []})

    assert dispatched == [("scout", "act", "list_dir", {"path": "."})]
    assert "executed" in result["last_result"]
    assert result["tool_error"] is False


def test_act_persists_failure_output_and_skips_remaining_calls(monkeypatch):
    import greth.agent.nodes as nodes

    calls = [
        {"name": "proc", "arguments": {"command": "false"}},
        {"name": "proc", "arguments": {"command": "should not run"}},
    ]
    dispatched = []
    monkeypatch.setattr(nodes, "request", lambda *args, **kwargs: calls)
    monkeypatch.setattr(
        nodes,
        "dispatch",
        lambda phase, call: dispatched.append(call) or "[Exit code: 2]",
    )
    monkeypatch.setattr(nodes, "save_artifact", lambda phase, output: "artifact-failed")
    monkeypatch.setattr(nodes, "remember", lambda journal, lines: journal + lines)

    result = nodes.act({"phase": "striker", "artifacts": [], "journal": []})

    assert dispatched == [calls[0]]
    assert result["tool_error"] is True
    assert "Exit code: 2" in result["last_result"]
    assert "artifact-failed" in result["error_message"]


@pytest.mark.parametrize("output", ["[ERROR] file missing", "[BUSY] session", "[TIMEOUT after 2s]", "[Exit code: 9]"])
def test_act_recognizes_tool_failure_outputs(output, monkeypatch):
    import greth.agent.nodes as nodes

    monkeypatch.setattr(nodes, "request", lambda *args, **kwargs: [{"name": "proc", "arguments": {}}])
    monkeypatch.setattr(nodes, "dispatch", lambda phase, call: output)
    monkeypatch.setattr(nodes, "save_artifact", lambda phase, text: "artifact-failed")
    monkeypatch.setattr(nodes, "remember", lambda journal, lines: journal + lines)

    result = nodes.act({"phase": "striker", "artifacts": [], "journal": []})

    assert result["tool_error"] is True


def test_request_retries_no_tool_call_with_response_hint(monkeypatch, tmp_path):
    prompt_dir = tmp_path / "prompts"
    prompt_path = prompt_dir / "scout" / "act.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("Use a tool.", encoding="utf-8")

    schema = {"name": "list_dir", "parameters": {"type": "object", "required": ["path"]}}
    monkeypatch.setattr(model, "PROMPT_DIR", prompt_dir)
    monkeypatch.setattr(model.policy, "schemas", lambda phase, state: [schema])
    monkeypatch.setattr(model, "render", lambda state, state_name: "Context")

    class RetryingClient:
        prompts = []

        def invoke(self, *, prompt, tools):
            self.prompts.append(prompt)
            if len(self.prompts) == 1:
                raise LLMResponseError("no tool call", response_text="I should inspect the directory.")
            return [{"name": "list_dir", "arguments": {"path": "."}}]

    client = RetryingClient()
    monkeypatch.setattr(model, "_llm", client)

    calls = model.request({"phase": "scout"}, "scout", "act", many=True)

    assert calls == [{"name": "list_dir", "arguments": {"path": "."}}]
    assert "I should inspect the directory." in client.prompts[1][1]["content"]


def test_request_stops_after_repeated_invalid_responses(monkeypatch, tmp_path):
    prompt_path = tmp_path / "scout" / "act.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("Use a tool.", encoding="utf-8")
    monkeypatch.setattr(model, "PROMPT_DIR", tmp_path)
    monkeypatch.setattr(model.policy, "schemas", lambda phase, state: [{"name": "list_dir", "parameters": {}}])
    monkeypatch.setattr(model, "render", lambda state, state_name: "Context")
    monkeypatch.setattr(model, "error", lambda message: None)

    class NoToolClient:
        calls = 0

        def invoke(self, **kwargs):
            self.calls += 1
            raise LLMResponseError("no tool call")

    client = NoToolClient()
    monkeypatch.setattr(model, "_llm", client)

    with pytest.raises(RuntimeError, match=f"after {MAX_TOOL_CALL_ATTEMPTS} attempts"):
        model.request({"phase": "scout"}, "scout", "act", many=True)

    assert client.calls == MAX_TOOL_CALL_ATTEMPTS


def test_cli_displays_full_tool_output(monkeypatch):
    from io import StringIO

    from rich.console import Console

    import greth.cli as cli
    import greth.ui.output as output_ui

    stream = StringIO()
    monkeypatch.setattr(output_ui, "console", Console(file=stream, force_terminal=False, color_system=None))

    cli._display_update(
        "act",
        {
            "tool_results": [
                {
                    "name": "list_dir",
                    "reference": "scout-ref",
                    "output": "README.md\nsrc/",
                    "status": "ok",
                }
            ],
            "tool_error": False,
        },
    )

    assert "README.md" in stream.getvalue()
    assert "src/" in stream.getvalue()
