from fastapi import APIRouter

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("")
async def create_session():
    """FL-03/FL-04: create a session with target_type ('jd'|'role'|'topic'),
    the corresponding target value, and consent — fixed 30 min duration."""
    raise NotImplementedError


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Session status/state for resuming a dropped session (FL-05.7)."""
    raise NotImplementedError
