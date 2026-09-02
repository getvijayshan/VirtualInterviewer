"""Claude-backed structured extraction from resume text (FL-01.4).

NOTE: not yet routed through Helicone (see issue #6) — this talks to the
Anthropic API directly. When #6 lands, only `_client()` needs to change
(base_url + auth header), the extraction logic here stays the same.
"""

import anthropic

from app.config import settings

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

_SYSTEM_PROMPT = (
    "You extract structured fields from resume text. Only use information present "
    "in the text — never invent employers, dates, or skills. Leave a field empty "
    "(omit it, or use an empty string/array) rather than guessing."
)


class ExtractionError(Exception):
    """Raised when Claude doesn't return a usable structured extraction (FL-01.5)."""


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def extract_candidate_fields(resume_text: str) -> dict:
    """Call Claude to extract structured candidate fields from resume text.

    Raises ExtractionError on any failure — callers should treat this the same
    as a parsing failure (FL-01.5): persist what we have and route to manual entry,
    not crash.
    """
    try:
        response = _client().messages.create(
            model=settings.anthropic_model_extraction,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            tools=[_RESUME_FIELDS_TOOL],
            tool_choice={"type": "tool", "name": "record_resume_fields"},
            messages=[{"role": "user", "content": resume_text}],
        )
    except anthropic.APIError as exc:
        raise ExtractionError(f"Anthropic API error: {exc}") from exc

    for block in response.content:
        if block.type == "tool_use" and block.name == "record_resume_fields":
            return block.input

    raise ExtractionError("Claude response did not include the expected tool call.")
