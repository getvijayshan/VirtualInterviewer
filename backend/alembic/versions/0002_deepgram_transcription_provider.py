"""rename transcription_provider enum value whisper -> deepgram

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-02

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE transcription_provider RENAME VALUE 'whisper' TO 'deepgram'")


def downgrade() -> None:
    op.execute("ALTER TYPE transcription_provider RENAME VALUE 'deepgram' TO 'whisper'")
