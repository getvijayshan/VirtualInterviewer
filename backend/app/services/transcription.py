"""Speech-to-text for recorded interview answers.

Per docs/Architecture-Decisions.md §4a: candidate answers are recorded as
audio and transcribed server-side before being appended to the transcript
as a `user` turn. `transcribe()` is the single entry point #7 (interview
loop) should call — swapping providers (Deepgram now, Azure AI Foundry
planned, #11) means adding a branch here, not touching the interview loop.
"""

from deepgram import DeepgramClient
from deepgram.core.api_error import ApiError

from app.config import settings


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
        raise TranscriptionError("Deepgram returned an empty transcript.")
    return transcript


def transcribe(audio_bytes: bytes) -> str:
    """Transcribe a recorded answer using the configured STT provider.

    Raises TranscriptionError on any failure — callers should surface a
    retry, not crash the interview loop.
    """
    if settings.stt_provider == "deepgram":
        return _transcribe_deepgram(audio_bytes)
    raise NotImplementedError(f"Unknown STT provider: {settings.stt_provider!r}")
