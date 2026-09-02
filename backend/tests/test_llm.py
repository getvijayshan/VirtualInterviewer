from types import SimpleNamespace

import anthropic
import pytest

from app.services import llm


class FakeMessages:
    def __init__(self, response):
        self._response = response
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self._response


class FakeAnthropicClient:
    """Stand-in for anthropic.Anthropic — captures constructor kwargs and
    exposes a fake .messages.create() so no real API/network call happens."""

    last_init_kwargs = None
    last_instance: "FakeAnthropicClient | None" = None
    next_response = None  # tests that only exercise _build_client don't need a response

    def __init__(self, **kwargs):
        FakeAnthropicClient.last_init_kwargs = kwargs
        self.messages = FakeMessages(FakeAnthropicClient.next_response)
        FakeAnthropicClient.last_instance = self


def _fake_response(content):
    usage = SimpleNamespace(input_tokens=100, output_tokens=20)
    return SimpleNamespace(content=content, usage=usage)


@pytest.fixture(autouse=True)
def patch_anthropic(monkeypatch):
    monkeypatch.setattr(anthropic, "Anthropic", FakeAnthropicClient)


def test_build_client_calls_anthropic_directly_when_no_helicone_url(monkeypatch):
    monkeypatch.setattr(llm.settings, "helicone_base_url", "")
    monkeypatch.setattr(llm.settings, "helicone_api_key", "")
    monkeypatch.setattr(llm.settings, "anthropic_api_key", "sk-test")

    llm._build_client({"Helicone-Property-Call-Type": "question_gen"})

    kwargs = FakeAnthropicClient.last_init_kwargs
    assert kwargs["api_key"] == "sk-test"
    assert "base_url" not in kwargs
    assert kwargs["default_headers"] == {"Helicone-Property-Call-Type": "question_gen"}


def test_build_client_routes_through_helicone_when_configured(monkeypatch):
    monkeypatch.setattr(llm.settings, "helicone_base_url", "http://localhost:8585")
    monkeypatch.setattr(llm.settings, "helicone_api_key", "helicone-secret")
    monkeypatch.setattr(llm.settings, "anthropic_api_key", "sk-test")

    llm._build_client({"Helicone-Property-Call-Type": "report_gen"})

    kwargs = FakeAnthropicClient.last_init_kwargs
    assert kwargs["base_url"] == "http://localhost:8585"
    assert kwargs["default_headers"]["Helicone-Auth"] == "Bearer helicone-secret"
    assert kwargs["default_headers"]["Helicone-Property-Call-Type"] == "report_gen"


def test_create_message_tags_session_id_and_call_type(monkeypatch):
    FakeAnthropicClient.next_response = _fake_response(content=[])
    monkeypatch.setattr(llm.settings, "helicone_base_url", "")
    monkeypatch.setattr(llm.settings, "helicone_api_key", "")

    llm.create_message(
        model="claude-sonnet-5",
        system="be helpful",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=100,
        call_type="question_gen",
        session_id="abc-123",
    )

    init_kwargs = FakeAnthropicClient.last_init_kwargs
    assert init_kwargs["default_headers"] == {
        llm.CALL_TYPE_HEADER: "question_gen",
        llm.SESSION_ID_HEADER: "abc-123",
    }


def test_create_message_omits_session_header_when_not_given(monkeypatch):
    FakeAnthropicClient.next_response = _fake_response(content=[])
    monkeypatch.setattr(llm.settings, "helicone_base_url", "")
    monkeypatch.setattr(llm.settings, "helicone_api_key", "")

    llm.create_message(
        model="claude-sonnet-5",
        system="be helpful",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=100,
        call_type="resume_extraction",
    )

    headers = FakeAnthropicClient.last_init_kwargs["default_headers"]
    assert llm.SESSION_ID_HEADER not in headers


def test_create_message_forwards_tools_and_tool_choice(monkeypatch):
    FakeAnthropicClient.next_response = _fake_response(content=[])
    monkeypatch.setattr(llm.settings, "helicone_base_url", "")
    monkeypatch.setattr(llm.settings, "helicone_api_key", "")

    tool = {"name": "record_thing", "input_schema": {"type": "object"}}
    llm.create_message(
        model="claude-sonnet-5",
        system="sys",
        messages=[{"role": "user", "content": "x"}],
        max_tokens=50,
        call_type="resume_extraction",
        tools=[tool],
        tool_choice={"type": "tool", "name": "record_thing"},
    )

    call_kwargs = FakeAnthropicClient.last_instance.messages.last_kwargs
    assert call_kwargs["model"] == "claude-sonnet-5"
    assert call_kwargs["max_tokens"] == 50
    assert call_kwargs["tools"] == [tool]
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": "record_thing"}


def test_create_message_omits_tools_when_not_given(monkeypatch):
    FakeAnthropicClient.next_response = _fake_response(content=[])
    monkeypatch.setattr(llm.settings, "helicone_base_url", "")
    monkeypatch.setattr(llm.settings, "helicone_api_key", "")

    llm.create_message(
        model="claude-sonnet-5",
        system="sys",
        messages=[{"role": "user", "content": "x"}],
        max_tokens=50,
        call_type="question_gen",
    )

    call_kwargs = FakeAnthropicClient.last_instance.messages.last_kwargs
    assert "tools" not in call_kwargs
    assert "tool_choice" not in call_kwargs


def test_get_usage_includes_cache_fields_when_present():
    usage = SimpleNamespace(
        input_tokens=500,
        output_tokens=50,
        cache_creation_input_tokens=200,
        cache_read_input_tokens=300,
    )
    response = SimpleNamespace(usage=usage)
    result = llm.get_usage(response)
    assert result == {
        "input_tokens": 500,
        "output_tokens": 50,
        "cache_creation_input_tokens": 200,
        "cache_read_input_tokens": 300,
    }


def test_get_usage_defaults_cache_fields_to_zero_when_absent():
    usage = SimpleNamespace(input_tokens=10, output_tokens=5)
    response = SimpleNamespace(usage=usage)
    result = llm.get_usage(response)
    assert result["cache_creation_input_tokens"] == 0
    assert result["cache_read_input_tokens"] == 0


def test_extract_candidate_fields_returns_tool_input(monkeypatch):
    tool_block = SimpleNamespace(type="tool_use", name="record_resume_fields", input={"name": "Jane"})
    FakeAnthropicClient.next_response = _fake_response(content=[tool_block])
    monkeypatch.setattr(llm.settings, "helicone_base_url", "")
    monkeypatch.setattr(llm.settings, "helicone_api_key", "")

    result = llm.extract_candidate_fields("some resume text")
    assert result == {"name": "Jane"}


def test_extract_candidate_fields_raises_when_no_tool_call_in_response(monkeypatch):
    FakeAnthropicClient.next_response = _fake_response(content=[])
    monkeypatch.setattr(llm.settings, "helicone_base_url", "")
    monkeypatch.setattr(llm.settings, "helicone_api_key", "")

    with pytest.raises(llm.ExtractionError):
        llm.extract_candidate_fields("some resume text")


def test_extract_candidate_fields_wraps_anthropic_api_error(monkeypatch):
    def _raise(**kwargs):
        raise anthropic.APIError("boom", request=None, body=None)

    class RaisingMessages:
        def create(self, **kwargs):
            _raise(**kwargs)

    class RaisingClient:
        def __init__(self, **kwargs):
            self.messages = RaisingMessages()

    monkeypatch.setattr(anthropic, "Anthropic", RaisingClient)
    monkeypatch.setattr(llm.settings, "helicone_base_url", "")
    monkeypatch.setattr(llm.settings, "helicone_api_key", "")

    with pytest.raises(llm.ExtractionError):
        llm.extract_candidate_fields("some resume text")
