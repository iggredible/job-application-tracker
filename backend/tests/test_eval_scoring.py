"""The eval's scoring: `score_fixture()` is pure, so these tests give it hand-built drafts.

The eval itself calls the real model and does not run in CI. This logic does.
"""

from app.ai.schemas import Experience, TailoredResume
from evals.scoring import FAILING_FIELDS, score_fixture

BASE = """# Jordan Avery
jordan@example.com

## Summary
Backend engineer.

## Experience
### Software Engineer — Acme Corp (2019 — 2024)
- Built REST services in Python and PostgreSQL
- Cut report time from 10 minutes to 2 minutes

## Skills
Python, PostgreSQL, Docker
"""

# The base resume has python, postgresql and docker, but not "rest apis": 3 of 4.
KEYWORDS = ["python", "postgresql", "rest apis", "docker"]


def job(**overrides: object) -> Experience:
    fields: dict[str, object] = {
        "employer": "Acme Corp",
        "title": "Software Engineer",
        "dates": "2019 — 2024",
        "bullets": [
            "Built REST APIs in Python and PostgreSQL",
            "Cut report time from 10 minutes to 2 minutes",
        ],
    }
    fields.update(overrides)
    return Experience(**fields)  # type: ignore[arg-type]


def draft(
    *,
    summary: str = "Backend engineer.",
    experiences: list[Experience] | None = None,
    skills: list[str] | None = None,
) -> TailoredResume:
    """A draft that passes against BASE: no failing flags, and it works "REST APIs" in, so its
    coverage is 4 of 4 against the base's 3 of 4."""
    return TailoredResume(
        summary=summary,
        experiences=[job()] if experiences is None else experiences,
        skills=["Python", "PostgreSQL", "Docker"] if skills is None else skills,
    )


def failing(result) -> list[tuple[str, str]]:  # noqa: ANN001
    """The flags that fail a fixture. A draft that gains coverage also gets a keyword flag, which
    is reported only, so the tests look at the failing fields."""
    return [(f.field, f.value) for f in result.flags if f.field in FAILING_FIELDS]


def score(
    tailored: TailoredResume,
    *,
    keywords: list[str] | None = None,
    forbidden: list[str] | None = None,
):
    return score_fixture(
        "fixture",
        base_resume=BASE,
        keywords=KEYWORDS if keywords is None else keywords,
        tailored=tailored,
        forbidden_skills=forbidden or [],
    )


def test_a_clean_draft_with_higher_coverage_passes() -> None:
    result = score(draft())

    assert result.passed
    assert result.failures == []
    assert (result.base_coverage, result.draft_coverage) == (0.75, 1.0)


def test_an_employer_flag_fails_the_fixture() -> None:
    result = score(draft(experiences=[job(employer="Globex")]))

    assert not result.passed
    assert failing(result) == [("employer", "Globex")]
    assert any('Employer "Globex"' in reason for reason in result.failures)


def test_a_title_flag_fails_the_fixture() -> None:
    result = score(draft(experiences=[job(title="Principal Engineer")]))

    assert not result.passed
    assert failing(result) == [("title", "Principal Engineer")]


def test_a_dates_flag_fails_the_fixture() -> None:
    result = score(draft(experiences=[job(dates="2015 — 2024")]))

    assert not result.passed
    assert failing(result) == [("dates", "2015 — 2024")]


def test_a_number_flag_fails_the_fixture() -> None:
    bullets = ["Built REST APIs in Python and PostgreSQL", "Cut report time by 40%"]
    result = score(draft(experiences=[job(bullets=bullets)]))

    assert not result.passed
    assert failing(result) == [("number", "40%")]


def test_a_forbidden_skill_in_the_draft_fails_the_fixture() -> None:
    tailored = draft(skills=["Python", "PostgreSQL", "Docker", "Kubernetes"])

    result = score(tailored, keywords=[*KEYWORDS, "kubernetes"], forbidden=["kubernetes"])

    assert not result.passed
    assert result.forbidden_found == ["kubernetes"]
    assert any("kubernetes" in reason for reason in result.failures)
    # Coverage went up, which is how a model that invents the skill would look good.
    assert result.draft_coverage > result.base_coverage


def test_a_forbidden_skill_is_matched_on_whole_words_only() -> None:
    # "Go" is not in "Google", and "Docker" does not contain it either.
    result = score(draft(summary="Backend engineer who reads Google docs."), forbidden=["go"])

    assert result.passed
    assert result.forbidden_found == []


def test_a_forbidden_skill_is_matched_whatever_its_case() -> None:
    result = score(draft(summary="Backend engineer using Terraform."), forbidden=["Terraform"])

    assert not result.passed
    assert result.forbidden_found == ["Terraform"]


def test_skill_and_keyword_flags_are_reported_but_do_not_fail() -> None:
    # "REST APIs" is a keyword the base resume lacks (a keyword flag); Kubernetes is a skill
    # flag. Neither is on the failing list, and nothing here is forbidden.
    tailored = draft(skills=["Python", "PostgreSQL", "Docker", "Kubernetes"])

    result = score(tailored)

    assert result.passed
    assert {f.field for f in result.flags} == {"keyword", "skill"}


def test_equal_coverage_passes_when_the_base_is_below_100_percent() -> None:
    # Coverage must not drop. A draft that keeps what the base resume had passes: an honest
    # draft cannot gain a keyword without also getting a keyword flag.
    result = score(draft(experiences=[job(bullets=["Built REST services in Python"])]))

    assert result.base_coverage == result.draft_coverage == 0.75
    assert result.passed
    assert result.failures == []


def test_lower_coverage_fails() -> None:
    result = score(draft(skills=["Python"], experiences=[job(bullets=["Built services."])]))

    assert result.draft_coverage < result.base_coverage
    assert not result.passed
    assert any("coverage dropped" in reason for reason in result.failures)


def test_equal_coverage_passes_when_the_base_is_already_at_100_percent() -> None:
    clean = draft(experiences=[job(bullets=["Built REST services in Python and PostgreSQL"])])

    result = score(clean, keywords=["python", "postgresql"])

    assert result.base_coverage == result.draft_coverage == 1.0
    assert result.passed


def test_a_draft_that_drops_coverage_fails_even_at_a_100_percent_base() -> None:
    # An empty skills list would keep the base's Skills section, so the draft names one skill.
    dropped = draft(skills=["Docker"], experiences=[job(bullets=["Built services."])])

    result = score(dropped, keywords=["python", "postgresql"])

    assert result.base_coverage == 1.0
    assert result.draft_coverage < 1.0
    assert not result.passed


def test_every_failure_is_listed_not_only_the_first() -> None:
    tailored = draft(
        experiences=[job(employer="Globex")], skills=["Python", "PostgreSQL", "Terraform"]
    )

    result = score(tailored, keywords=[*KEYWORDS, "terraform"], forbidden=["terraform"])

    assert not result.passed
    assert len(result.failures) == 2


def test_coverage_is_measured_on_the_rendered_draft_not_on_the_structure() -> None:
    # The draft has no Education section of its own, but the base's other sections are copied
    # through by the renderer, so a keyword there counts for both sides.
    base = BASE + "\n## Education\nB.Sc. Computer Science\n"

    result = score_fixture(
        "fixture",
        base_resume=base,
        keywords=["computer science", "rest apis"],
        tailored=draft(),
        forbidden_skills=[],
    )

    assert (result.base_coverage, result.draft_coverage) == (0.5, 1.0)
