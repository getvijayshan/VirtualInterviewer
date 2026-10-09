from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Every datetime column is timestamptz. The routers compare against
# datetime.now(timezone.utc), which raises TypeError on a naive value read back
# from a plain TIMESTAMP column (hit live on POST /sessions/{id}/start).
Base = declarative_base(type_annotation_map={datetime: DateTime(timezone=True)})


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
