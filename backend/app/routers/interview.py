from fastapi import APIRouter, UploadFile

router = APIRouter(prefix="/sessions/{session_id}", tags=["interview"])


@router.post("/turns")
async def submit_answer(session_id: str, audio: UploadFile):
    """FL-05: transcribe the candidate's spoken answer (see docs/Architecture-Decisions.md
    §4a — Whisper now, Azure AI Foundry planned), append to the transcript, call Claude
    for the next question. Server-side duration/turn cap enforced here (FL-05.5)."""
    raise NotImplementedError


@router.get("/transcript")
async def get_transcript(session_id: str):
    """FL-05.8: full ordered question/answer transcript."""
    raise NotImplementedError


@router.post("/end")
async def end_session(session_id: str):
    """FL-05.6: candidate ends the session early."""
    raise NotImplementedError
