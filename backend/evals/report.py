"""The printed table and the results file. Plain formatting, no I/O."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from evals.scoring import FAILING_FIELDS, FixtureScore


@dataclass(frozen=True)
class FixtureRun:
    """A fixture's score and what its calls used, as logged by the in-memory sink."""

    score: FixtureScore
    input_tokens: int | None
    output_tokens: int | None
    cost: Decimal | None


def _percent(ratio: float) -> str:
    return f"{ratio:.0%}"


def format_table(scores: list[FixtureScore]) -> str:
    rows = []
    for score in scores:
        if score.error is not None:
            rows.append((score.name, "-", "-", "FAIL"))
        else:
            coverage = f"{_percent(score.base_coverage)} → {_percent(score.draft_coverage)}"
            rows.append(
                (score.name, str(len(score.flags)), coverage, "PASS" if score.passed else "FAIL")
            )
    header = ("fixture", "flags", "coverage (base → draft)", "result")
    widths = [max(len(row[i]) for row in [header, *rows]) for i in range(4)]

    def line(cells: tuple[str, ...]) -> str:
        return "  ".join(cell.ljust(width) for cell, width in zip(cells, widths, strict=True))

    lines = [line(header).rstrip(), "  ".join("-" * width for width in widths)]
    for score, row in zip(scores, rows, strict=True):
        lines.append(line(row).rstrip())
        lines.extend(f"    - {reason}" for reason in score.failures)
        # Flags that are reported but do not fail the fixture.
        lines.extend(
            f"    note: {flag.message} (reported only)"
            for flag in score.flags
            if flag.field not in FAILING_FIELDS
        )
    lines.append("")
    lines.append(f"{sum(s.passed for s in scores)} of {len(scores)} passed")
    return "\n".join(lines)


def results_file_name(analysis_version: str, tailor_version: str, model: str) -> str:
    return f"posting_analysis-{analysis_version}_tailor_resume-{tailor_version}_{model}.json"


def to_result_json(
    runs: list[FixtureRun], *, model: str, versions: dict[str, str], ran_at: datetime
) -> dict[str, Any]:
    """The results file. It keeps flags, coverage and usage, not the drafts, so a diff between
    two prompt versions stays readable."""
    return {
        "ran_at": ran_at.isoformat(),
        "model": model,
        "prompt_versions": versions,
        "passed": sum(run.score.passed for run in runs),
        "total": len(runs),
        "fixtures": [
            {
                "name": run.score.name,
                "passed": run.score.passed,
                "failures": run.score.failures,
                "flags": [
                    {"field": f.field, "value": f.value, "message": f.message}
                    for f in run.score.flags
                ],
                "forbidden_found": run.score.forbidden_found,
                "coverage": {"base": run.score.base_coverage, "draft": run.score.draft_coverage},
                "tokens": {"input": run.input_tokens, "output": run.output_tokens},
                "cost": str(run.cost) if run.cost is not None else None,
                "error": run.score.error,
            }
            for run in runs
        ],
    }
