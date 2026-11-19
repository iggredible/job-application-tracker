from pydantic import BaseModel


class CoverageRead(BaseModel):
    """Which keywords a resume contains. `ratio` is covered over all keywords, from 0 to 1."""

    covered: list[str]
    missing: list[str]
    ratio: float


class ApplicationCoverageRead(CoverageRead):
    """The same, and when a resume other than the base was asked for, how it compares with the
    base resume. The three comparison fields are left out of the response otherwise."""

    base: CoverageRead | None = None
    newly_covered: list[str] | None = None
    still_missing: list[str] | None = None
