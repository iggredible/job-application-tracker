"""add tailored resume columns to resumes

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # All three are null for the base resume. guardrail_flags is added by feature 9.
    op.add_column("resumes", sa.Column("ai_call_id", sa.BigInteger(), sa.ForeignKey("ai_calls.id")))
    op.add_column("resumes", sa.Column("content_json", postgresql.JSONB()))
    # As generated, never changed: the edit ratio compares it with content_markdown.
    op.add_column("resumes", sa.Column("draft_markdown", sa.Text()))

    op.execute(
        """
        CREATE FUNCTION reject_draft_markdown_change() RETURNS trigger AS $$
        BEGIN
            IF NEW.draft_markdown IS DISTINCT FROM OLD.draft_markdown THEN
                RAISE EXCEPTION 'resumes.draft_markdown cannot change after insert';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER resumes_draft_markdown_fixed
        BEFORE UPDATE ON resumes
        FOR EACH ROW EXECUTE FUNCTION reject_draft_markdown_change()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER resumes_draft_markdown_fixed ON resumes")
    op.execute("DROP FUNCTION reject_draft_markdown_change()")
    op.drop_column("resumes", "draft_markdown")
    op.drop_column("resumes", "content_json")
    op.drop_column("resumes", "ai_call_id")
