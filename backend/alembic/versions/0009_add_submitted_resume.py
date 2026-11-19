"""add submitted_resume_id to applications

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The resume that was sent: a snapshot of the base resume, or an approved tailored resume.
    # Null until the application leaves Saved with one. Applications moved to Applied before this
    # migration have none, so the development database is reset after it.
    op.add_column(
        "applications",
        sa.Column(
            "submitted_resume_id",
            sa.BigInteger(),
            sa.ForeignKey("resumes.id", name="applications_submitted_resume_id_fkey"),
        ),
    )


def downgrade() -> None:
    op.drop_column("applications", "submitted_resume_id")
