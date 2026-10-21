"""Email OTP + OAuth sign-in: replace phone verification

candidates.phone_verified_at -> verified_at (+ auth_provider); otp_codes.phone -> email.
Candidates verified by SMS keep their verified status (auth_provider "sms").
In-flight SMS codes are meaningless now, so they are deleted.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("candidates", "phone_verified_at", new_column_name="verified_at")
    op.add_column("candidates", sa.Column("auth_provider", sa.String(), nullable=True))
    op.execute("UPDATE candidates SET auth_provider = 'sms' WHERE verified_at IS NOT NULL")

    op.execute("DELETE FROM otp_codes")
    op.alter_column("otp_codes", "phone", new_column_name="email")


def downgrade() -> None:
    op.alter_column("otp_codes", "email", new_column_name="phone")
    op.drop_column("candidates", "auth_provider")
    op.alter_column("candidates", "verified_at", new_column_name="phone_verified_at")
