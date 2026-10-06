import httpx
import pytest

from greth.llm.ollama import ChatOllama, LLMConnectionError, LLMRequestError, LLMResponseError


def client_with_transport(handler, *, api_key="") -> ChatOllama:
    client = ChatOllama("test-model", "http://ollama.test", api_key=api_key)
    client._client.close()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    return client


def test_invoke_sends_bearer_token_and_returns_tool_call():
    seen = {}

    def handle(request):
        seen["authorization"] = request.headers.get("Authorization")
        return httpx.Response(
            200,
            json={"message": {"tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "README.md"}}}]}},
        )

    client = client_with_transport(handle, api_key="example-token")
    try:
        calls = client.invoke([{"role": "user", "content": "read the file"}], [{"name": "read_file"}])
    finally:
        client._client.close()

    assert seen["authorization"] == "Bearer example-token"
    assert calls == [{"name": "read_file", "arguments": {"path": "README.md"}}]


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_non_retryable_http_errors_are_reported_as_request_errors(status):
    client = client_with_transport(lambda request: httpx.Response(status, text="request rejected"))
    try:
        with pytest.raises(LLMRequestError, match=f"HTTP {status}"):
            client._post({})
    finally:
        client._client.close()


@pytest.mark.parametrize("status", [408, 429, 500, 503])
def test_transient_http_errors_remain_retryable(status):
    client = client_with_transport(lambda request: httpx.Response(status, text="try again"))
    try:
        with pytest.raises(LLMConnectionError, match=f"HTTP {status}"):
            client._post({})
    finally:
        client._client.close()


def test_no_tool_call_error_keeps_a_bounded_response_hint():
    client = client_with_transport(
        lambda request: httpx.Response(200, json={"message": {"content": "I should inspect the directory first."}})
    )
    try:
        with pytest.raises(LLMResponseError) as error:
            client.invoke([{"role": "user", "content": "inspect"}], [{"name": "list_dir"}])
    finally:
        client._client.close()

    assert error.value.response_text == "I should inspect the directory first."
