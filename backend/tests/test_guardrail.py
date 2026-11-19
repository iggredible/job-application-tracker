"""The guardrail check: `check()` on the model's output and `current_flags()` on the edited text.

Both are pure. Every flag type has a test, and so do the matching rules that are easy to get
wrong: whole tokens only, number tokens, reformatted dates and the edit cases.
"""

from app.ai.schemas import Experience, TailoredResume
from app.services.guardrail import Flag, check, current_flags
from app.services.rendering import render_tailored_markdown

BASE = """# Jordan Avery
Lead Software Engineer · Austin, TX

## Experience
### Lead Software Engineer — Coldline Logistics (Jun 2021 – May 2026)
- Led a team of 5 building shipment tracking in Rails
- Moved slow reports to background jobs with Sidekiq

### Software Engineer — Harbor Mortgage (2018 — 2021)
- Built REST APIs on Rails and PostgreSQL for loan servicing

## Skills
Ruby on Rails, PostgreSQL, Sidekiq, REST APIs, NetSuite, RSpec
"""

KEYWORDS = ["ruby on rails", "postgresql", "kubernetes"]


def job(**overrides: object) -> Experience:
    fields: dict[str, object] = {
        "employer": "Coldline Logistics",
        "title": "Lead Software Engineer",
        "dates": "Jun 2021 — May 2026",
        "bullets": ["Led a team of 5 building shipment tracking in Rails"],
    }
    fields.update(overrides)
    return Experience(**fields)  # type: ignore[arg-type]


def draft(
    *,
    summary: str = "Backend lead on Ruby on Rails and PostgreSQL.",
    experiences: list[Experience] | None = None,
    skills: list[str] | None = None,
) -> TailoredResume:
    """A draft that is clean against BASE unless a test changes something."""
    return TailoredResume(
        summary=summary,
        experiences=[job()] if experiences is None else experiences,
        skills=["Ruby on Rails", "PostgreSQL"] if skills is None else skills,
    )


def pairs(flags: list[Flag]) -> list[tuple[str, str]]:
    return [(flag.field, flag.value) for flag in flags]


def only(flags: list[Flag], field: str) -> list[str]:
    return [flag.value for flag in flags if flag.field == field]


# --- check(): one test per flag type ------------------------------------------------------------


def test_a_clean_draft_has_no_flags() -> None:
    assert check(draft(), BASE, KEYWORDS) == []


def test_an_employer_not_in_the_base_resume_is_flagged() -> None:
    flags = check(draft(experiences=[job(employer="Acme Corp")]), BASE, KEYWORDS)

    assert pairs(flags) == [("employer", "Acme Corp")]
    assert flags[0].message == 'Employer "Acme Corp"'


def test_a_title_not_in_the_base_resume_is_flagged() -> None:
    flags = check(draft(experiences=[job(title="Principal Engineer")]), BASE, KEYWORDS)

    assert pairs(flags) == [("title", "Principal Engineer")]
    assert flags[0].message == 'Title "Principal Engineer"'


def test_a_year_not_in_the_base_resume_flags_the_dates() -> None:
    flags = check(draft(experiences=[job(dates="Jun 2021 — May 2027")]), BASE, KEYWORDS)

    assert pairs(flags) == [("dates", "Jun 2021 — May 2027")]
    assert flags[0].message == 'Dates "Jun 2021 — May 2027"'


def test_a_month_not_in_the_base_resume_flags_the_dates() -> None:
    flags = check(draft(experiences=[job(dates="Sep 2021 — May 2026")]), BASE, KEYWORDS)

    assert pairs(flags) == [("dates", "Sep 2021 — May 2026")]


def test_a_skill_not_in_the_base_resume_is_flagged() -> None:
    flags = check(draft(skills=["Ruby on Rails", "Kubernetes"]), BASE, [])

    assert pairs(flags) == [("skill", "Kubernetes")]
    assert flags[0].message == 'Skill "Kubernetes"'


def test_a_number_in_a_bullet_that_is_not_in_the_base_resume_is_flagged() -> None:
    bullet = "Cut report run time by 40% by moving work to Sidekiq background jobs"
    flags = check(draft(experiences=[job(bullets=[bullet])]), BASE, KEYWORDS)

    assert pairs(flags) == [("number", "40%")]
    assert flags[0].message == 'Number "40%" in "Cut report run time by 40%…"'


def test_a_number_in_the_summary_that_is_not_in_the_base_resume_is_flagged() -> None:
    flags = check(draft(summary="Backend lead with 12 years of Rails."), BASE, KEYWORDS)

    assert pairs(flags) == [("number", "12")]
    assert flags[0].message == 'Number "12" in "Backend lead with 12…"'


def test_an_approved_keyword_in_the_draft_but_not_in_the_base_resume_is_flagged() -> None:
    flags = check(draft(summary="Backend lead who ships on Kubernetes."), BASE, KEYWORDS)

    assert pairs(flags) == [("keyword", "kubernetes")]
    assert flags[0].message == 'Keyword "kubernetes"'


def test_a_keyword_is_found_in_a_bullet_and_in_the_skills() -> None:
    bullet = "Ran Kubernetes clusters"
    in_bullet = check(draft(experiences=[job(bullets=[bullet])]), BASE, KEYWORDS)
    in_skills = check(draft(skills=["Kubernetes"]), BASE, KEYWORDS)

    assert only(in_bullet, "keyword") == ["kubernetes"]
    assert only(in_skills, "keyword") == ["kubernetes"]
    assert only(in_skills, "skill") == ["Kubernetes"]  # the skill is flagged on its own as well


def test_a_keyword_the_draft_does_not_use_is_not_flagged() -> None:
    # The posting wants it and the resume lacks it: that is a missing keyword (coverage), not a
    # flag about the draft.
    assert check(draft(), BASE, ["kubernetes", "terraform"]) == []


def test_a_keyword_that_is_in_the_base_resume_is_not_flagged() -> None:
    assert check(draft(summary="Sidekiq expert."), BASE, ["sidekiq"]) == []


def test_each_flag_is_listed_once() -> None:
    flags = check(
        draft(
            experiences=[job(employer="Acme Corp"), job(employer="Acme Corp", title="Founder")],
            skills=["Kubernetes", "kubernetes"],
        ),
        BASE,
        [],
    )

    assert only(flags, "employer") == ["Acme Corp"]
    assert only(flags, "skill") == ["Kubernetes"]


def test_flags_come_in_a_fixed_order_by_field() -> None:
    flags = check(
        draft(
            summary="Backend lead on Kubernetes with 12 years.",
            experiences=[job(employer="Acme Corp", title="Founder", dates="2030")],
            skills=["Terraform"],
        ),
        BASE,
        ["kubernetes"],
    )

    assert [flag.field for flag in flags] == [
        "employer",
        "title",
        "dates",
        "number",
        "skill",
        "keyword",
    ]


# --- check(): matching rules --------------------------------------------------------------------


def test_go_does_not_match_google() -> None:
    base = "## Skills\nPython\n\n## Experience\nWorked at Google on search.\n"

    flags = check(draft(experiences=[], skills=["Go"]), base, [])

    assert pairs(flags) == [("skill", "Go")]


def test_go_matches_the_word_go() -> None:
    base = "## Skills\nPython, Go\n"

    assert check(draft(experiences=[], skills=["Go"]), base, []) == []


def test_a_skill_with_punctuation_matches_as_a_whole_phrase() -> None:
    base = "## Skills\nC++, ASP.NET\n"

    assert check(draft(experiences=[], skills=["C++"]), base, []) == []
    # `.NET` touches the word character `P` in `ASP.NET`, so it is not found there.
    assert pairs(check(draft(experiences=[], skills=[".NET"]), base, [])) == [("skill", ".NET")]


def test_a_number_does_not_pass_because_a_longer_number_contains_it() -> None:
    base = "## Experience\n- Shipped in 2025 and again in 2026\n"
    flags = check(
        draft(experiences=[job(bullets=["Led 5 engineers"])], summary="Backend lead."), base, []
    )

    assert only(flags, "number") == ["5"]


def test_a_number_in_the_base_resume_passes() -> None:
    base = "## Experience\n- Led 5 engineers\n"

    flags = check(draft(experiences=[job(bullets=["Led 5 engineers."])]), base, [])

    assert only(flags, "number") == []  # the full stop is not part of the token


def test_number_tokens_take_symbols_and_a_trailing_k_m_or_x() -> None:
    bullet = "Saved $2M, 1,500 hours, 3.5 days, 10k users, 40% of cost and ran 5x faster"
    flags = check(draft(experiences=[job(bullets=[bullet])]), BASE, [])

    assert only(flags, "number") == ["$2M", "1,500", "3.5", "10k", "40%", "5x"]


def test_a_number_token_is_compared_without_regard_to_case() -> None:
    base = "## Experience\n- Saved $2m\n"

    flags = check(draft(experiences=[job(bullets=["Saved $2M"])]), base, [])

    assert only(flags, "number") == []


def test_digits_inside_a_word_are_not_number_tokens() -> None:
    bullet = "Stored files in S3 on EC2 and moved to Python3 in the v2.5 release"
    flags = check(draft(experiences=[job(bullets=[bullet])]), BASE, [])

    assert only(flags, "number") == []


def test_a_number_glued_to_letters_is_one_whole_token() -> None:
    # Not just k, m and x: the letters belong to the token, so `$1.2B` is not read as `$1`.
    bullet = "Grew revenue to $1.5B, cut 3.7yrs of delay, saved 1.5h per run and shipped on the 1st"
    flags = check(draft(experiences=[job(bullets=[bullet])]), BASE, [])

    assert only(flags, "number") == ["$1.5B", "3.7yrs", "1.5h", "1st"]


def test_a_changed_figure_with_a_letter_suffix_is_flagged() -> None:
    base = "## Experience\n- Grew revenue to $1.2B and cut 3.5yrs of delay\n"
    bullet = "Grew revenue to $1.5B and cut 3.7yrs of delay"

    flags = check(draft(experiences=[job(bullets=[bullet])]), base, [])

    assert only(flags, "number") == ["$1.5B", "3.7yrs"]


def test_the_same_figure_with_a_letter_suffix_passes() -> None:
    base = "## Experience\n- Grew revenue to $1.2B and cut 3.5yrs of delay\n"
    bullet = "Grew revenue to $1.2b, then cut 3.5yrs of delay."

    assert only(check(draft(experiences=[job(bullets=[bullet])]), base, []), "number") == []


def test_a_changed_figure_with_a_letter_suffix_is_flagged_in_the_edited_text() -> None:
    base = "## Experience\n- Grew revenue to $1.2B\n"

    flags = current_flags([], "## Experience\n- Grew revenue to $1.5B\n", base, [])

    assert only(flags, "number") == ["$1.5B"]


def test_numbers_in_dates_are_checked_as_dates_not_as_numbers() -> None:
    flags = check(draft(experiences=[job(dates="2030 — 2031")]), BASE, [])

    assert pairs(flags) == [("dates", "2030 — 2031")]


def test_a_reformatted_date_passes() -> None:
    # Longer month names, a hyphen for an en dash, and Present or Current for an end date.
    for dates in (
        "June 2021 - May 2026",
        "Jun 2021 – May 2026",
        "June 2021 — Present",
        "2018 – Current",
        "2018 - 2021",
    ):
        assert check(draft(experiences=[job(dates=dates)]), BASE, []) == [], dates


def test_a_word_that_only_starts_like_a_month_is_not_a_month() -> None:
    base = "## Experience\n- Marketing lead in 2020\n"

    flags = check(draft(experiences=[job(dates="Mar 2020")], summary="Lead."), base, [])

    assert only(flags, "dates") == ["Mar 2020"]


def test_a_month_in_the_base_resume_is_matched_by_its_first_three_letters() -> None:
    base = "## Experience\n- Joined in September 2019\n"

    flags = check(draft(experiences=[job(dates="Sept 2019")], summary="Lead."), base, [])

    assert only(flags, "dates") == []


def test_matching_ignores_case_whitespace_and_dash_style() -> None:
    base = "### Senior Engineer – Platform Team, Coldline  Logistics\n"

    flags = check(
        draft(
            experiences=[
                job(title="SENIOR engineer — platform team", employer="coldline\nlogistics")
            ],
            summary="Lead.",
        ),
        base,
        [],
    )

    assert only(flags, "title") == []
    assert only(flags, "employer") == []


# --- current_flags(): what the user sees --------------------------------------------------------

DIRTY = draft(
    summary="Backend lead who ships on Kubernetes.",
    experiences=[
        job(
            employer="Acme Corp",
            title="Principal Engineer",
            dates="Jun 2021 — May 2027",
            bullets=["Cut report run time by 40%"],
        )
    ],
    skills=["Ruby on Rails", "Kubernetes"],
)


def test_current_flags_equal_the_stored_flags_for_an_untouched_draft() -> None:
    stored = check(DIRTY, BASE, KEYWORDS)
    markdown = render_tailored_markdown(BASE, DIRTY)

    assert [flag.field for flag in stored] == [
        "employer",
        "title",
        "dates",
        "number",
        "skill",
        "keyword",
    ]
    assert current_flags(stored, markdown, BASE, KEYWORDS) == stored


def test_a_flagged_skill_drops_out_when_it_is_removed_from_the_text() -> None:
    stored = check(draft(skills=["Ruby on Rails", "Kubernetes"]), BASE, [])
    markdown = render_tailored_markdown(BASE, draft(skills=["Ruby on Rails", "Kubernetes"]))
    assert pairs(current_flags(stored, markdown, BASE, [])) == [("skill", "Kubernetes")]

    edited = markdown.replace(", Kubernetes", "")

    assert current_flags(stored, edited, BASE, []) == []


def test_a_structural_flag_stays_while_its_value_is_in_the_text() -> None:
    stored = check(DIRTY, BASE, [])
    markdown = render_tailored_markdown(BASE, DIRTY)

    edited = markdown.replace("Cut report run time by 40%", "Cut report run time")
    flags = current_flags(stored, edited, BASE, [])

    assert [flag.field for flag in flags] == ["employer", "title", "dates", "skill"]


def test_a_structural_flag_drops_out_when_its_value_is_removed() -> None:
    stored = check(DIRTY, BASE, [])
    markdown = render_tailored_markdown(BASE, DIRTY)

    edited = markdown.replace("Acme Corp", "Coldline Logistics").replace(
        "Principal Engineer", "Lead Software Engineer"
    )
    flags = current_flags(stored, edited, BASE, [])

    assert [flag.field for flag in flags] == ["dates", "number", "skill"]


def test_a_dates_flag_is_found_in_the_text_whatever_the_dash_style() -> None:
    stored = [Flag("dates", "Jun 2021 — May 2027", 'Dates "Jun 2021 — May 2027"')]

    text = "### Lead — Coldline Logistics (Jun 2021 – May 2027)\n"

    assert current_flags(stored, text, BASE, []) == stored


def test_a_number_flag_is_recalculated_from_the_text() -> None:
    stored = check(DIRTY, BASE, [])
    markdown = render_tailored_markdown(BASE, DIRTY)

    removed = current_flags(
        stored, markdown.replace("Cut report run time by 40%", "Cut time"), BASE, []
    )
    added = current_flags(stored, markdown + "\n- Saved $9M a year\n", BASE, [])

    assert only(removed, "number") == []
    assert only(added, "number") == ["40%", "$9M"]


def test_a_number_the_user_adds_to_the_summary_is_flagged() -> None:
    markdown = "## Summary\nBackend lead with 12 years of Rails.\n"

    flags = current_flags([], markdown, BASE, [])

    assert pairs(flags) == [("number", "12")]


def test_a_number_that_the_user_changes_to_one_in_the_base_resume_is_not_flagged() -> None:
    stored = [Flag("number", "7", 'Number "7" in "Led 7…"')]

    flags = current_flags(stored, "## Experience\n- Led 5 engineers\n", BASE, [])

    assert flags == []


def test_a_keyword_flag_is_recalculated_from_the_text() -> None:
    stored = [Flag("keyword", "kubernetes", 'Keyword "kubernetes"')]

    gone = current_flags(stored, "## Summary\nBackend lead.\n", BASE, KEYWORDS)
    added = current_flags([], "## Skills\nRuby on Rails, Kubernetes\n", BASE, KEYWORDS)

    assert gone == []
    assert only(added, "keyword") == ["kubernetes"]


def test_a_keyword_in_a_base_copied_section_is_not_flagged() -> None:
    # Sections other than summary, bullets and skills are not part of the keyword check.
    markdown = "## Education\nKubernetes certification\n"

    assert current_flags([], markdown, BASE, KEYWORDS) == []


def test_headings_are_not_scanned_for_numbers_or_keywords() -> None:
    markdown = "### Kubernetes Lead — Acme (2030 — 2031)\n"

    assert current_flags([], markdown, BASE, KEYWORDS) == []


def test_the_summary_is_found_under_any_heading_level_and_case() -> None:
    markdown = "# SUMMARY:\nLed 12 people.\n"

    assert only(current_flags([], markdown, BASE, []), "number") == ["12"]
