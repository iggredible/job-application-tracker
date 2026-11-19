"""create ai_calls

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AI_FEATURES = ("posting_analysis", "tailor_resume")


def upgrade() -> None:
    ai_feature = postgresql.ENUM(*AI_FEATURES, name="ai_feature", create_type=False)
    ai_feature.create(op.get_bind(), checkfirst=False)

    # The foreign keys from resumes and posting_analyses to ai_calls are added by features 6
    # and 8, which create those columns.
    op.create_table(
        "ai_calls",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("application_id", sa.BigInteger(), sa.ForeignKey("applications.id")),
        sa.Column("feature", ai_feature, nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        # The full rendered request, as sent.
        sa.Column("request_json", postgresql.JSONB(), nullable=False),
        # Null when the call failed.
        sa.Column("response_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "retrieved_example_ids",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        # Stored at call time, because prices change.
        sa.Column("estimated_cost", sa.Numeric(10, 6), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("schema_valid", sa.Boolean(), nullable=False),
        sa.Column("stop_reason", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ai_calls_application_idx", "ai_calls", ["application_id"])

    # Append-only is enforced by the database, not only by convention. TRUNCATE is not
    # blocked, so test cleanup and the seed reset still work.
    op.execute(
        """
        CREATE FUNCTION reject_ai_calls_change() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'ai_calls is append-only: % is not allowed', TG_OP;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER ai_calls_append_only
        BEFORE UPDATE OR DELETE ON ai_calls
        FOR EACH ROW EXECUTE FUNCTION reject_ai_calls_change()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER ai_calls_append_only ON ai_calls")
    op.execute("DROP FUNCTION reject_ai_calls_change()")
    op.drop_index("ai_calls_application_idx", table_name="ai_calls")
    op.drop_table("ai_calls")
    postgresql.ENUM(name="ai_feature").drop(op.get_bind(), checkfirst=False)
