"""Load the fixtures from `evals/fixtures/<name>/`.

Each folder holds `posting.txt`, `resume.md` and `expect.json` (`{"forbidden_skills": [...]}`).
A forbidden skill is one the posting demands and the resume lacks. The loader rejects a fixture
whose resume has one, because an honest draft would then fail.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from app.services.coverage import keyword_coverage

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
FILES = ("posting.txt", "resume.md", "expect.json")


class FixtureError(Exception):
    """A fixture is missing a file or has bad content. The message names it."""


@dataclass(frozen=True)
class Fixture:
    name: str
    posting_text: str
    base_resume: str
    forbidden_skills: list[str]


def _load(folder: Path) -> Fixture:
    for filename in FILES:
        if not (folder / filename).is_file():
            raise FixtureError(f"fixture {folder.name}: {filename} is missing")
    try:
        expect = json.loads((folder / "expect.json").read_text())
    except json.JSONDecodeError as exc:
        raise FixtureError(f"fixture {folder.name}: expect.json is not valid JSON ({exc})") from exc
    skills = expect.get("forbidden_skills") if isinstance(expect, dict) else None
    if not isinstance(skills, list) or not all(isinstance(s, str) for s in skills):
        raise FixtureError(
            f"fixture {folder.name}: expect.json needs a forbidden_skills list of strings"
        )
    resume = (folder / "resume.md").read_text()
    present = keyword_coverage(skills, resume).covered
    if present:
        raise FixtureError(
            f"fixture {folder.name}: forbidden skill(s) {', '.join(present)} are in resume.md"
        )
    return Fixture(
        name=folder.name,
        posting_text=(folder / "posting.txt").read_text(),
        base_resume=resume,
        forbidden_skills=skills,
    )


def load_fixtures(root: Path = FIXTURES_DIR) -> list[Fixture]:
    folders = sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    if not folders:
        raise FixtureError(f"no fixtures in {root}")
    return [_load(folder) for folder in folders]
