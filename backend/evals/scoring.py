"""Score one fixture's draft. Pure: no I/O and no AI, so a unit test can run it in CI.

A fixture passes when all of these hold:

- no flag on employer, title, dates or numbers (`FAILING_FIELDS`)
- none of its forbidden skills appear in the draft
- draft coverage is not lower than the base resume's

Skill and keyword flags are reported but never fail a fixture.
"""

from dataclasses import dataclass, field

from app.ai.schemas import TailoredResume
from app.services.coverage import keyword_coverage
from app.services.guardrail import Flag, check
from app.services.rendering import render_tailored_markdown

FAILING_FIELDS = ("employer", "title", "dates", "number")


@dataclass(frozen=True)
class FixtureScore:
    name: str
    flags: list[Flag] = field(default_factory=list)
    forbidden_found: list[str] = field(default_factory=list)
    base_coverage: float = 0.0
    draft_coverage: float = 0.0
    passed: bool = False
    failures: list[str] = field(default_factory=list)
    # Set when a call failed, so there was no draft to score.
    error: str | None = None


def score_fixture(
    name: str,
    *,
    base_resume: str,
    keywords: list[str],
    tailored: TailoredResume,
    forbidden_skills: list[str],
) -> FixtureScore:
    # Flags come from the structured output, as in the app. Coverage and forbidden skills are
    # measured on the rendered Markdown, which is what the user would read.
    markdown = render_tailored_markdown(base_resume, tailored)
    flags = check(tailored, base_resume, keywords)
    forbidden_found = keyword_coverage(forbidden_skills, markdown).covered
    base = keyword_coverage(keywords, base_resume).ratio
    draft = keyword_coverage(keywords, markdown).ratio

    failing_flags = [flag for flag in flags if flag.field in FAILING_FIELDS]
    failures = [f"{flag.message} is not in the base resume" for flag in failing_flags]
    failures += [f"forbidden skill in the draft: {skill}" for skill in forbidden_found]
    if draft < base:
        failures.append(f"coverage dropped ({base:.0%} to {draft:.0%})")

    return FixtureScore(
        name=name,
        flags=flags,
        forbidden_found=forbidden_found,
        base_coverage=base,
        draft_coverage=draft,
        passed=not failures,
        failures=failures,
    )


def score_error(name: str, error: str) -> FixtureScore:
    """A fixture whose call failed. There is no draft, so it fails with the error as the reason."""
    return FixtureScore(name=name, failures=[error], error=error)
