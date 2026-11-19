"""add posting_tsv to applications

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The posting as a search vector, kept in step with posting_text by the database. Existing
    # rows are filled when the column is added. Example retrieval (feature 12) searches it.
    op.add_column(
        "applications",
        sa.Column(
            "posting_tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', posting_text)", persisted=True),
        ),
    )
    op.create_index(
        "applications_posting_tsv_idx",
        "applications",
        ["posting_tsv"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("applications_posting_tsv_idx", table_name="applications")
    op.drop_column("applications", "posting_tsv")
