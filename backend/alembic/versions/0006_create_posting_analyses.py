"""create posting_analyses

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The review_status enum already exists (migration 0004).
    review_status = postgresql.ENUM(
        "draft", "approved", "rejected", name="review_status", create_type=False
    )
    op.create_table(
        "posting_analyses",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "application_id", sa.BigInteger(), sa.ForeignKey("applications.id"), nullable=False
        ),
        sa.Column("ai_call_id", sa.BigInteger(), sa.ForeignKey("ai_calls.id"), nullable=False),
        # [{"text": ..., "category": "must_have" | "nice_to_have"}]
        sa.Column("requirements", postgresql.JSONB(), nullable=False),
        sa.Column("keywords", postgresql.JSONB(), nullable=False),
        sa.Column("status", review_status, nullable=False, server_default=sa.text("'draft'")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("posting_analyses_application_idx", "posting_analyses", ["application_id"])


def downgrade() -> None:
    op.drop_index("posting_analyses_application_idx", table_name="posting_analyses")
    op.drop_table("posting_analyses")
