"""Shared Azure OpenAI client wrapper, routed through self-hosted Helicone.

Per docs/Architecture-Decisions.md §4c/§5: every LLM call goes through this
module rather than the openai SDK directly, so usage tracking and the
Helicone gateway are configured in exactly one place. #7 (interview loop)
and #10 (report generation) should call create_message() the same way
extract_candidate_fields() below does.
"""

import json

import openai

from app.config import settings

CALL_TYPE_HEADER = "Helicone-Property-Call-Type"
SESSION_ID_HEADER = "Helicone-Property-Session-Id"


class ExtractionError(Exception):
    """Raised when the model doesn't return a usable structured extraction (FL-01.5)."""


def _build_client(extra_headers: dict[str, str]) -> openai.OpenAI:
    """Plain openai.OpenAI client pointed at Azure's v1 API surface
    (settings.azure_openai_endpoint, e.g. https://<resource>.openai.azure.com/openai/v1) —
    not openai.AzureOpenAI. This newer Azure surface is OpenAI-SDK-compatible and doesn't
    take/require an api_version param at all (2026-09-21, user-directed)."""
    kwargs: dict = {
        "api_key": settings.azure_openai_api_key,
        "base_url": settings.helicone_base_url or settings.azure_openai_endpoint,
    }

    headers = dict(extra_headers)
    if settings.helicone_api_key:
        headers["Helicone-Auth"] = f"Bearer {settings.helicone_api_key}"
    if headers:
        kwargs["default_headers"] = headers

    return openai.OpenAI(**kwargs)


def create_message(
    *,
    model: str,
    system: str,
    messages: list[dict],
    max_completion_tokens: int,
    call_type: str,
    session_id: str | None = None,
    tools: list[dict] | None = None,
    tool_choice: dict | None = None,
) -> openai.types.chat.ChatCompletion:
    """Single entry point for every LLM call in the app.

    `model` is the Azure deployment name (see settings.azure_openai_deployment_*),
    not a published model id. `call_type` (e.g. 'resume_extraction', 'question_gen',
    'report_gen') and `session_id` are sent as Helicone custom properties (FL-08.2)
    so per-session cost is queryable in Helicone without a separate usage table.

    `max_completion_tokens`, not `max_tokens` — the gpt-5 reasoning-model family
    rejects `max_tokens` outright (400 unsupported_parameter), confirmed live
    2026-09-21 against the real deployment.

    Prompt caching is automatic on Azure OpenAI for prompts over ~1024 tokens —
    no manual cache-breakpoint markup needed, unlike the prior Anthropic wrapper.
    """
    extra_headers = {CALL_TYPE_HEADER: call_type}
    if session_id:
        extra_headers[SESSION_ID_HEADER] = session_id

    client = _build_client(extra_headers)
    kwargs: dict = {
        "model": model,
        "messages": [{"role": "system", "content": system}, *messages],
        "max_completion_tokens": max_completion_tokens,
    }
    if tools:
        kwargs["tools"] = tools
    if tool_choice:
        kwargs["tool_choice"] = tool_choice

    return client.chat.completions.create(**kwargs)


def get_usage(response: openai.types.chat.ChatCompletion) -> dict[str, int]:
    """Token usage off a response, including the prompt-cache field (FL-09) —
    callers logging usage (once #7/#9 persist anything locally) should use
    this rather than reading response.usage directly, so the field set is
    consistent everywhere.

    Azure OpenAI/OpenAI caching is automatic and doesn't bill/report a
    separate "cache creation" cost the way Anthropic did — that field is
    always 0 here, kept only so callers don't need to branch on provider.
    """
    usage = response.usage
    cached_tokens = 0
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None:
        cached_tokens = getattr(details, "cached_tokens", 0) or 0
    return {
        "input_tokens": usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": cached_tokens,
    }


_RESUME_FIELDS_TOOL = {
    "type": "function",
    "function": {
        "name": "record_resume_fields",
        "description": "Record structured fields extracted from a candidate's resume.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "skills": {"type": "array", "items": {"type": "string"}},
                "experience": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "company": {"type": "string"},
                            "role": {"type": "string"},
                            "start_date": {"type": "string"},
                            "end_date": {"type": "string"},
                            "summary": {"type": "string"},
                        },
                        "required": ["company", "role"],
                    },
                },
                "education": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "institution": {"type": "string"},
                            "degree": {"type": "string"},
                            "year": {"type": "string"},
                        },
                        "required": ["institution"],
                    },
                },
                "projects": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "summary": {"type": "string"},
                        },
                        "required": ["name"],
                    },
                },
            },
            "required": ["skills", "experience", "education", "projects"],
        },
    },
}

_RESUME_EXTRACTION_SYSTEM_PROMPT = (
    "You extract structured fields from resume text. Only use information present "
    "in the text — never invent employers, dates, or skills. Leave a field empty "
    "(omit it, or use an empty string/array) rather than guessing."
)


def extract_candidate_fields(resume_text: str) -> dict:
    """Call the model to extract structured candidate fields from resume text.

    Raises ExtractionError on any failure — callers should treat this the same
    as a parsing failure (FL-01.5): persist what we have and route to manual entry,
    not crash.
    """
    try:
        response = create_message(
            model=settings.azure_openai_deployment_extraction,
            system=_RESUME_EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": resume_text}],
            max_completion_tokens=2048,
            call_type="resume_extraction",
            tools=[_RESUME_FIELDS_TOOL],
            tool_choice={"type": "function", "function": {"name": "record_resume_fields"}},
        )
    except openai.OpenAIError as exc:
        raise ExtractionError(f"Azure OpenAI error: {exc}") from exc

    message = response.choices[0].message
    for tool_call in message.tool_calls or []:
        if tool_call.function.name == "record_resume_fields":
            return json.loads(tool_call.function.arguments)

    raise ExtractionError("Model response did not include the expected tool call.")
