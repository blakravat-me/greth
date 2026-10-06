# llm/ollama.py
"""Minimal Ollama client: native tool calling over /api/chat, no text-only path."""

from __future__ import annotations

import json
from typing import Any, TypedDict

import httpx

from greth_logging.logger import debug

REQUEST_TIMEOUT = 360.0  # read timeout in seconds
TEMPERATURE = 0.2
TOP_P = 0.9
TOP_K = 40
KEEP_ALIVE = "30m"
NUM_CTX = 16384
TOOL_NUM_PREDICT = 1024


class LLMConnectionError(RuntimeError):
    """Server unreachable, timed out, or unhealthy; the caller waits and retries."""


class LLMResponseError(ValueError):
    """Server answered but the reply is unusable; the caller retries with an Error section."""


class ToolCall(TypedDict):
    """One tool call as the agent consumes it."""

    name: str
    arguments: dict[str, Any]


def _inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Flatten $defs/$ref because Ollama's constrained decoding does not follow references."""
    defs = schema.get("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                target = walk(defs[node["$ref"].rsplit("/", 1)[-1]])
                extra = {key: walk(value) for key, value in node.items() if key != "$ref"}
                return {**target, **extra}

            return {key: walk(value) for key, value in node.items() if key != "$defs"}

        if isinstance(node, list):
            return [walk(value) for value in node]

        return node

    return walk(schema)


def _tool_spec(schema: dict[str, Any]) -> dict[str, Any]:
    """Turn a policy schema {name, description, parameters} into an Ollama tool spec."""
    parameters = schema.get("parameters") or {
        "type": "object",
        "properties": {},
    }

    return {
        "type": "function",
        "function": {
            "name": schema["name"],
            "description": schema.get("description", ""),
            "parameters": _inline_refs(parameters),
        },
    }


class ChatOllama:
    """Chat with native tool calling over /api/chat; one public method, invoke()."""

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str = "",
        timeout: float = REQUEST_TIMEOUT,
        think: bool = False,
    ) -> None:
        self.model = model
        self.endpoint = f"{base_url.rstrip('/')}/api/chat"
        self.think = think

        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

        self._client = httpx.Client(
            timeout=httpx.Timeout(
                connect=10.0,
                write=30.0,
                read=timeout,
                pool=10.0,
            )
        )

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST to Ollama; every server-side problem becomes LLMConnectionError."""
        try:
            response = self._client.post(
                self.endpoint,
                json=payload,
                headers=self._headers,
            )
            response.raise_for_status()

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            body = exc.response.text[:300]
            raise LLMConnectionError(f"HTTP {status}: {body}") from exc

        except httpx.TimeoutException as exc:
            raise LLMConnectionError(f"request timed out: {self.endpoint}") from exc

        except httpx.RequestError as exc:
            raise LLMConnectionError(f"request failed: {exc}") from exc

        try:
            data = response.json()

        except ValueError as exc:
            raise LLMConnectionError(f"invalid JSON body: {response.text[:300]}") from exc

        if not isinstance(data, dict):
            raise LLMConnectionError("response body is not a JSON object")

        return data

    @staticmethod
    def _parse(call: Any) -> ToolCall:
        """Read one raw tool call; arguments may arrive as an object or a JSON string."""
        function = call.get("function") if isinstance(call, dict) else None

        if not isinstance(function, dict) or not isinstance(function.get("name"), str):
            raise LLMResponseError("a tool call has no function name")

        name = function["name"]
        arguments = function.get("arguments") or {}

        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)

            except json.JSONDecodeError as exc:
                raise LLMResponseError(f"tool {name}: invalid JSON arguments: {exc}") from exc

        if not isinstance(arguments, dict):
            raise LLMResponseError(f"tool {name}: arguments must be an object")

        return {
            "name": name,
            "arguments": arguments,
        }

    def invoke(
        self,
        prompt: list[dict[str, str]],
        tools: list[dict[str, Any]],
    ) -> list[ToolCall]:
        """Send the prompt and return every tool call; the caller validates names and arguments."""
        payload = {
            "model": self.model,
            "messages": prompt,
            "stream": False,
            "think": self.think,
            "keep_alive": KEEP_ALIVE,
            "tools": [_tool_spec(schema) for schema in tools],
            "options": {
                "temperature": TEMPERATURE,
                "top_p": TOP_P,
                "top_k": TOP_K,
                "num_ctx": NUM_CTX,
                "num_predict": TOOL_NUM_PREDICT,
            },
        }

        debug(
            {
                "event": "ollama.request",
                "model": self.model,
                "tool_names": [tool["name"] for tool in tools],
            }
        )

        data = self._post(payload)

        message = data.get("message")
        message = message if isinstance(message, dict) else {}

        raw_calls = message.get("tool_calls")
        content = (message.get("content") or "")[:500]

        debug(
            {
                "event": "ollama.response",
                "tool_calls": raw_calls,
                "content": content,
            }
        )

        if not isinstance(raw_calls, list) or not raw_calls:
            cut = "; the output hit the token limit, answer shorter" if data.get("done_reason") == "length" else ""
            names = ", ".join(t["name"] for t in tools)
            raise LLMResponseError(f"the model returned no tool call; reply only by calling: {names}{cut}")

        return [self._parse(call) for call in raw_calls]
