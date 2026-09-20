"""Azure Blob Storage-backed file storage (switched from S3, 2026-09-20 —
see docs/Architecture-Decisions.md §4d)."""

from azure.storage.blob import BlobServiceClient, ContentSettings

from app.config import settings


def _container_client():
    service_client = BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)
    return service_client.get_container_client(settings.azure_storage_container)


def _upload(blob_name: str, data: bytes, content_type: str) -> str:
    blob_client = _container_client().get_blob_client(blob_name)
    blob_client.upload_blob(
        data,
        overwrite=True,
        content_settings=ContentSettings(content_type=content_type),
    )
    return blob_client.url


def upload_resume_file(candidate_id: str, filename: str, data: bytes, content_type: str) -> str:
    """Upload the raw resume file to Azure Blob Storage, return its stored URL."""
    return _upload(f"resumes/{candidate_id}/{filename}", data, content_type)


def upload_interview_answer_audio(
    session_id: str, turn_index: int, data: bytes, content_type: str
) -> str:
    """Upload a candidate's recorded answer to Azure Blob Storage (kept for
    STT-quality debugging/reprocessing, see docs/Architecture-Decisions.md §6 —
    transcript_turns.audio_file_url). Return its stored URL."""
    ext = "webm"
    if content_type and "/" in content_type:
        ext = content_type.split("/")[-1].split(";")[0] or ext
    return _upload(f"interview-audio/{session_id}/{turn_index}.{ext}", data, content_type)
