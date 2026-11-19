"""Fill an empty database with sample data: about 40 applications with timelines, analyses,
tailored resumes and AI call rows, so the list, the timeline and Insights have something to show.

Run from the backend folder (or `make seed`):

    uv run python -m scripts.seed            # refuses if the database already has data
    uv run python -m scripts.seed --reset    # empties every table first

The data is fictional and fixed: the same run gives the same rows, with dates counted back from
today. It makes no AI call. It is the documented exception to the `change_stage()` rule: it
writes stages, timeline events and review statuses directly, with explicit timestamps, through
the repositories. The data still follows the transition table and the apply rules.
"""

import argparse
import sys
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.core.db import get_session_factory
from app.models import AICall, Application, PostingAnalysis, Resume, ReviewStatus, TimelineEvent
from app.repositories.ai_calls import AICallRepository
from app.repositories.applications import ApplicationRepository
from app.repositories.maintenance import MaintenanceRepository
from app.repositories.posting_analyses import PostingAnalysisRepository
from app.repositories.resumes import ResumeRepository
from app.repositories.timeline import TimelineRepository
from scripts.seed_plan import MODEL, CallPlan, SeedPlan, build_plan


class SeedRefused(Exception):
    """The database already has data and --reset was not passed."""


def seed(session: Session, *, now: datetime, reset: bool = False) -> dict[str, int]:
    """Insert the plan in one transaction and return how many rows of each kind were added."""
    try:
        maintenance = MaintenanceRepository(session)
        if reset:
            maintenance.truncate_all()
        elif not maintenance.is_empty():
            raise SeedRefused("The database already has data. Run with --reset to empty it first.")
        counts = _insert(session, build_plan(now))
        session.commit()
    except Exception:
        session.rollback()
        raise
    return counts


def _ai_call(application_id: int, call: CallPlan) -> AICall:
    return AICall(
        application_id=application_id,
        feature=call.feature,
        prompt_version=call.prompt_version,
        model=MODEL,
        request_json=call.request_json,
        response_json=call.response_json,
        retrieved_example_ids=[],
        input_tokens=call.input_tokens,
        output_tokens=call.output_tokens,
        estimated_cost=call.cost,
        latency_ms=call.latency_ms,
        schema_valid=call.error is None,
        stop_reason=call.stop_reason,
        error=call.error,
        created_at=call.at,
    )


def _insert(session: Session, plan: SeedPlan) -> dict[str, int]:
    applications = ApplicationRepository(session)
    timeline = TimelineRepository(session)
    calls = AICallRepository(session)
    analyses = PostingAnalysisRepository(session)
    resumes = ResumeRepository(session)
    counts = dict.fromkeys(
        [
            "applications",
            "timeline events",
            "ai calls",
            "analyses",
            "tailored resumes",
            "snapshots",
        ],
        0,
    )

    resumes.add(
        Resume(
            content_markdown=plan.base_markdown,
            status=ReviewStatus.APPROVED,
            created_at=plan.base_at,
            updated_at=plan.base_at,
        )
    )
    for item in plan.applications:
        application = applications.add(
            Application(
                company=item.company,
                role=item.role,
                posting_url=item.posting_url,
                posting_text=item.posting_text,
                source=item.source,
                stage=item.stage,  # the documented exception: no change_stage() here
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
        )
        counts["applications"] += 1
        for event in item.events:
            timeline.add(
                TimelineEvent(
                    application_id=application.id,
                    type=event.type,
                    from_stage=event.from_stage,
                    to_stage=event.to_stage,
                    note=event.note,
                    created_at=event.at,
                )
            )
            counts["timeline events"] += 1
        for failed in item.failed_calls:
            calls.add(_ai_call(application.id, failed))
            counts["ai calls"] += 1
        for analysis in item.analyses:
            call = calls.add(_ai_call(application.id, analysis.call))
            analyses.add(
                PostingAnalysis(
                    application_id=application.id,
                    ai_call_id=call.id,
                    requirements=analysis.requirements,
                    keywords=analysis.keywords,
                    status=analysis.status,
                    created_at=analysis.created_at,
                    reviewed_at=analysis.reviewed_at,
                )
            )
            counts["ai calls"] += 1
            counts["analyses"] += 1
        drafts = []
        for draft in item.tailored:
            call = calls.add(_ai_call(application.id, draft.call))
            # One INSERT with its final text and status, so the draft_markdown trigger never fires.
            drafts.append(
                resumes.add_draft(
                    Resume(
                        application_id=application.id,
                        ai_call_id=call.id,
                        content_json=draft.content_json,
                        draft_markdown=draft.draft_markdown,
                        content_markdown=draft.content_markdown,
                        guardrail_flags=draft.flags,
                        status=draft.status,
                        created_at=draft.created_at,
                        updated_at=draft.updated_at,
                        reviewed_at=draft.reviewed_at,
                    )
                )
            )
            counts["ai calls"] += 1
            counts["tailored resumes"] += 1

        submitted = None
        if item.submitted == "tailored":
            submitted = drafts[-1]  # the approved one, always the newest
        elif item.submitted == "base":
            submitted = resumes.add_snapshot(
                Resume(
                    application_id=application.id,
                    content_markdown=plan.base_markdown,
                    status=ReviewStatus.APPROVED,
                    created_at=item.submitted_at,
                    updated_at=item.submitted_at,
                )
            )
            counts["snapshots"] += 1
        if submitted is not None:
            # The application and the resume point at each other, so the pointer is set last. The
            # update would stamp updated_at with now(), so it is put back to the last activity.
            applications.set_submitted_resume(application, submitted.id)
            application.updated_at = item.updated_at
            applications.add(application)  # flushes the change
    return counts


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.seed", description=__doc__.split("\n")[0]
    )
    parser.add_argument(
        "--reset", action="store_true", help="empty every table first (all existing data is lost)"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    with get_session_factory()() as session:
        try:
            counts = seed(session, now=utc_now(), reset=args.reset)
        except SeedRefused as error:
            print(error, file=sys.stderr)
            return 1
    print("Seeded " + ", ".join(f"{count} {name}" for name, count in counts.items()) + ".")
    return 0


if __name__ == "__main__":
    sys.exit(main())
