"""create timeline_events

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EVENT_TYPES = ("stage_change", "note")


def upgrade() -> None:
    event_type = postgresql.ENUM(*EVENT_TYPES, name="event_type", create_type=False)
    # The stage enum was created by 0002.
    stage = postgresql.ENUM(name="stage", create_type=False)
    event_type.create(op.get_bind(), checkfirst=False)

    op.create_table(
        "timeline_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "application_id", sa.BigInteger(), sa.ForeignKey("applications.id"), nullable=False
        ),
        sa.Column("type", event_type, nullable=False),
        sa.Column("from_stage", stage, nullable=True),
        sa.Column("to_stage", stage, nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "timeline_events_application_idx", "timeline_events", ["application_id", "created_at"]
    )

    # Append-only is enforced by the database, not only by convention. TRUNCATE is not
    # blocked, so test cleanup and the seed reset still work.
    op.execute(
        """
        CREATE FUNCTION reject_timeline_events_change() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'timeline_events is append-only: % is not allowed', TG_OP;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER timeline_events_append_only
        BEFORE UPDATE OR DELETE ON timeline_events
        FOR EACH ROW EXECUTE FUNCTION reject_timeline_events_change()
        """
    )

    # Applications created in feature 2 have no history yet. Every one of them is in `saved`
    # (the stage could not be changed), so each gets its initial event, dated at creation.
    op.execute(
        """
        INSERT INTO timeline_events (application_id, type, from_stage, to_stage, created_at)
        SELECT id, 'stage_change', NULL, 'saved', created_at FROM applications
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER timeline_events_append_only ON timeline_events")
    op.execute("DROP FUNCTION reject_timeline_events_change()")
    op.drop_index("timeline_events_application_idx", table_name="timeline_events")
    op.drop_table("timeline_events")
    postgresql.ENUM(name="event_type").drop(op.get_bind(), checkfirst=False)
