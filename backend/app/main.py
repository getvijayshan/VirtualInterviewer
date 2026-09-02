from fastapi import FastAPI

from app.routers import auth, interview, reports, resumes, sessions

app = FastAPI(title="Candidate True Companion API")

app.include_router(resumes.router)
app.include_router(sessions.router)
app.include_router(interview.router)
app.include_router(auth.router)
app.include_router(reports.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
