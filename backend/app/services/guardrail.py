"""The guardrail check: does every hard fact in a tailored draft exist in the base resume?

Plain code, no AI. `check()` runs once, on the model's structured output, and its flags are
stored as generated. `current_flags()` recalculates what the user sees from the text as it is
now, so editing the draft updates the flags.

Matching rule: normalize both sides (lowercase, collapse whitespace, en and em dashes become
hyphens, `**` bold marks removed), then match whole tokens or phrases on word boundaries. Never
raw substrings: `Go` does not match `Google`, and `5` does not match `2025`.
"""

import re
from dataclasses import dataclass

from app.ai.schemas import TailoredResume
from app.services.rendering import find_headings


@dataclass(frozen=True)
class Flag:
    """One fact in the draft that the base resume does not support. `message` is what the user
    reads, for example `Skill "Kubernetes"`."""

    field: str
    value: str
    message: str


# Flags are listed in this order, so `check()` and `current_flags()` agree on an untouched draft.
FIELDS = ("employer", "title", "dates", "number", "skill", "keyword")
# These stay while their value is in the text. The others are recalculated from the text.
STRUCTURAL = ("employer", "title", "dates", "skill")
LABELS = {
    "employer": "Employer",
    "title": "Title",
    "dates": "Dates",
    "number": "Number",
    "skill": "Skill",
    "keyword": "Keyword",
}

# A number token starts at a digit (after an optional `$`) and takes everything glued to it:
# digits, `,` `.` `%` and letters. The letters are how resumes write a quantity:
#   `10k`   = 10 thousand (users, requests)     `$2M`  = 2 million dollars
#   `5x`    = five times (faster, cheaper)      `$1.2B` = 1.2 billion dollars
#   `3.5yrs`, `40%`, `1,500` are tokens too.
# The spec names only a trailing k, m or x; any letters are taken here, so each of these is one
# whole token. The match never stops partway, which would let `$1.5B` pass as `$1`.
# It must not start inside a word, so the 3 in `S3` and `Python3` is not a number. A trailing
# `.` or `,` is punctuation, and is stripped after matching.
_NUMBER = re.compile(r"(?<![\w$.,])\$?\d[\w.,%]*")
_YEAR = re.compile(r"(?<!\w)(?:19|20)\d{2}(?!\w)")
# Whole month words only, so `Marketing` is not March. Compared by their first three letters.
_MONTH = re.compile(
    r"(?<!\w)(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?(?!\w)"
)
_BULLET = re.compile(r"^\s*[-*+]\s+")


def _normalize(text: str) -> str:
    """Lowercase, en and em dashes as hyphens, `**` removed, every run of whitespace as one space.

    `**` is removed with no space in its place: `**Lead** Software` becomes `lead software`, and
    `**Go**ogle` becomes `google`. No other Markdown mark is removed.
    """
    return " ".join(text.casefold().replace("–", "-").replace("—", "-").replace("**", "").split())


def _found(normalized_text: str, value: str) -> bool:
    """Whether the value appears in the (already normalized) text as a whole word or phrase.

    `\\b` cannot be used: terms such as `c++` and `.net` start or end with punctuation. The match
    must not touch a word character on either side instead.
    """
    phrase = _normalize(value)
    return bool(phrase) and bool(re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", normalized_text))


def _flag(field: str, value: str, detail: str = "") -> Flag:
    return Flag(field=field, value=value, message=f'{LABELS[field]} "{value}"{detail}')


def _ordered(flags: list[Flag]) -> list[Flag]:
    return sorted(flags, key=lambda flag: FIELDS.index(flag.field))  # stable


def _numbers(text: str) -> list[tuple[str, str]]:
    """(token as written, key) for each number in the text."""
    found = []
    for match in _NUMBER.finditer(text):
        token = match[0].rstrip(".,")
        found.append((token, token.casefold()))
    return found


def _dates_facts(text: str) -> tuple[set[str], set[str]]:
    """The years and the months (first three letters) in the text."""
    years = set(_YEAR.findall(text))
    months = {match[1][:3] for match in _MONTH.finditer(text.casefold())}
    return years, months


def _number_flags(lines: list[str], base_text: str) -> list[Flag]:
    """A flag for each distinct number in the lines that the base resume does not have, with the
    start of its first line as context."""
    known = {key for _, key in _numbers(base_text)}
    flags: dict[str, Flag] = {}
    for line in lines:
        for match in _NUMBER.finditer(line):
            token = match[0].rstrip(".,")
            if token.casefold() in known or token.casefold() in flags:
                continue
            end = match.start() + len(token)
            more = line[end:].strip(" .,;:") != ""
            flags[token.casefold()] = _flag(
                "number", token, f' in "{line[:end]}{"…" if more else ""}"'
            )
    return list(flags.values())


def _keyword_flags(keywords: list[str], draft_lines: list[str], base_normalized: str) -> list[Flag]:
    """A flag for each keyword that the draft uses and the base resume does not have."""
    draft = _normalize("\n".join(draft_lines))
    flags: dict[str, Flag] = {}
    for keyword in keywords:
        key = _normalize(keyword)
        if key and key not in flags and _found(draft, key) and not _found(base_normalized, key):
            flags[key] = _flag("keyword", keyword)
    return list(flags.values())


def check(tailored: TailoredResume, base_text: str, keywords: list[str]) -> list[Flag]:
    """Flag every fact in the structured draft that the base resume does not support.

    Employers, titles and skills must be found in the base resume. Dates are flagged when a year
    or a month in them is not in it ("Present" and "Current" are ignored). A number in the
    summary or a bullet must be a number in the base resume. An approved analysis keyword that
    the draft uses (summary, bullets or skills) must be in the base resume too.
    """
    base = _normalize(base_text)
    base_years, base_months = _dates_facts(base_text)
    flags: list[Flag] = []
    seen: set[tuple[str, str]] = set()

    def add_structural(field: str, value: str) -> None:
        key = (field, _normalize(value))
        if key[1] and key not in seen and not _found(base, value):
            seen.add(key)
            flags.append(_flag(field, value))

    for job in tailored.experiences:
        add_structural("employer", job.employer)
        add_structural("title", job.title)
        years, months = _dates_facts(job.dates)
        key = ("dates", _normalize(job.dates))
        if (years - base_years or months - base_months) and key not in seen:
            seen.add(key)
            flags.append(_flag("dates", job.dates))
    for skill in tailored.skills:
        add_structural("skill", skill)

    prose = [tailored.summary.strip(), *(b for job in tailored.experiences for b in job.bullets)]
    flags.extend(_number_flags(prose, base_text))
    flags.extend(_keyword_flags(keywords, [*prose, ", ".join(tailored.skills)], base))
    return _ordered(flags)


def _markdown_lines(markdown: str) -> tuple[list[str], list[str]]:
    """(lines to check for numbers, lines to check for keywords) in the draft's Markdown.

    Numbers are checked in the summary and in bullets. Keywords are checked in those and in the
    skills. Headings are never checked: a job's dates and title are structural fields. Other
    sections are copied from the base resume, so they cannot hold anything it lacks.
    """
    lines = markdown.split("\n")
    names = {index: name for index, _, name in find_headings(lines)}
    section = ""
    numbers: list[str] = []
    keywords: list[str] = []
    for index, line in enumerate(lines):
        if index in names:
            section = names[index]
            continue
        if not line.strip():
            continue
        bullet = _BULLET.match(line)
        text = line[bullet.end() :] if bullet else line.strip()
        if bullet or section == "summary":
            numbers.append(text)
        if bullet or section in ("summary", "skills"):
            keywords.append(text)
    return numbers, keywords


def current_flags(
    flags: list[Flag], content_markdown: str, base_text: str, keywords: list[str]
) -> list[Flag]:
    """The flags to show beside the draft as it is now.

    A stored structural flag (employer, title, dates, skill) stays only while its value is still
    in the text. Number and keyword flags are calculated again from the text, so a number or a
    keyword the user adds is flagged too. A structural fact the user adds is not re-checked.
    """
    text = _normalize(content_markdown)
    numbers, draft = _markdown_lines(content_markdown)
    kept = [flag for flag in flags if flag.field in STRUCTURAL and _found(text, flag.value)]
    fresh = _number_flags(numbers, base_text) + _keyword_flags(
        keywords, draft, _normalize(base_text)
    )
    return _ordered(kept + fresh)
