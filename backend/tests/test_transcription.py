from types import SimpleNamespace

import pytest
from deepgram.core.api_error import ApiError

from app.services import transcription


class FakeMedia:
    next_response = None
    next_error = None

    def __init__(self):
        self.last_kwargs = None

    def transcribe_file(self, **kwargs):
        self.last_kwargs = kwargs
        if FakeMedia.next_error:
            raise FakeMedia.next_error
        return FakeMedia.next_response


class FakeListenV1:
    def __init__(self):
        self.media = FakeMedia()


class FakeListen:
    def __init__(self):
        self.v1 = FakeListenV1()


class FakeDeepgramClient:
    last_instance = None

    def __init__(self, **kwargs):
        self.init_kwargs = kwargs
        self.listen = FakeListen()
        FakeDeepgramClient.last_instance = self


def _response(transcript: str):
    alt = SimpleNamespace(transcript=transcript)
    channel = SimpleNamespace(alternatives=[alt])
    results = SimpleNamespace(channels=[channel])
    return SimpleNamespace(results=results)


@pytest.fixture(autouse=True)
def patch_client(monkeypatch):
    FakeMedia.next_response = None
    FakeMedia.next_error = None
    monkeypatch.setattr(transcription, "DeepgramClient", FakeDeepgramClient)
    monkeypatch.setattr(transcription.settings, "stt_provider", "deepgram")
    monkeypatch.setattr(transcription.settings, "deepgram_api_key", "dg-test")
    monkeypatch.setattr(transcription.settings, "deepgram_model", "nova-2")


def test_transcribe_returns_transcript_text():
    FakeMedia.next_response = _response("tell me about your last project")

    result = transcription.transcribe(b"fake-audio-bytes")

    assert result == "tell me about your last project"
    kwargs = FakeDeepgramClient.last_instance.listen.v1.media.last_kwargs
    assert kwargs["request"] == b"fake-audio-bytes"
    assert kwargs["model"] == "nova-2"


def test_transcribe_passes_api_key_to_client():
    FakeMedia.next_response = _response("hello")
    transcription.transcribe(b"audio")
    assert FakeDeepgramClient.last_instance.init_kwargs["api_key"] == "dg-test"


def test_transcribe_strips_whitespace():
    FakeMedia.next_response = _response("  padded transcript  ")
    assert transcription.transcribe(b"audio") == "padded transcript"


def test_transcribe_raises_on_api_error():
    FakeMedia.next_error = ApiError(body="boom")
    with pytest.raises(transcription.TranscriptionError):
        transcription.transcribe(b"audio")


def test_transcribe_raises_on_empty_transcript():
    FakeMedia.next_response = _response("")
    with pytest.raises(transcription.TranscriptionError):
        transcription.transcribe(b"audio")


def test_transcribe_raises_on_missing_channels():
    FakeMedia.next_response = SimpleNamespace(results=SimpleNamespace(channels=[]))
    with pytest.raises(transcription.TranscriptionError):
        transcription.transcribe(b"audio")


def test_transcribe_raises_for_unknown_provider(monkeypatch):
    monkeypatch.setattr(transcription.settings, "stt_provider", "azure_foundry")
    with pytest.raises(NotImplementedError):
        transcription.transcribe(b"audio")
