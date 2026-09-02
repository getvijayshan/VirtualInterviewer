"""Shared Anthropic client wrapper, routed through self-hosted Helicone.

Per docs/Architecture-Decisions.md §5: every Claude call goes through this
module rather than the Anthropic SDK directly, so usage tracking and the
Helicone gateway are configured in exactly one place. #7 (interview loop)
and #10 (report generation) should call create_message() the same way
extract_candidate_fields() below does.
"""

import anthropic

from app.config import settings

CALL_TYPE_HEADER = "Helicone-Property-Call-Type"
SESSION_ID_HEADER = "Helicone-Property-Session-Id"


class ExtractionError(Exception):
    """Raised when Claude doesn't return a usable structured extraction (FL-01.5)."""


def _build_client(extra_headers: dict[str, str]) -> anthropic.Anthropic:
    kwargs: dict = {"api_key": settings.anthropic_api_key}
    if settings.helicone_base_url:
        kwargs["base_url"] = settings.helicone_base_url

    headers = dict(extra_headers)
    if settings.helicone_api_key:
        headers["Helicone-Auth"] = f"Bearer {settings.helicone_api_key}"
    if headers:
        kwargs["default_headers"] = headers

    return anthropic.Anthropic(**kwargs)


def create_message(
    *,
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int,
    call_type: str,
    session_id: str | None = None,
    tools: list[dict] | None = None,
    tool_choice: dict | None = None,
) -> anthropic.types.Message:
    """Single entry point for every Claude call in the app.

    `call_type` (e.g. 'resume_extraction', 'question_gen', 'report_gen') and
    `session_id` are sent as Helicone custom properties (FL-08.2) so
    per-session cost is queryable in Helicone without a separate usage table.
    """
    extra_headers = {CALL_TYPE_HEADER: call_type}
    if session_id:
        extra_headers[SESSION_ID_HEADER] = session_id

    client = _build_client(extra_headers)
    kwargs: dict = {
        "model": model,
        "system": system,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if tools:
        kwargs["tools"] = tools
    if tool_choice:
        kwargs["tool_choice"] = tool_choice

    return client.messages.create(**kwargs)


def get_usage(response: anthropic.types.Message) -> dict[str, int]:
    """Token usage off a response, including prompt-cache fields (FL-09) —
    callers logging usage (once #7/#9 persist anything locally) should use
    this rather than reading response.usage directly, so the field set is
    consistent everywhere."""
    usage = response.usage
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
    }


_RESUME_FIELDS_TOOL = {
    "name": "record_resume_fields",
    "description": "Record structured fields extracted from a candidate's resume.",
    "input_schema": {
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
}

_RESUME_EXTRACTION_SYSTEM_PROMPT = (
    "You extract structured fields from resume text. Only use information present "
    "in the text — never invent employers, dates, or skills. Leave a field empty "
    "(omit it, or use an empty string/array) rather than guessing."
)


def extract_candidate_fields(resume_text: str) -> dict:
    """Call Claude to extract structured candidate fields from resume text.

    Raises ExtractionError on any failure — callers should treat this the same
    as a parsing failure (FL-01.5): persist what we have and route to manual entry,
    not crash.
    """
    try:
        response = create_message(
            model=settings.anthropic_model_extraction,
            system=_RESUME_EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": resume_text}],
            max_tokens=2048,
            call_type="resume_extraction",
            tools=[_RESUME_FIELDS_TOOL],
            tool_choice={"type": "tool", "name": "record_resume_fields"},
        )
    except anthropic.APIError as exc:
        raise ExtractionError(f"Anthropic API error: {exc}") from exc

    for block in response.content:
        if block.type == "tool_use" and block.name == "record_resume_fields":
            return block.input

    raise ExtractionError("Claude response did not include the expected tool call.")
