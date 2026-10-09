"""initial schema - candidates, sessions, transcript_turns, reports

Revision ID: 0001
Revises:
Create Date: 2026-09-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("resume_file_url", sa.String(), nullable=True),
        sa.Column("resume_parsed_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # create_type=False: the type is created explicitly below, once — letting the
    # column definition auto-create it too would emit a duplicate CREATE TYPE.
    target_type = postgresql.ENUM("jd", "role", "topic", name="target_type", create_type=False)
    session_status = postgresql.ENUM(
        "pending", "in_progress", "completed", "abandoned", name="session_status", create_type=False
    )
    target_type.create(op.get_bind())
    session_status.create(op.get_bind())

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("target_type", target_type, nullable=False),
        sa.Column("jd_text", sa.Text(), nullable=True),
        sa.Column("target_role", sa.String(), nullable=True),
        sa.Column("target_topic", sa.String(), nullable=True),
        sa.Column("duration_min", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("status", session_status, nullable=False, server_default="pending"),
        sa.Column("consent_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
    )

    turn_role = postgresql.ENUM("assistant", "user", name="turn_role", create_type=False)
    transcription_provider = postgresql.ENUM(
        "whisper", "azure_foundry", name="transcription_provider", create_type=False
    )
    turn_role.create(op.get_bind())
    transcription_provider.create(op.get_bind())

    op.create_table(
        "transcript_turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("role", turn_role, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("audio_file_url", sa.String(), nullable=True),
        sa.Column("transcription_provider", transcription_provider, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("scorecard_json", sa.JSON(), nullable=False),
        sa.Column("feedback_text", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_table("transcript_turns")
    op.drop_table("sessions")
    op.drop_table("candidates")

    for enum_name in ("transcription_provider", "turn_role", "session_status", "target_type"):
        postgresql.ENUM(name=enum_name).drop(op.get_bind())
