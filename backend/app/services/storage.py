"""S3-compatible file storage."""

import boto3

from app.config import settings


def _client():
    kwargs = {}
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
    if settings.aws_secret_access_key:
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client("s3", **kwargs)


def _upload(key: str, data: bytes, content_type: str) -> str:
    _client().put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    if settings.s3_endpoint_url:
        return f"{settings.s3_endpoint_url.rstrip('/')}/{settings.s3_bucket}/{key}"
    return f"https://{settings.s3_bucket}.s3.amazonaws.com/{key}"


def upload_resume_file(candidate_id: str, filename: str, data: bytes, content_type: str) -> str:
    """Upload the raw resume file to S3, return its stored URL."""
    return _upload(f"resumes/{candidate_id}/{filename}", data, content_type)


def upload_interview_answer_audio(
    session_id: str, turn_index: int, data: bytes, content_type: str
) -> str:
    """Upload a candidate's recorded answer to S3 (kept for STT-quality
    debugging/reprocessing, see docs/Architecture-Decisions.md §6 —
    transcript_turns.audio_file_url). Return its stored URL."""
    ext = "webm"
    if content_type and "/" in content_type:
        ext = content_type.split("/")[-1].split(";")[0] or ext
    return _upload(f"interview-audio/{session_id}/{turn_index}.{ext}", data, content_type)
