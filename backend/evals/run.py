"""Run the prompt eval against the real model.

    make eval                      (or: cd backend && uv run python -m evals.run)
    make eval ARGS=--prompts=v2    (measure the v2 tailoring prompt; the default is v1)

Run it by hand when a prompt or the model changes. It costs money and the model's output varies
between runs, so it never runs in CI. It needs ANTHROPIC_API_KEY and ANTHROPIC_MODEL (see .env).

For each fixture it calls `analyze()`, then `tailor()` with no examples (retrieval is off, so runs
compare), and scores the draft. Calls are logged to an in-memory sink: this module never opens a
database session. Exit code: 0 all fixtures passed, 1 any failed, 2 not configured or a bad fixture.
"""

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.ai.client import AnthropicAIClient
from app.ai.prompts import PromptModule, posting_analysis, tailor_resume, tailor_resume_v2
from app.ai.sinks import InMemoryLogSink
from app.ai.types import AIClient, AIConfigurationError, AIError, LogSink
from app.core.config import get_settings
from app.services.generation import analyze, tailor
from evals.fixtures import FIXTURES_DIR, Fixture, FixtureError, load_fixtures
from evals.report import FixtureRun, format_table, results_file_name, to_result_json
from evals.scoring import score_error, score_fixture

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# The tailoring prompt to measure, by name. v1 is what the app runs, so it is the default. The
# analysis prompt stays v1 for every choice, so a difference between runs comes from tailoring.
TAILOR_PROMPTS: dict[str, PromptModule] = {"v1": tailor_resume, "v2": tailor_resume_v2}


def build_client(sink: LogSink) -> AIClient:
    """The real client. The key and model come from ANTHROPIC_API_KEY and ANTHROPIC_MODEL."""
    return AnthropicAIClient.from_settings(get_settings(), sink)


def run_fixture(
    client: AIClient,
    sink: InMemoryLogSink,
    fixture: Fixture,
    tailor_prompt: PromptModule = tailor_resume,
) -> FixtureRun:
    first_record = len(sink.records)
    try:
        analysis = analyze(client, posting_text=fixture.posting_text, application_id=None)
        keywords = analysis.output.keywords
        draft = tailor(
            client,
            base_resume=fixture.base_resume,
            posting_text=fixture.posting_text,
            keywords=keywords,
            application_id=None,
            prompt=tailor_prompt,
        )
        score = score_fixture(
            fixture.name,
            base_resume=fixture.base_resume,
            keywords=keywords,
            tailored=draft.output,
            forbidden_skills=fixture.forbidden_skills,
        )
    except AIError as exc:
        score = score_error(fixture.name, f"{type(exc).__name__}: {exc}")

    records = sink.records[first_record:]
    input_tokens = [r.input_tokens for r in records if r.input_tokens is not None]
    output_tokens = [r.output_tokens for r in records if r.output_tokens is not None]
    costs = [r.estimated_cost for r in records if r.estimated_cost is not None]
    return FixtureRun(
        score,
        input_tokens=sum(input_tokens) if input_tokens else None,
        output_tokens=sum(output_tokens) if output_tokens else None,
        cost=sum(costs, Decimal(0)) if costs else None,
    )


def main(
    *,
    make_client: Callable[[LogSink], AIClient] = build_client,
    fixtures_dir: Path = FIXTURES_DIR,
    results_dir: Path = RESULTS_DIR,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    prompts: str = "v1",
) -> int:
    tailor_prompt = TAILOR_PROMPTS.get(prompts)
    if tailor_prompt is None:
        choices = ", ".join(TAILOR_PROMPTS)
        print(f"Cannot run the eval: unknown --prompts {prompts!r} (use {choices})")
        return 2
    sink = InMemoryLogSink()
    try:
        client = make_client(sink)
        fixtures = load_fixtures(fixtures_dir)
    except (AIConfigurationError, FixtureError) as exc:
        print(f"Cannot run the eval: {exc}")
        return 2

    runs = [run_fixture(client, sink, fixture, tailor_prompt) for fixture in fixtures]

    model = sink.records[0].model
    analysis_version, tailor_version = posting_analysis.VERSION, tailor_prompt.VERSION
    versions = {"posting_analysis": analysis_version, "tailor_resume": tailor_version}
    print(f"Model: {model}")
    print(f"Prompts: posting_analysis {analysis_version}, tailor_resume {tailor_version}\n")
    print(format_table([run.score for run in runs]))

    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / results_file_name(analysis_version, tailor_version, model)
    data = to_result_json(runs, model=model, versions=versions, ran_at=now())
    path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"\nResults written to {path}")

    return 0 if all(run.score.passed for run in runs) else 1


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="evals.run", description="Run the prompt eval.")
    parser.add_argument(
        "--prompts",
        default="v1",
        help="tailoring prompt version to measure: v1 (what the app runs, the default) or v2",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main(prompts=parse_args(sys.argv[1:]).prompts))
