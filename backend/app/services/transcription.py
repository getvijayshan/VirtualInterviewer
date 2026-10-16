"""Speech-to-text for recorded interview answers.

Per docs/Architecture-Decisions.md §4a: candidate answers are recorded as
audio and transcribed server-side before being appended to the transcript
as a `user` turn. `transcribe()` is the single entry point #7 (interview
loop) should call — swapping providers (Deepgram now, Azure AI Foundry
planned, #11) means adding a branch here, not touching the interview loop.
"""

import logging

from deepgram import DeepgramClient
from deepgram.core.api_error import ApiError

from app.config import settings

logger = logging.getLogger(__name__)


class TranscriptionError(Exception):
    """Raised when STT fails to produce usable text."""


def _deepgram_client() -> DeepgramClient:
    return DeepgramClient(api_key=settings.deepgram_api_key)


def _transcribe_deepgram(audio_bytes: bytes) -> str:
    try:
        response = _deepgram_client().listen.v1.media.transcribe_file(
            request=audio_bytes,
            model=settings.deepgram_model,
            smart_format=True,
            punctuate=True,
        )
    except ApiError as exc:
        raise TranscriptionError(f"Deepgram transcription failed: {exc}") from exc

    try:
        transcript = response.results.channels[0].alternatives[0].transcript
    except (AttributeError, IndexError, TypeError) as exc:
        raise TranscriptionError("Deepgram response did not include a transcript.") from exc

    transcript = (transcript or "").strip()
    if not transcript:
        duration = getattr(getattr(response, "metadata", None), "duration", None)
        logger.warning("Empty transcript: %d bytes, duration=%s", len(audio_bytes), duration)
        raise TranscriptionError(
            "We didn't hear any speech in that recording "
            f"({len(audio_bytes)} bytes, {duration or 0:.1f}s). "
            "Check your microphone is not muted, speak for a few seconds, and try again."
        )
    return transcript


def transcribe(audio_bytes: bytes) -> str:
    """Transcribe a recorded answer using the configured STT provider.

    Raises TranscriptionError on any failure — callers should surface a
    retry, not crash the interview loop.
    """
    if settings.stt_provider == "deepgram":
        return _transcribe_deepgram(audio_bytes)
    raise NotImplementedError(f"Unknown STT provider: {settings.stt_provider!r}")
