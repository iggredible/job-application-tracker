"""Keyword coverage: which of a posting's keywords a resume contains. Plain code, no AI.

`keyword_coverage()` is pure, so the review flow and the eval can call it directly. The result
is calculated on every request and never stored.
"""

import re
from dataclasses import dataclass

from app.models import PostingAnalysis, ReviewStatus
from app.repositories.applications import ApplicationRepository
from app.repositories.posting_analyses import PostingAnalysisRepository
from app.repositories.resumes import ResumeRepository
from app.services.applications import ApplicationNotFound


class NoAnalysis(Exception):
    """The application has no analysis to take keywords from (none, or only rejected ones)."""


class ResumeNotFound(Exception):
    """No base resume exists, or the resume is not the base resume or one of this application's."""


@dataclass(frozen=True)
class Coverage:
    covered: list[str]
    missing: list[str]
    ratio: float


@dataclass(frozen=True)
class ApplicationCoverage:
    """Coverage of one resume. When a resume other than the base was asked for, `base` and the
    two comparisons are filled in; otherwise they are None."""

    coverage: Coverage
    base: Coverage | None = None
    newly_covered: list[str] | None = None
    still_missing: list[str] | None = None


def _normalize(text: str) -> str:
    """Case-folded, with every run of whitespace collapsed to one space."""
    return " ".join(text.casefold().split())


def _pattern(keyword: str) -> re.Pattern[str]:
    """The keyword as a literal, whole-word phrase.

    `\\b` cannot be used: it needs a word character beside it, and terms such as `c++` and
    `.net` start or end with punctuation. Instead the match must not touch a word character on
    either side, so `java` is not found in `javascript` and `.net` is not found in `asp.net`.
    The keyword is already normalized, so its spaces are single.
    """
    return re.compile(rf"(?<!\w){re.escape(keyword)}(?!\w)")


def keyword_coverage(keywords: list[str], resume_text: str) -> Coverage:
    """Split the keywords into those the text contains and those it does not.

    Matching ignores case and whitespace differences, uses whole words, and takes every
    character literally. A keyword with several words must appear as that phrase. Blank
    keywords are dropped and repeats (in any case) count once. `covered` and `missing` keep the
    order and casing of the input. The ratio is covered over all distinct keywords, and 0.0
    when there are none.
    """
    text = _normalize(resume_text)
    covered: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        key = _normalize(keyword)
        if not key or key in seen:
            continue
        seen.add(key)
        (covered if _pattern(key).search(text) else missing).append(keyword)
    total = len(covered) + len(missing)
    return Coverage(covered=covered, missing=missing, ratio=len(covered) / total if total else 0.0)


def _analysis_to_use(analyses: list[PostingAnalysis]) -> PostingAnalysis | None:
    """The latest approved analysis, else the latest draft. A rejected one is never used.
    `analyses` is newest first."""
    for wanted in (ReviewStatus.APPROVED, ReviewStatus.DRAFT):
        for analysis in analyses:
            if analysis.status is wanted:
                return analysis
    return None


class CoverageService:
    def __init__(
        self,
        analyses: PostingAnalysisRepository,
        applications: ApplicationRepository,
        resumes: ResumeRepository,
    ) -> None:
        self._analyses = analyses
        self._applications = applications
        self._resumes = resumes

    def for_application(
        self, application_id: int, resume_id: int | None = None
    ) -> ApplicationCoverage:
        """Coverage of the base resume, or of `resume_id` compared with the base resume.

        `resume_id` must be the base resume or one that belongs to this application.
        """
        if self._applications.get(application_id) is None:
            raise ApplicationNotFound
        analysis = _analysis_to_use(self._analyses.list_for_application(application_id))
        if analysis is None:
            raise NoAnalysis
        keywords = analysis.keywords

        base = self._resumes.get_base()
        if base is None:
            raise ResumeNotFound
        base_coverage = keyword_coverage(keywords, base.content_markdown)
        if resume_id is None:
            return ApplicationCoverage(coverage=base_coverage)

        resume = self._resumes.get(resume_id)
        if resume is None or resume.application_id not in (None, application_id):
            raise ResumeNotFound
        coverage = keyword_coverage(keywords, resume.content_markdown)
        was_covered = set(base_coverage.covered)
        was_missing = set(base_coverage.missing)
        return ApplicationCoverage(
            coverage=coverage,
            base=base_coverage,
            newly_covered=[k for k in coverage.covered if k not in was_covered],
            still_missing=[k for k in coverage.missing if k in was_missing],
        )
