"""render_tailored_markdown(): structured output into the base resume, by plain code."""

from app.ai.schemas import Experience, TailoredResume
from app.services.rendering import render_tailored_markdown

TAILORED = TailoredResume(
    summary="Backend lead on Ruby on Rails.",
    experiences=[
        Experience(
            employer="Coldline Logistics",
            title="Lead Software Engineer",
            dates="Jun 2021 — May 2026",
            bullets=["Led a team of 5", "Moved reports to background jobs"],
        ),
        Experience(
            employer="Harbor Mortgage",
            title="Software Engineer",
            dates="2018 — 2021",
            bullets=["Built REST APIs"],
        ),
    ],
    skills=["Ruby on Rails", "PostgreSQL"],
)

BASE = """\
# Jordan Avery
Lead Software Engineer · Austin, TX

## Summary
An old summary.

## Experience
### Lead Software Engineer — Coldline Logistics (Jun 2021 — May 2026)
- An old bullet

## Education
BS Computer Science, 2014

## Skills
Ruby, Sidekiq
"""

EXPECTED = """\
# Jordan Avery
Lead Software Engineer · Austin, TX

## Summary
Backend lead on Ruby on Rails.

## Experience
### Lead Software Engineer — Coldline Logistics (Jun 2021 — May 2026)
- Led a team of 5
- Moved reports to background jobs

### Software Engineer — Harbor Mortgage (2018 — 2021)
- Built REST APIs

## Education
BS Computer Science, 2014

## Skills
Ruby on Rails, PostgreSQL
"""


def test_summary_experience_and_skills_are_replaced_and_the_rest_is_copied() -> None:
    assert render_tailored_markdown(BASE, TAILORED) == EXPECTED


def test_the_sections_replaced_include_their_deeper_headings() -> None:
    result = render_tailored_markdown(BASE, TAILORED)

    assert "An old bullet" not in result
    assert result.count("### ") == 2  # the two generated jobs, not the old one


def test_headings_match_case_insensitively_and_keep_the_base_wording() -> None:
    base = "## SUMMARY\nold\n\n## experience\nold\n\n## SkIlLs\nold\n"

    result = render_tailored_markdown(base, TAILORED)

    assert result.startswith("## SUMMARY\nBackend lead on Ruby on Rails.\n")
    assert "\n## experience\n### Lead Software Engineer — Coldline Logistics" in result
    assert result.endswith("\n## SkIlLs\nRuby on Rails, PostgreSQL\n")


def test_other_sections_and_text_before_the_first_heading_are_copied_unchanged() -> None:
    base = (
        "Jordan Avery\njordan@example.com\n\n## Projects\n- A thing\n\n"
        "## Summary\nold\n\n## Experience\nold\n\n## Skills\nold\n"
    )

    result = render_tailored_markdown(base, TAILORED)

    assert result.startswith("Jordan Avery\njordan@example.com\n\n## Projects\n- A thing\n\n")


def test_a_heading_inside_a_code_block_does_not_end_a_section() -> None:
    base = "## Experience\nold\n```\n## Education\n```\n\n## Education\nBS\n"

    result = render_tailored_markdown(base, TAILORED)

    assert "```" not in result
    assert result.endswith("## Education\nBS\n")


def test_a_missing_section_is_added_after_the_header() -> None:
    base = "# Jordan Avery\nAustin, TX\n\n## Education\nBS\n"

    result = render_tailored_markdown(base, TAILORED)

    assert result == (
        "# Jordan Avery\nAustin, TX\n\n"
        "## Summary\nBackend lead on Ruby on Rails.\n\n"
        "## Experience\n"
        "### Lead Software Engineer — Coldline Logistics (Jun 2021 — May 2026)\n"
        "- Led a team of 5\n- Moved reports to background jobs\n\n"
        "### Software Engineer — Harbor Mortgage (2018 — 2021)\n- Built REST APIs\n\n"
        "## Skills\nRuby on Rails, PostgreSQL\n\n"
        "## Education\nBS\n"
    )


def test_only_the_missing_sections_are_added_and_the_present_one_is_replaced_in_place() -> None:
    base = "# Jordan Avery\n\n## Summary\nold\n\n## Education\nBS\n"

    result = render_tailored_markdown(base, TAILORED)

    assert result == (
        "# Jordan Avery\n\n"
        "## Experience\n"
        "### Lead Software Engineer — Coldline Logistics (Jun 2021 — May 2026)\n"
        "- Led a team of 5\n- Moved reports to background jobs\n\n"
        "### Software Engineer — Harbor Mortgage (2018 — 2021)\n- Built REST APIs\n\n"
        "## Skills\nRuby on Rails, PostgreSQL\n\n"
        "## Summary\nBackend lead on Ruby on Rails.\n\n"
        "## Education\nBS\n"
    )


def test_an_empty_part_of_the_output_leaves_the_base_section_unchanged() -> None:
    empty = TailoredResume(summary="  ", experiences=[], skills=[])

    assert render_tailored_markdown(BASE, empty) == BASE


def test_a_base_without_headings_gets_the_generated_sections_after_its_text() -> None:
    result = render_tailored_markdown("Jordan Avery\n", TAILORED)

    assert result.startswith("Jordan Avery\n\n## Summary\n")
    assert result.endswith("## Skills\nRuby on Rails, PostgreSQL\n")


def test_the_same_input_always_gives_the_same_markdown() -> None:
    assert render_tailored_markdown(BASE, TAILORED) == render_tailored_markdown(BASE, TAILORED)
