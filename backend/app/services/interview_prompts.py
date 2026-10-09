"""System prompt construction for the interview loop (FL-05, ADR §4).

FL-09.1: the system prompt must be stable/deterministic across turns within a
session for the cache to hit — nothing here interpolates a timestamp, a
session ID, or anything else that changes turn to turn. session_id is only
ever attached as a Helicone header (see app.services.llm), never in the
prompt text itself.
"""

from app.models import Candidate, InterviewSession
from app.services.candidate_context import describe_target, summarize_resume


def build_system_prompt(candidate: Candidate, session: InterviewSession) -> str:
    return (
        "You are conducting a spoken technical interview. The candidate answers out "
        "loud and their speech is transcribed to text before you see it, so expect "
        "occasional transcription artifacts — interpret intent, don't nitpick phrasing.\n\n"
        f"Candidate resume summary:\n{summarize_resume(candidate.resume_parsed_json)}\n\n"
        f"{describe_target(session)}\n\n"
        "Rules:\n"
        "- Ask exactly one question at a time.\n"
        "- Mix theory, scenario-based, and project-experience-based questions, adapting "
        "difficulty to the candidate's apparent experience level from their resume.\n"
        "- Do not reveal correct answers, grade, or give feedback during the interview — "
        "that happens afterward in a separate report.\n"
        "- After each answer, use your judgment to either follow up on it or move to a "
        "new area — don't announce which you're doing.\n"
        "- Respond with ONLY the next interview question. No preamble, no numbering, "
        "no meta-commentary, no markdown formatting."
    )
