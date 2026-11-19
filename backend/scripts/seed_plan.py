"""The seed plan: every row the seed script will insert, chosen from one fixed random seed.

Pure: no database and no clock (the caller passes `now`). The same `now` always gives the same
plan, and every timestamp is an offset from `now`, so "stale" and "ten weeks" hold whenever the
seed runs. The real pure functions do the domain work: `render_tailored_markdown()` writes the
drafts, `check()` finds their flags and `edit_ratio()` tunes how much the user changed them.
"""

import random
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from app.ai.cost import estimate_cost
from app.ai.schemas import Experience, TailoredResume
from app.core.config import ModelPrice
from app.models import AIFeature, EventType, ReviewStatus, Source, Stage
from app.services.guardrail import check
from app.services.rendering import render_tailored_markdown
from app.services.resume_review import edit_ratio
from app.services.transitions import TRANSITIONS
from scripts import seed_content as content

RANDOM_SEED = 13
MODEL = "seed"  # told apart from real calls by name
PRICES = {MODEL: ModelPrice(Decimal("2"), Decimal("10"))}
S = Stage

WINDOW = timedelta(days=70)  # ten weeks
STALE_COUNT = 5
STALE_AFTER = timedelta(days=15)  # the rule is 14 days; stay clear of the edge
RECENT = timedelta(days=10)  # a live application had some activity within this

# How many applications follow each path: the stages after Saved. 40 in all, 34 of them applied.
PATHS: list[tuple[int, tuple[Stage, ...]]] = [
    (4, ()),
    (2, (S.WITHDRAWN,)),
    (11, (S.APPLIED,)),
    (3, (S.APPLIED, S.WITHDRAWN)),
    (5, (S.APPLIED, S.REJECTED)),
    (1, (S.APPLIED, S.SCREENING)),
    (3, (S.APPLIED, S.SCREENING, S.REJECTED)),
    (1, (S.APPLIED, S.SCREENING, S.WITHDRAWN)),
    (3, (S.APPLIED, S.SCREENING, S.INTERVIEWING)),
    (3, (S.APPLIED, S.SCREENING, S.INTERVIEWING, S.REJECTED)),
    (1, (S.APPLIED, S.SCREENING, S.INTERVIEWING, S.OFFER)),
    (1, (S.APPLIED, S.SCREENING, S.INTERVIEWING, S.OFFER, S.ACCEPTED)),
    (1, (S.APPLIED, S.INTERVIEWING)),
    (1, (S.APPLIED, S.SCREENING, S.INTERVIEWING, S.WITHDRAWN)),
]
# Days spent in a stage before moving on. The AI work needs a longer stay in Saved.
DWELL = {
    S.SAVED: (1, 3),
    S.APPLIED: (4, 14),
    S.SCREENING: (3, 9),
    S.INTERVIEWING: (7, 18),
    S.OFFER: (2, 6),
}
AI_SAVED_DWELL = (2, 4)

# Of the applications that were applied to, this many sent a tailored resume (the rest sent the
# base resume). Taking more of them from those that got a response gives the higher response rate.
TAILORED_RESPONDERS, TAILORED_SILENT = 12, 6
SAVED_WITH_AI = 3

# What happened to each tailored draft of one application, in the order they were made.
V1_SCENARIOS = [
    ("approved",), ("edited",), ("edited",), ("rejected", "edited"), ("edited",), ("approved",),
    ("superseded", "edited"), ("rejected", "approved"),
]  # fmt: skip
V2_SCENARIOS = [
    ("approved",), ("approved",), ("edited",), ("approved",), ("rejected", "edited"), ("approved",),
    ("edited",), ("superseded", "approved"), ("approved",), ("edited",),
]  # fmt: skip
SAVED_SCENARIOS = [("pending",), ("superseded", "pending"), ("approved",)]
V1_SHARE = 0.43  # the oldest 43% of the AI work used prompt v1, the rest v2

# v2 needs less fixing than v1: lower edit ratio, fewer guardrail flags.
EDIT_TARGET = {"v1": (0.2, 0.35), "v2": (0.06, 0.16)}
FLAG_CHANCE = {"v1": 0.5, "v2": 0.2}
FLAG_MAX = {"v1": 3, "v2": 1}
LATENCY_MS = {"v1": (8000, 11500), "v2": (7500, 10500)}

_BASE_MARKDOWN = content.base_markdown()


# --- the plan ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class EventPlan:
    at: datetime
    type: EventType
    from_stage: Stage | None
    to_stage: Stage | None
    note: str | None


@dataclass(frozen=True)
class CallPlan:
    feature: AIFeature
    prompt_version: str
    at: datetime
    request_json: dict[str, Any]
    response_json: dict[str, Any] | None  # None when the call failed
    input_tokens: int | None
    output_tokens: int | None
    cost: Decimal | None
    latency_ms: int
    stop_reason: str | None
    error: str | None


@dataclass(frozen=True)
class AnalysisPlan:
    call: CallPlan
    requirements: list[dict[str, str]]
    keywords: list[str]
    status: ReviewStatus
    created_at: datetime
    reviewed_at: datetime


@dataclass(frozen=True)
class TailoredPlan:
    call: CallPlan
    content_json: dict[str, Any]
    draft_markdown: str
    content_markdown: str
    flags: list[dict[str, str]]  # as generated
    status: ReviewStatus
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None


@dataclass(frozen=True)
class ApplicationPlan:
    company: str
    role: str
    source: Source
    posting_url: str | None
    posting_text: str
    stage: Stage  # where the timeline ends
    created_at: datetime
    updated_at: datetime
    events: list[EventPlan]
    analyses: list[AnalysisPlan]  # oldest first
    tailored: list[TailoredPlan]  # oldest first; an application that sent one ends with it
    failed_calls: list[CallPlan]
    submitted: str | None  # None, "base" or "tailored"
    submitted_at: datetime | None  # when it moved Saved -> Applied


@dataclass(frozen=True)
class SeedPlan:
    base_markdown: str
    base_at: datetime
    applications: list[ApplicationPlan]


@dataclass(frozen=True)
class Posting:
    role: str
    keywords: list[str]
    requirements: list[dict[str, str]]
    text: str
    url: str | None


def build_plan(now: datetime) -> SeedPlan:
    rng = random.Random(RANDOM_SEED)
    paths = [path for count, path in PATHS for _ in range(count)]
    rng.shuffle(paths)
    total = len(paths)
    sources = [list(Source)[i % len(Source)] for i in range(total)]
    rng.shuffle(sources)
    companies = rng.sample(content.COMPANIES, total)

    live = [i for i, path in enumerate(paths) if TRANSITIONS[(S.SAVED, *path)[-1]]]
    stale = set(rng.sample(live, STALE_COUNT))
    applied = [i for i, path in enumerate(paths) if path and path[0] is S.APPLIED]
    responded = [i for i in applied if any(s is not S.WITHDRAWN for s in paths[i][1:])]
    silent = [i for i in applied if i not in responded]
    rng.shuffle(responded)
    rng.shuffle(silent)
    sent_tailored = set(responded[:TAILORED_RESPONDERS]) | set(silent[:TAILORED_SILENT])
    saved = [i for i, path in enumerate(paths) if not path]
    saved_with_ai = set(rng.sample(saved, SAVED_WITH_AI))

    timelines = [
        _timeline(rng, now, paths[i], i in stale, i in sent_tailored) for i in range(total)
    ]
    postings = [_posting(rng, companies[i], i) for i in range(total)]
    ai = _ai_work(rng, timelines, postings, sent_tailored, saved_with_ai)

    applications = []
    for i in range(total):
        events = timelines[i]
        applied_event = next((e for e in events if e.to_stage is S.APPLIED), None)
        analyses, tailored, failed = ai.get(i, ([], [], []))
        submitted = None
        if applied_event is not None:
            submitted = "tailored" if i in sent_tailored else "base"
        applications.append(
            ApplicationPlan(
                company=companies[i],
                role=postings[i].role,
                source=sources[i],
                posting_url=postings[i].url,
                posting_text=postings[i].text,
                stage=(S.SAVED, *paths[i])[-1],
                created_at=events[0].at,
                updated_at=max(e.at for e in events),
                events=events,
                analyses=analyses,
                tailored=tailored,
                failed_calls=failed,
                submitted=submitted,
                submitted_at=applied_event.at if applied_event else None,
            )
        )
    applications.sort(key=lambda a: a.created_at)  # ids then run in the order things happened
    base_at = applications[0].created_at - timedelta(days=2)
    return SeedPlan(_BASE_MARKDOWN, base_at, applications)


# --- timelines -----------------------------------------------------------------------------------


def _timeline(
    rng: random.Random, now: datetime, path: tuple[Stage, ...], stale: bool, has_ai: bool
) -> list[EventPlan]:
    """Saved, then each stage of the path. Time in a stage comes from DWELL. The last stage change
    falls where the application is live (a recent note keeps it from going stale), stale (nothing
    for 15 days or more) or finished (anywhere in the window)."""
    stages = [S.SAVED, *path]
    stays = []
    for stage in stages[:-1]:
        low, high = AI_SAVED_DWELL if has_ai and stage is S.SAVED else DWELL[stage]
        days, hours, minutes = rng.randint(low, high), rng.randint(0, 8), rng.randint(0, 59)
        stays.append(timedelta(days=days, hours=hours, minutes=minutes))
    span = sum(stays, timedelta())
    oldest = now - WINDOW + span
    newest = now - (STALE_AFTER if stale else timedelta(days=1))
    last_change = oldest + (newest - oldest) * rng.random()

    at = last_change - span
    events = [EventPlan(at, EventType.STAGE_CHANGE, None, S.SAVED, None)]
    for stage, next_stage, stay in zip(stages[:-1], stages[1:], stays, strict=True):
        events.extend(_notes(rng, at, at + stay, stage))
        at += stay
        events.append(EventPlan(at, EventType.STAGE_CHANGE, stage, next_stage, None))

    final = stages[-1]
    if TRANSITIONS[final] and not stale:  # live: some activity in the last ten days
        if now - last_change > RECENT:
            noted = now - timedelta(days=rng.randint(1, 9), hours=rng.randint(0, 12))
            events.append(_note(rng, noted, final))
        elif rng.random() < 0.4:
            noted = last_change + (now - timedelta(hours=2) - last_change) * rng.uniform(0.3, 0.9)
            events.append(_note(rng, noted, final))
    return events


def _notes(rng: random.Random, start: datetime, end: datetime, stage: Stage) -> list[EventPlan]:
    """A few notes inside one stay. Interviewing always gets one or two (the rounds)."""
    if stage is S.INTERVIEWING:
        count = rng.randint(1, 2)
    elif stage is S.SAVED:
        count = 0
    else:
        count = rng.randint(0, 1)
    texts = rng.sample(content.NOTES[stage], count)
    times = sorted(start + (end - start) * rng.uniform(0.2, 0.8) for _ in texts)
    return [
        EventPlan(t, EventType.NOTE, None, None, text) for t, text in zip(times, texts, strict=True)
    ]


def _note(rng: random.Random, at: datetime, stage: Stage) -> EventPlan:
    return EventPlan(at, EventType.NOTE, None, None, rng.choice(content.NOTES[stage]))


# --- postings ------------------------------------------------------------------------------------


def _posting(rng: random.Random, company: str, number: int) -> Posting:
    family = content.FAMILIES[rng.choice(list(content.FAMILIES))]
    role = rng.choice(family.roles)
    covered = rng.sample(family.covered, k=rng.randint(4, min(6, len(family.covered))))
    missing = rng.sample(family.missing, k=rng.randint(2, min(3, len(family.missing))))
    keywords = covered + missing
    rng.shuffle(keywords)

    requirements = [{"text": family.duties[0], "category": "must_have"}]
    requirements += [
        {"text": f"Hands-on experience with {k}", "category": "must_have"} for k in keywords[:3]
    ]
    requirements += [
        {"text": f"Familiarity with {k}", "category": "nice_to_have"} for k in keywords[3:]
    ]
    text = "\n\n".join(
        [
            f"{company} is hiring a {role} to join a small, friendly engineering team.",
            "What you'll do\n" + "\n".join(f"- {duty}" for duty in family.duties),
            "What we're looking for\n" + "\n".join(f"- {r['text']}" for r in requirements[1:]),
            f"Our stack includes {', '.join(keywords)}.",
        ]
    )
    slug = re.sub(r"[^a-z0-9]+", "", company.casefold())
    url = f"https://careers.{slug}.example/jobs/{1000 + number}" if rng.random() < 0.7 else None
    return Posting(role, keywords, requirements, text, url)


# --- AI work -------------------------------------------------------------------------------------

type _Work = tuple[list[AnalysisPlan], list[TailoredPlan], list[CallPlan]]


def _ai_work(
    rng: random.Random,
    timelines: list[list[EventPlan]],
    postings: list[Posting],
    sent_tailored: set[int],
    saved_with_ai: set[int],
) -> dict[int, _Work]:
    """An approved analysis and tailored drafts for each application that sent a tailored resume
    and for a few that are still Saved. The oldest work used prompt v1 and the newest v2."""
    ordered = sorted(sent_tailored | saved_with_ai, key=lambda i: timelines[i][0].at)
    cutoff = timelines[ordered[round(len(ordered) * V1_SHARE)]][0].at
    work: dict[int, _Work] = {}
    seen = {"v1": 0, "v2": 0, "saved": 0}
    for position, i in enumerate(ordered):
        start = timelines[i][0].at
        version = "v1" if start < cutoff else "v2"
        if i in saved_with_ai:
            scenario = SAVED_SCENARIOS[seen["saved"] % len(SAVED_SCENARIOS)]
            seen["saved"] += 1
        else:
            scenarios = V1_SCENARIOS if version == "v1" else V2_SCENARIOS
            scenario = scenarios[seen[version] % len(scenarios)]
            seen[version] += 1
        style = {2: "rejected", 5: "failed", 9: "rejected", 14: "rejected"}.get(position, "ok")
        # One v2 application had a failed call first, then a retry.
        failed_tailor = i not in saved_with_ai and version == "v2" and seen["v2"] == 3
        work[i] = _ai_for(rng, start, postings[i], version, scenario, style, failed_tailor)
    return work


def _ai_for(
    rng: random.Random,
    start: datetime,
    posting: Posting,
    version: str,
    scenario: tuple[str, ...],
    style: str,
    failed_tailor: bool,
) -> _Work:
    """Analysis first (a rejected or failed try before the approved one for some), then each
    tailored draft in turn. The whole thing fits well inside the first day in Saved."""
    at = start + timedelta(minutes=rng.randint(20, 60))
    analyses: list[AnalysisPlan] = []
    failed: list[CallPlan] = []
    if style == "failed":
        failed.append(_failed_call(AIFeature.POSTING_ANALYSIS, "v1", at, posting.text))
        at += timedelta(minutes=rng.randint(5, 15))
    if style == "rejected":
        rejected, at = _analysis(rng, at, posting, ReviewStatus.REJECTED, thinner=True)
        analyses.append(rejected)
    approved, at = _analysis(rng, at, posting, ReviewStatus.APPROVED)
    analyses.append(approved)

    drafts: list[TailoredPlan] = []
    for number, outcome in enumerate(scenario):
        if failed_tailor and number == 0:
            failed.append(_failed_call(AIFeature.TAILOR_RESUME, version, at, posting.text))
            at += timedelta(minutes=rng.randint(5, 15))
        draft, at = _tailored(rng, at, posting, approved.keywords, version, outcome)
        drafts.append(draft)
    return analyses, drafts, failed


def _request(posting_text: str) -> dict[str, Any]:
    return {"system": "seed", "messages": [{"role": "user", "content": posting_text}]}


def _call(
    rng: random.Random,
    feature: AIFeature,
    version: str,
    at: datetime,
    posting_text: str,
    response: dict[str, Any],
) -> CallPlan:
    if feature is AIFeature.POSTING_ANALYSIS:
        tokens_in, tokens_out = rng.randint(1800, 2800), rng.randint(280, 520)
        latency = rng.randint(3000, 5600)
    else:
        tokens_in, tokens_out = rng.randint(3600, 5200), rng.randint(900, 1500)
        latency = rng.randint(*LATENCY_MS[version])
    return CallPlan(
        feature=feature,
        prompt_version=version,
        at=at,
        request_json=_request(posting_text),
        response_json=response,
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        cost=estimate_cost(MODEL, tokens_in, tokens_out, prices=PRICES),
        latency_ms=latency,
        stop_reason="end_turn",
        error=None,
    )


def _failed_call(feature: AIFeature, version: str, at: datetime, posting_text: str) -> CallPlan:
    return CallPlan(
        feature, version, at, _request(posting_text), None, None, None, None, 30000, None,
        "api_error: the upstream request timed out",
    )  # fmt: skip


def _analysis(
    rng: random.Random, at: datetime, posting: Posting, status: ReviewStatus, thinner: bool = False
) -> tuple[AnalysisPlan, datetime]:
    """One analysis and the time just after it was decided. A `thinner` one found fewer keywords."""
    keywords = list(posting.keywords)
    if thinner:
        keep = set(rng.sample(keywords, max(4, len(keywords) - 3)))
        keywords = [k for k in keywords if k in keep]
    response = {"requirements": posting.requirements, "keywords": keywords}
    call = _call(rng, AIFeature.POSTING_ANALYSIS, "v1", at, posting.text, response)
    reviewed = at + timedelta(minutes=rng.randint(3, 15))
    analysis = AnalysisPlan(call, posting.requirements, keywords, status, at, reviewed)
    return analysis, reviewed + timedelta(minutes=rng.randint(5, 30))


def _tailored(
    rng: random.Random,
    at: datetime,
    posting: Posting,
    keywords: list[str],
    version: str,
    outcome: str,
) -> tuple[TailoredPlan, datetime]:
    """One draft and the time the next step can start. `outcome` is approved, edited (then
    approved), rejected, pending or superseded (left as a draft while a newer one was made)."""
    draft = _draft(rng, keywords, version)
    markdown = render_tailored_markdown(_BASE_MARKDOWN, draft)
    flags = [asdict(flag) for flag in check(draft, _BASE_MARKDOWN, keywords)]
    text = _edit(rng, markdown, version) if outcome == "edited" else markdown
    decided = outcome in ("approved", "edited", "rejected")
    reviewed = at + timedelta(minutes=rng.randint(10, 90)) if decided else None
    status = {
        "approved": ReviewStatus.APPROVED,
        "edited": ReviewStatus.APPROVED,
        "rejected": ReviewStatus.REJECTED,
    }.get(outcome, ReviewStatus.DRAFT)
    call = _call(
        rng, AIFeature.TAILOR_RESUME, version, at, posting.text, draft.model_dump(mode="json")
    )
    plan = TailoredPlan(
        call, draft.model_dump(mode="json"), markdown, text, flags, status, at, reviewed or at,
        reviewed,
    )  # fmt: skip
    wait = rng.randint(15, 45) if outcome == "superseded" else rng.randint(5, 20)
    return plan, (reviewed or at) + timedelta(minutes=wait)


def _draft(rng: random.Random, keywords: list[str], version: str) -> TailoredResume:
    """A selection from the base resume, so every fact is in it. Now and then (more often for v1)
    it invents a skill, a number or a title, which is what the guardrail exists to catch."""
    base = content.base_resume()
    jobs = []
    for number, job in enumerate(base.experiences):
        if number == len(base.experiences) - 1 and rng.random() < 0.3:
            continue  # the oldest job is sometimes left out
        picked = sorted(
            rng.sample(range(len(job.bullets)), min(len(job.bullets), rng.randint(3, 5)))
        )
        jobs.append(job.model_copy(update={"bullets": [job.bullets[n] for n in picked]}))
    wanted = [s for s in base.skills if s.casefold() in keywords]
    rest = [s for s in base.skills if s not in wanted]
    rng.shuffle(rest)
    skills = (wanted + rest)[: max(len(wanted), rng.randint(8, 12))]
    draft = TailoredResume(
        summary=rng.choice(content.SUMMARY_VARIANTS), experiences=jobs, skills=skills
    )
    if rng.random() < FLAG_CHANCE[version]:
        draft = _invent(rng, draft, rng.randint(1, FLAG_MAX[version]))
    return draft


def _invent(rng: random.Random, draft: TailoredResume, count: int) -> TailoredResume:
    skills = list(draft.skills)
    jobs: list[Experience] = list(draft.experiences)
    for kind in rng.sample(["skill", "number", "title"], count):
        job_number = rng.randrange(len(jobs))
        if kind == "skill":
            skills.append(rng.choice(content.INVENTED_SKILLS))
        elif kind == "title":
            jobs[job_number] = jobs[job_number].model_copy(
                update={"title": rng.choice(content.INVENTED_TITLES)}
            )
        else:
            bullets = list(jobs[job_number].bullets)
            line = rng.randrange(len(bullets))
            bullets[line] = f"{bullets[line]}, a {rng.choice(content.INVENTED_NUMBERS)} gain"
            jobs[job_number] = jobs[job_number].model_copy(update={"bullets": bullets})
    return TailoredResume(summary=draft.summary, experiences=jobs, skills=skills)


def _edit(rng: random.Random, markdown: str, version: str) -> str:
    """What the user did to a draft: reword the summary, then swap or drop bullets until the edit
    ratio reaches a target (about 31% for v1, 14% for v2, as the Insights page shows). Swapped-in
    text comes from the base resume, so the edit adds no new fact."""
    target = rng.uniform(*EDIT_TARGET[version])
    lines: list[str | None] = markdown.split("\n")
    summary_at = lines.index("## Summary") + 1
    others = [s for s in content.SUMMARY_VARIANTS if s != lines[summary_at]]
    lines[summary_at] = rng.choice(others)
    spare = [b for job in content.BASE_EXPERIENCES for b in job.bullets if f"- {b}" not in lines]
    rng.shuffle(spare)
    bullets = [n for n, line in enumerate(lines) if line and line.startswith("- ")]
    rng.shuffle(bullets)
    result = "\n".join(line for line in lines if line is not None)
    for n in bullets:
        if edit_ratio(markdown, result) >= target:
            break
        lines[n] = f"- {spare.pop()}" if spare else None
        result = "\n".join(line for line in lines if line is not None)
    return result
