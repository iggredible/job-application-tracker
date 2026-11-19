"""create resumes

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVIEW_STATUSES = ("draft", "approved", "rejected")


def upgrade() -> None:
    review_status = postgresql.ENUM(*REVIEW_STATUSES, name="review_status", create_type=False)
    review_status.create(op.get_bind(), checkfirst=False)

    # ai_call_id, content_json, draft_markdown and guardrail_flags are added by features 8 and
    # 9, and applications.submitted_resume_id by feature 11. ai_calls does not exist yet.
    op.create_table(
        "resumes",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        # Null only for the base resume.
        sa.Column("application_id", sa.BigInteger(), sa.ForeignKey("applications.id")),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("status", review_status, nullable=False, server_default=sa.text("'draft'")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("resumes_application_idx", "resumes", ["application_id"])
    # Only one base resume: an index on a constant, over the rows that have no application.
    op.execute(
        "CREATE UNIQUE INDEX resumes_one_base_idx ON resumes ((true)) WHERE application_id IS NULL"
    )


def downgrade() -> None:
    op.drop_table("resumes")
    postgresql.ENUM(name="review_status").drop(op.get_bind(), checkfirst=False)
