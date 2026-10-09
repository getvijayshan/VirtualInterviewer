"""Make all datetime columns timezone-aware (timestamptz)

Existing values were written as UTC, so they are reinterpreted as UTC.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-09

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE candidates ALTER COLUMN phone_verified_at TYPE TIMESTAMPTZ USING phone_verified_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE candidates ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE sessions ALTER COLUMN consent_at TYPE TIMESTAMPTZ USING consent_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE sessions ALTER COLUMN started_at TYPE TIMESTAMPTZ USING started_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE sessions ALTER COLUMN ended_at TYPE TIMESTAMPTZ USING ended_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE otp_codes ALTER COLUMN expires_at TYPE TIMESTAMPTZ USING expires_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE otp_codes ALTER COLUMN consumed_at TYPE TIMESTAMPTZ USING consumed_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE otp_codes ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE transcript_turns ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE reports ALTER COLUMN generated_at TYPE TIMESTAMPTZ USING generated_at AT TIME ZONE 'UTC'")


def downgrade() -> None:
    op.execute("ALTER TABLE candidates ALTER COLUMN phone_verified_at TYPE TIMESTAMP USING phone_verified_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE candidates ALTER COLUMN created_at TYPE TIMESTAMP USING created_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE sessions ALTER COLUMN consent_at TYPE TIMESTAMP USING consent_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE sessions ALTER COLUMN started_at TYPE TIMESTAMP USING started_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE sessions ALTER COLUMN ended_at TYPE TIMESTAMP USING ended_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE otp_codes ALTER COLUMN expires_at TYPE TIMESTAMP USING expires_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE otp_codes ALTER COLUMN consumed_at TYPE TIMESTAMP USING consumed_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE otp_codes ALTER COLUMN created_at TYPE TIMESTAMP USING created_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE transcript_turns ALTER COLUMN created_at TYPE TIMESTAMP USING created_at AT TIME ZONE 'UTC'")
    op.execute("ALTER TABLE reports ALTER COLUMN generated_at TYPE TIMESTAMP USING generated_at AT TIME ZONE 'UTC'")
