import json
from types import SimpleNamespace

import openai
import pytest

from app.services import llm


class FakeCompletions:
    def __init__(self, response):
        self._response = response
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self._response


class FakeOpenAIClient:
    """Stand-in for openai.OpenAI — captures constructor kwargs and
    exposes a fake .chat.completions.create() so no real API/network call happens."""

    last_init_kwargs = None
    last_instance: "FakeOpenAIClient | None" = None
    next_response = None  # tests that only exercise _build_client don't need a response

    def __init__(self, **kwargs):
        FakeOpenAIClient.last_init_kwargs = kwargs
        completions = FakeCompletions(FakeOpenAIClient.next_response)
        self.chat = SimpleNamespace(completions=completions)
        FakeOpenAIClient.last_instance = self


def _fake_response(content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    usage = SimpleNamespace(prompt_tokens=100, completion_tokens=20)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


def _tool_call(name, arguments: dict):
    return SimpleNamespace(function=SimpleNamespace(name=name, arguments=json.dumps(arguments)))


@pytest.fixture(autouse=True)
def patch_openai(monkeypatch):
    monkeypatch.setattr(openai, "OpenAI", FakeOpenAIClient)


def test_build_client_uses_azure_endpoint_when_no_helicone_url(monkeypatch):
    monkeypatch.setattr(llm.settings, "helicone_base_url", "")
    monkeypatch.setattr(llm.settings, "helicone_api_key", "")
    monkeypatch.setattr(llm.settings, "azure_openai_api_key", "az-test")
    monkeypatch.setattr(
        llm.settings, "azure_openai_endpoint", "https://example.openai.azure.com/openai/v1"
    )

    llm._build_client({"Helicone-Property-Call-Type": "question_gen"})

    kwargs = FakeOpenAIClient.last_init_kwargs
    assert kwargs["api_key"] == "az-test"
    assert kwargs["base_url"] == "https://example.openai.azure.com/openai/v1"
    assert "api_version" not in kwargs
    assert kwargs["default_headers"] == {"Helicone-Property-Call-Type": "question_gen"}


def test_build_client_routes_through_helicone_when_configured(monkeypatch):
    monkeypatch.setattr(llm.settings, "helicone_base_url", "http://localhost:8585")
    monkeypatch.setattr(llm.settings, "helicone_api_key", "helicone-secret")
    monkeypatch.setattr(llm.settings, "azure_openai_api_key", "az-test")

    llm._build_client({"Helicone-Property-Call-Type": "report_gen"})

    kwargs = FakeOpenAIClient.last_init_kwargs
    assert kwargs["base_url"] == "http://localhost:8585"
    assert kwargs["default_headers"]["Helicone-Auth"] == "Bearer helicone-secret"
    assert kwargs["default_headers"]["Helicone-Property-Call-Type"] == "report_gen"


def test_create_message_tags_session_id_and_call_type(monkeypatch):
    FakeOpenAIClient.next_response = _fake_response(content="hi")
    monkeypatch.setattr(llm.settings, "helicone_base_url", "")
    monkeypatch.setattr(llm.settings, "helicone_api_key", "")

    llm.create_message(
        model="interview-deployment",
        system="be helpful",
        messages=[{"role": "user", "content": "hi"}],
        max_completion_tokens=100,
        call_type="question_gen",
        session_id="abc-123",
    )

    init_kwargs = FakeOpenAIClient.last_init_kwargs
    assert init_kwargs["default_headers"] == {
        llm.CALL_TYPE_HEADER: "question_gen",
        llm.SESSION_ID_HEADER: "abc-123",
    }


def test_create_message_omits_session_header_when_not_given(monkeypatch):
    FakeOpenAIClient.next_response = _fake_response(content="hi")
    monkeypatch.setattr(llm.settings, "helicone_base_url", "")
    monkeypatch.setattr(llm.settings, "helicone_api_key", "")

    llm.create_message(
        model="extraction-deployment",
        system="be helpful",
        messages=[{"role": "user", "content": "hi"}],
        max_completion_tokens=100,
        call_type="resume_extraction",
    )

    headers = FakeOpenAIClient.last_init_kwargs["default_headers"]
    assert llm.SESSION_ID_HEADER not in headers


def test_create_message_prepends_system_message(monkeypatch):
    FakeOpenAIClient.next_response = _fake_response(content="hi")
    monkeypatch.setattr(llm.settings, "helicone_base_url", "")
    monkeypatch.setattr(llm.settings, "helicone_api_key", "")

    llm.create_message(
        model="interview-deployment",
        system="sys prompt",
        messages=[{"role": "user", "content": "hi"}],
        max_completion_tokens=100,
        call_type="question_gen",
    )

    call_kwargs = FakeOpenAIClient.last_instance.chat.completions.last_kwargs
    assert call_kwargs["messages"][0] == {"role": "system", "content": "sys prompt"}
    assert call_kwargs["messages"][1] == {"role": "user", "content": "hi"}


def test_create_message_uses_max_completion_tokens_not_max_tokens(monkeypatch):
    FakeOpenAIClient.next_response = _fake_response(content="hi")
    monkeypatch.setattr(llm.settings, "helicone_base_url", "")
    monkeypatch.setattr(llm.settings, "helicone_api_key", "")

    llm.create_message(
        model="interview-deployment",
        system="sys",
        messages=[{"role": "user", "content": "hi"}],
        max_completion_tokens=123,
        call_type="question_gen",
    )

    call_kwargs = FakeOpenAIClient.last_instance.chat.completions.last_kwargs
    assert call_kwargs["max_completion_tokens"] == 123
    assert "max_tokens" not in call_kwargs


def test_create_message_forwards_tools_and_tool_choice(monkeypatch):
    FakeOpenAIClient.next_response = _fake_response(content=None, tool_calls=[])
    monkeypatch.setattr(llm.settings, "helicone_base_url", "")
    monkeypatch.setattr(llm.settings, "helicone_api_key", "")

    tool = {"type": "function", "function": {"name": "record_thing", "parameters": {"type": "object"}}}
    llm.create_message(
        model="extraction-deployment",
        system="sys",
        messages=[{"role": "user", "content": "x"}],
        max_completion_tokens=50,
        call_type="resume_extraction",
        tools=[tool],
        tool_choice={"type": "function", "function": {"name": "record_thing"}},
    )

    call_kwargs = FakeOpenAIClient.last_instance.chat.completions.last_kwargs
    assert call_kwargs["model"] == "extraction-deployment"
    assert call_kwargs["max_completion_tokens"] == 50
    assert call_kwargs["tools"] == [tool]
    assert call_kwargs["tool_choice"] == {"type": "function", "function": {"name": "record_thing"}}


def test_create_message_omits_tools_when_not_given(monkeypatch):
    FakeOpenAIClient.next_response = _fake_response(content="hi")
    monkeypatch.setattr(llm.settings, "helicone_base_url", "")
    monkeypatch.setattr(llm.settings, "helicone_api_key", "")

    llm.create_message(
        model="interview-deployment",
        system="sys",
        messages=[{"role": "user", "content": "x"}],
        max_completion_tokens=50,
        call_type="question_gen",
    )

    call_kwargs = FakeOpenAIClient.last_instance.chat.completions.last_kwargs
    assert "tools" not in call_kwargs
    assert "tool_choice" not in call_kwargs


def test_get_usage_includes_cached_tokens_when_present():
    usage = SimpleNamespace(
        prompt_tokens=500,
        completion_tokens=50,
        prompt_tokens_details=SimpleNamespace(cached_tokens=300),
    )
    response = SimpleNamespace(usage=usage)
    result = llm.get_usage(response)
    assert result == {
        "input_tokens": 500,
        "output_tokens": 50,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 300,
    }


def test_get_usage_defaults_cached_tokens_to_zero_when_absent():
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)
    response = SimpleNamespace(usage=usage)
    result = llm.get_usage(response)
    assert result["cache_creation_input_tokens"] == 0
    assert result["cache_read_input_tokens"] == 0


def test_extract_candidate_fields_returns_tool_arguments(monkeypatch):
    FakeOpenAIClient.next_response = _fake_response(
        content=None, tool_calls=[_tool_call("record_resume_fields", {"name": "Jane"})]
    )
    monkeypatch.setattr(llm.settings, "helicone_base_url", "")
    monkeypatch.setattr(llm.settings, "helicone_api_key", "")

    result = llm.extract_candidate_fields("some resume text")
    assert result == {"name": "Jane"}


def test_extract_candidate_fields_raises_when_no_tool_call_in_response(monkeypatch):
    FakeOpenAIClient.next_response = _fake_response(content=None, tool_calls=[])
    monkeypatch.setattr(llm.settings, "helicone_base_url", "")
    monkeypatch.setattr(llm.settings, "helicone_api_key", "")

    with pytest.raises(llm.ExtractionError):
        llm.extract_candidate_fields("some resume text")


def test_extract_candidate_fields_wraps_openai_error(monkeypatch):
    class RaisingCompletions:
        def create(self, **kwargs):
            raise openai.APIError("boom", request=SimpleNamespace(), body=None)

    class RaisingClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=RaisingCompletions())

    monkeypatch.setattr(openai, "OpenAI", RaisingClient)
    monkeypatch.setattr(llm.settings, "helicone_base_url", "")
    monkeypatch.setattr(llm.settings, "helicone_api_key", "")

    with pytest.raises(llm.ExtractionError):
        llm.extract_candidate_fields("some resume text")
