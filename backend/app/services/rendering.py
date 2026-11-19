"""Render a tailored resume into the base resume's Markdown, by plain code. No AI.

The base resume is split by headings. A section headed Summary, Experience or Skills
(case-insensitive) is replaced by the model's output, and everything else is copied through
unchanged. A section the base lacks is added after the header.
"""

import re
from collections.abc import Callable

from app.ai.schemas import TailoredResume

_HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
_FENCE = re.compile(r"^ {0,3}(```|~~~)")

# Each returns the body lines of its section, or nothing when the model gave nothing for it.
# `level` is the heading level of the section, so job entries sit one level below it.
type _Body = Callable[[TailoredResume, int], list[str]]


def _summary(tailored: TailoredResume, level: int) -> list[str]:
    return [tailored.summary.strip()] if tailored.summary.strip() else []


def _experience(tailored: TailoredResume, level: int) -> list[str]:
    lines: list[str] = []
    for job in tailored.experiences:
        if lines:
            lines.append("")
        lines.append(f"{'#' * (level + 1)} {job.title} — {job.employer} ({job.dates})")
        lines.extend(f"- {bullet}" for bullet in job.bullets)
    return lines


def _skills(tailored: TailoredResume, level: int) -> list[str]:
    return [", ".join(tailored.skills)] if tailored.skills else []


_SECTIONS: dict[str, _Body] = {"summary": _summary, "experience": _experience, "skills": _skills}


def _headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """(line index, level, lowercase name) of every heading outside a fenced code block."""
    found = []
    in_fence = False
    for index, line in enumerate(lines):
        if _FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence and (match := _HEADING.match(line)):
            found.append((index, len(match[1]), match[2].strip().rstrip(":").casefold()))
    return found


def render_tailored_markdown(base_markdown: str, tailored: TailoredResume) -> str:
    lines = base_markdown.split("\n")
    headings = _headings(lines)

    # The header is the text before the first heading, plus a leading `#` title and its body.
    header_end = headings[0][0] if headings else len(lines)
    if headings and headings[0][1] == 1 and headings[0][2] not in _SECTIONS:
        header_end = headings[1][0] if len(headings) > 1 else len(lines)

    out: list[str] = []
    present: set[str] = set()
    position = 0
    for n, (start, level, name) in enumerate(headings):
        if name not in _SECTIONS or name in present or start < position:
            continue  # not a section to replace, a repeat, or inside one already replaced
        present.add(name)
        # A section runs to the next heading of the same or a higher level.
        end = next((i for i, lv, _ in headings[n + 1 :] if lv <= level), len(lines))
        body = _SECTIONS[name](tailored, level)
        out.extend(lines[position:start])
        section = lines[start:end]
        if body:
            # Keep the blank lines that separated this section from the next one.
            blanks = next((i for i, text in enumerate(reversed(section)) if text.strip()), 0)
            out.extend([lines[start], *body, *[""] * blanks])
        else:
            out.extend(section)  # nothing from the model: keep the base section
        position = end
    out.extend(lines[position:])

    added = [
        [f"## {name.capitalize()}", *body]
        for name, make in _SECTIONS.items()
        if name not in present and (body := make(tailored, 2))
    ]
    if added:
        header, rest = out[:header_end], out[header_end:]
        while header and not header[-1].strip():
            header.pop()
        out = [*header, *([""] if header else [])]
        for block in added:
            out.extend([*block, ""])
        out.extend(rest)
    return "\n".join(out)
