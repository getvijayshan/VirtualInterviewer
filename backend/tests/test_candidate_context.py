import uuid

from app.models import InterviewSession, TargetType
from app.services.candidate_context import describe_target, summarize_resume


def test_summarize_resume_handles_none():
    assert "No structured resume data" in summarize_resume(None)


def test_summarize_resume_includes_skills_experience_projects_education():
    parsed = {
        "skills": ["Python", "SQL"],
        "experience": [{"role": "Engineer", "company": "Acme", "start_date": "2022", "end_date": "2024"}],
        "projects": [{"name": "Widget", "summary": "A widget."}],
        "education": [{"degree": "BSc CS", "institution": "State U"}],
    }
    text = summarize_resume(parsed)
    assert "Python, SQL" in text
    assert "Engineer at Acme" in text
    assert "2022 - 2024" in text
    assert "Widget" in text
    assert "State U" in text


def test_summarize_resume_handles_empty_dict():
    assert "No structured resume data" in summarize_resume({})


def test_describe_target_jd():
    session = InterviewSession(id=uuid.uuid4(), candidate_id=uuid.uuid4(), target_type=TargetType.jd, jd_text="We need a backend engineer.")
    assert "We need a backend engineer." in describe_target(session)


def test_describe_target_role():
    session = InterviewSession(id=uuid.uuid4(), candidate_id=uuid.uuid4(), target_type=TargetType.role, target_role="Backend Engineer")
    assert "Backend Engineer" in describe_target(session)


def test_describe_target_topic_uses_label_not_raw_value():
    session = InterviewSession(id=uuid.uuid4(), candidate_id=uuid.uuid4(), target_type=TargetType.topic, target_topic="system_design")
    result = describe_target(session)
    assert "System Design" in result
    assert "system_design" not in result
