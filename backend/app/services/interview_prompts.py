"""System prompt construction for the interview loop (FL-05, ADR §4).

FL-09.1: the system prompt must be stable/deterministic across turns within a
session for the cache to hit — nothing here interpolates a timestamp, a
session ID, or anything else that changes turn to turn. session_id is only
ever attached as a Helicone header (see app.services.llm), never in the
prompt text itself.
"""

from app.constants import PREDEFINED_TOPICS
from app.models import Candidate, InterviewSession, TargetType

_TOPIC_LABELS = {t["value"]: t["label"] for t in PREDEFINED_TOPICS}


def _summarize_resume(parsed: dict | None) -> str:
    if not parsed:
        return "No structured resume data available — ask general questions calibrated to a mid-level candidate."

    lines: list[str] = []

    skills = parsed.get("skills") or []
    if skills:
        lines.append("Skills: " + ", ".join(skills))

    for exp in parsed.get("experience") or []:
        dates = " - ".join(filter(None, [exp.get("start_date"), exp.get("end_date")]))
        line = f"- {exp.get('role', '')} at {exp.get('company', '')}"
        if dates:
            line += f" ({dates})"
        if exp.get("summary"):
            line += f": {exp['summary']}"
        lines.append(line)

    for project in parsed.get("projects") or []:
        line = f"- Project: {project.get('name', '')}"
        if project.get("summary"):
            line += f" — {project['summary']}"
        lines.append(line)

    for edu in parsed.get("education") or []:
        line = f"- {edu.get('degree', '')} at {edu.get('institution', '')}".strip()
        if line != "-":
            lines.append(line)

    return "\n".join(lines) if lines else "No structured resume data available."


def _describe_target(session: InterviewSession) -> str:
    if session.target_type == TargetType.jd:
        return f"Job description:\n{session.jd_text}"
    if session.target_type == TargetType.role:
        return f"Target role: {session.target_role}"
    if session.target_type == TargetType.topic:
        label = _TOPIC_LABELS.get(session.target_topic, session.target_topic)
        return f"Interview focus: {label} (topic-based practice, not tied to a specific job)"
    return ""


def build_system_prompt(candidate: Candidate, session: InterviewSession) -> str:
    return (
        "You are conducting a spoken technical interview. The candidate answers out "
        "loud and their speech is transcribed to text before you see it, so expect "
        "occasional transcription artifacts — interpret intent, don't nitpick phrasing.\n\n"
        f"Candidate resume summary:\n{_summarize_resume(candidate.resume_parsed_json)}\n\n"
        f"{_describe_target(session)}\n\n"
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
