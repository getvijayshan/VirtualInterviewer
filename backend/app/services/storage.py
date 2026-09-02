"""S3-compatible file storage for raw resume uploads."""

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


def upload_resume_file(candidate_id: str, filename: str, data: bytes, content_type: str) -> str:
    """Upload the raw resume file to S3, return its stored URL."""
    key = f"resumes/{candidate_id}/{filename}"
    _client().put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    if settings.s3_endpoint_url:
        return f"{settings.s3_endpoint_url.rstrip('/')}/{settings.s3_bucket}/{key}"
    return f"https://{settings.s3_bucket}.s3.amazonaws.com/{key}"
