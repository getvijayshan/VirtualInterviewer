"""Shared prompt-building context: turning a candidate's resume and a
session's target into text for Claude. Used by both the interview loop
(app.services.interview_prompts) and report generation
(app.services.report_prompts) so the two don't drift independently.
"""

from app.constants import PREDEFINED_TOPICS
from app.models import Candidate, InterviewSession, TargetType

_TOPIC_LABELS = {t["value"]: t["label"] for t in PREDEFINED_TOPICS}


def summarize_resume(parsed: dict | None) -> str:
    if not parsed:
        return "No structured resume data available — treat as a mid-level candidate."

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


def describe_target(session: InterviewSession) -> str:
    if session.target_type == TargetType.jd:
        return f"Job description:\n{session.jd_text}"
    if session.target_type == TargetType.role:
        return f"Target role: {session.target_role}"
    if session.target_type == TargetType.topic:
        label = _TOPIC_LABELS.get(session.target_topic, session.target_topic)
        return f"Interview focus: {label} (topic-based practice, not tied to a specific job)"
    return ""
