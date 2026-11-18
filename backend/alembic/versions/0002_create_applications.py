"""create applications

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STAGES = (
    "saved",
    "applied",
    "screening",
    "interviewing",
    "offer",
    "accepted",
    "rejected",
    "withdrawn",
)
SOURCES = ("referral", "linkedin", "company_site", "recruiter", "other")


def upgrade() -> None:
    stage = postgresql.ENUM(*STAGES, name="stage", create_type=False)
    source = postgresql.ENUM(*SOURCES, name="source", create_type=False)
    stage.create(op.get_bind(), checkfirst=False)
    source.create(op.get_bind(), checkfirst=False)

    # posting_tsv and submitted_resume_id are added by later features.
    op.create_table(
        "applications",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("posting_url", sa.Text(), nullable=True),
        sa.Column("posting_text", sa.Text(), nullable=False),
        sa.Column("source", source, nullable=False),
        sa.Column("stage", stage, nullable=False, server_default=sa.text("'saved'")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("applications")
    postgresql.ENUM(name="source").drop(op.get_bind(), checkfirst=False)
    postgresql.ENUM(name="stage").drop(op.get_bind(), checkfirst=False)
