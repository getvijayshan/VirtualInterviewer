"""Report-generation prompt (FL-07, ADR §4): a single "strict grader" call
over the full transcript, not per-turn scoring.
"""

from app.models import Candidate, InterviewSession, TranscriptTurn
from app.services.candidate_context import describe_target, summarize_resume

REPORT_TOOL = {
    "name": "record_interview_report",
    "description": "Record a structured scorecard for a completed interview.",
    "input_schema": {
        "type": "object",
        "properties": {
            "overall_score": {
                "type": "number",
                "description": "Overall performance, 0-10.",
            },
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "quality": {"type": "string", "enum": ["strong", "needs_work"]},
                        "note": {
                            "type": "string",
                            "description": (
                                "One concise, specific, actionable note. If 'needs_work', say "
                                "what a stronger answer would include. If 'strong', say what "
                                "specifically made it land. Do not restate the answer."
                            ),
                        },
                    },
                    "required": ["question", "quality", "note"],
                },
            },
            "communication_notes": {
                "type": "string",
                "description": "2-3 sentences on pacing, clarity, and structure of the candidate's speech.",
            },
        },
        "required": ["overall_score", "questions", "communication_notes"],
    },
}


def build_system_prompt(candidate: Candidate, session: InterviewSession) -> str:
    return (
        "You are a strict, fair technical interview grader. You will be given the full "
        "transcript of a spoken technical interview — questions asked and the candidate's "
        "transcribed answers. The candidate's speech was transcribed by an ASR system, so "
        "ignore minor transcription artifacts (missing punctuation, homophones, filler "
        "words) and judge intent, not exact phrasing.\n\n"
        f"Candidate resume summary:\n{summarize_resume(candidate.resume_parsed_json)}\n\n"
        f"{describe_target(session)}\n\n"
        "Evaluate the whole transcript in one pass — do not score turn by turn. For each "
        "question the candidate answered, judge its quality and give one specific, "
        "actionable note. Then give an overall score and a short note on communication. "
        "Be constructive but honest — this is meant to help the candidate improve, not "
        "just to praise them."
    )


def build_transcript_text(turns: list[TranscriptTurn]) -> str:
    lines: list[str] = []
    question_number = 0
    for turn in turns:
        if turn.role.value == "assistant":
            question_number += 1
            lines.append(f"Q{question_number}: {turn.content}")
        else:
            lines.append(f"A{question_number}: {turn.content}")
    return "\n".join(lines)
