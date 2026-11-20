"""The eval around the scoring: fixtures, the printed table, the results file and the run loop.

The run loop gets a scripted fake client, so no test calls the model or opens a database.
"""

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import SecretStr

from app.ai.schemas import (
    Experience,
    PostingAnalysisOutput,
    Requirement,
    RequirementCategory,
    TailoredResume,
)
from app.ai.sinks import InMemoryLogSink
from app.ai.types import AIError, AIRefusalError, LogSink
from app.core.config import Settings
from app.services.coverage import keyword_coverage
from app.services.rendering import find_headings
from evals import run
from evals.fixtures import FIXTURES_DIR, Fixture, FixtureError, load_fixtures
from evals.report import FixtureRun, format_table, results_file_name, to_result_json
from evals.scoring import FixtureScore, score_error, score_fixture
from tests.fakes import FakeAIClient

BASE = """# Jordan Avery

## Summary
Backend engineer.

## Experience
### Software Engineer — Acme Corp (2019 — 2024)
- Built REST services in Python and PostgreSQL

## Skills
Python, PostgreSQL, Docker
"""
POSTING = "We need Python, PostgreSQL, REST APIs and Docker."
KEYWORDS = ["python", "postgresql", "rest apis", "docker"]
ANALYSIS = PostingAnalysisOutput(
    requirements=[Requirement(text="Python", category=RequirementCategory.MUST_HAVE)],
    keywords=KEYWORDS,
)


def tailored(employer: str = "Acme Corp") -> TailoredResume:
    """Passes with the default employer (REST APIs lifts coverage from 3/4 to 4/4); fails with
    any other."""
    return TailoredResume(
        summary="Backend engineer.",
        experiences=[
            Experience(
                employer=employer,
                title="Software Engineer",
                dates="2019 — 2024",
                bullets=["Built REST APIs in Python and PostgreSQL"],
            )
        ],
        skills=["Python", "PostgreSQL", "Docker"],
    )


class ScriptedClient:
    """Answers the analysis call with ANALYSIS and each tailoring call with the next outcome,
    in order (fixtures run in name order). Every call is logged through the sink."""

    model = "fake-model"

    def __init__(self, sink: LogSink, outcomes: list[TailoredResume | type[AIError]]) -> None:
        self.sink = sink
        self.outcomes = list(outcomes)
        self.calls = 0

    def generate(self, *, output_model, **kwargs):  # noqa: ANN001, ANN003, ANN201
        self.calls += 1
        if output_model is PostingAnalysisOutput:
            return FakeAIClient(self.sink, output=ANALYSIS).generate(
                output_model=output_model, **kwargs
            )
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, TailoredResume):
            return FakeAIClient(self.sink, output=outcome).generate(
                output_model=output_model, **kwargs
            )
        return FakeAIClient(self.sink, error=outcome).generate(output_model=output_model, **kwargs)


def make_fixture(root: Path, name: str, *, forbidden: list[str] | None = None) -> None:
    folder = root / name
    folder.mkdir(parents=True)
    (folder / "posting.txt").write_text(POSTING)
    (folder / "resume.md").write_text(BASE)
    (folder / "expect.json").write_text(json.dumps({"forbidden_skills": forbidden or []}))


def run_eval(
    tmp_path: Path, outcomes: list[TailoredResume | type[AIError]], names: list[str] | None = None
) -> tuple[int, ScriptedClient]:
    fixtures_dir = tmp_path / "fixtures"
    for name in names or ["a", "b"]:
        make_fixture(fixtures_dir, name)
    holder: list[ScriptedClient] = []

    def make_client(sink: LogSink) -> ScriptedClient:
        holder.append(ScriptedClient(sink, outcomes))
        return holder[0]

    code = run.main(
        make_client=make_client,
        fixtures_dir=fixtures_dir,
        results_dir=tmp_path / "results",
        now=lambda: datetime(2026, 11, 19, 15, 0, tzinfo=UTC),
    )
    return code, holder[0]


# --- fixtures ------------------------------------------------------------------------------------


def test_every_shipped_fixture_loads() -> None:
    fixtures = load_fixtures()

    assert all(isinstance(f, Fixture) for f in fixtures)
    assert all(f.posting_text.strip() and f.base_resume.strip() for f in fixtures)


def test_there_are_three_to_five_fixtures_and_at_least_one_trap() -> None:
    fixtures = load_fixtures()

    assert 3 <= len(fixtures) <= 5
    assert any(f.forbidden_skills for f in fixtures)


def test_every_forbidden_skill_is_demanded_by_its_posting_and_missing_from_its_resume() -> None:
    for fixture in load_fixtures():
        if not fixture.forbidden_skills:
            continue
        in_posting = keyword_coverage(fixture.forbidden_skills, fixture.posting_text)
        in_resume = keyword_coverage(fixture.forbidden_skills, fixture.base_resume)
        assert in_posting.missing == [], fixture.name
        assert in_resume.covered == [], fixture.name


def test_every_shipped_resume_has_summary_experience_and_skills_sections() -> None:
    for fixture in load_fixtures():
        names = {name for _, _, name in find_headings(fixture.base_resume.split("\n"))}
        assert {"summary", "experience", "skills"} <= names, fixture.name


def test_fixtures_load_in_name_order(tmp_path: Path) -> None:
    for name in ["zeta", "alpha", "mid"]:
        make_fixture(tmp_path, name)

    assert [f.name for f in load_fixtures(tmp_path)] == ["alpha", "mid", "zeta"]


def test_a_missing_fixture_file_names_the_file(tmp_path: Path) -> None:
    make_fixture(tmp_path, "broken")
    (tmp_path / "broken" / "resume.md").unlink()

    with pytest.raises(FixtureError, match=r"broken.*resume\.md"):
        load_fixtures(tmp_path)


def test_bad_expect_json_names_the_fixture(tmp_path: Path) -> None:
    make_fixture(tmp_path, "broken")
    (tmp_path / "broken" / "expect.json").write_text("{not json")

    with pytest.raises(FixtureError, match=r"broken.*expect\.json"):
        load_fixtures(tmp_path)


def test_expect_json_needs_a_forbidden_skills_list(tmp_path: Path) -> None:
    make_fixture(tmp_path, "broken")
    (tmp_path / "broken" / "expect.json").write_text("{}")

    with pytest.raises(FixtureError, match="forbidden_skills"):
        load_fixtures(tmp_path)


def test_a_forbidden_skill_that_the_base_resume_has_is_rejected(tmp_path: Path) -> None:
    make_fixture(tmp_path, "broken", forbidden=["docker"])

    with pytest.raises(FixtureError, match=r"broken.*docker"):
        load_fixtures(tmp_path)


def test_a_folder_with_no_fixtures_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(FixtureError, match="no fixtures"):
        load_fixtures(tmp_path)


def test_the_fixtures_folder_is_backend_evals_fixtures() -> None:
    assert FIXTURES_DIR == Path(run.__file__).parent / "fixtures"


# --- the table and the results file --------------------------------------------------------------


def passing_score() -> FixtureScore:
    return score_fixture(
        "backend-python",
        base_resume=BASE,
        keywords=KEYWORDS,
        tailored=tailored(),
        forbidden_skills=[],
    )


def failing_score() -> FixtureScore:
    return score_fixture(
        "data-trap",
        base_resume=BASE,
        keywords=KEYWORDS,
        tailored=tailored(employer="Globex"),
        forbidden_skills=[],
    )


def test_the_table_lists_fixture_flags_coverage_and_result() -> None:
    table = format_table([passing_score(), failing_score()])
    lines = table.splitlines()

    assert all(word in lines[0].lower() for word in ("fixture", "flags", "coverage", "result"))
    ok = next(line for line in lines if "backend-python" in line)
    bad = next(line for line in lines if "data-trap" in line)
    assert "75% → 100%" in ok and "PASS" in ok
    assert "FAIL" in bad
    assert "2 flags" not in ok


def test_the_table_says_why_a_fixture_failed() -> None:
    assert 'Employer "Globex"' in format_table([failing_score()])


def test_the_table_ends_with_the_pass_count() -> None:
    assert format_table([passing_score(), failing_score()]).splitlines()[-1] == "1 of 2 passed"


def test_a_failed_call_shows_as_a_failed_row_with_its_error() -> None:
    table = format_table([score_error("broken", "refusal: the model refused the request")])

    assert "broken" in table and "FAIL" in table
    assert "refusal: the model refused the request" in table


def test_the_results_file_name_has_both_prompt_versions_and_the_model() -> None:
    assert (
        results_file_name("v1", "v2", "claude-sonnet-5-5")
        == "posting_analysis-v1_tailor_resume-v2_claude-sonnet-5-5.json"
    )


def test_the_results_json_holds_every_flag_and_the_coverage_per_fixture() -> None:
    runs = [FixtureRun(failing_score(), input_tokens=100, output_tokens=40, cost=None)]

    data = to_result_json(
        runs,
        model="claude-sonnet-5-5",
        versions={"posting_analysis": "v1", "tailor_resume": "v1"},
        ran_at=datetime(2026, 11, 19, 15, 0, tzinfo=UTC),
    )

    assert data["model"] == "claude-sonnet-5-5"
    assert data["prompt_versions"] == {"posting_analysis": "v1", "tailor_resume": "v1"}
    assert data["ran_at"] == "2026-11-19T15:00:00+00:00"
    assert (data["passed"], data["total"]) == (0, 1)
    entry = data["fixtures"][0]
    assert entry["name"] == "data-trap"
    assert entry["passed"] is False
    assert entry["flags"][0] == {
        "field": "employer",
        "value": "Globex",
        "message": 'Employer "Globex"',
    }
    assert entry["coverage"] == {"base": 0.75, "draft": 1.0}
    assert entry["tokens"] == {"input": 100, "output": 40}
    assert entry["failures"]
    assert json.dumps(data)  # plain JSON types, so it can be written as is


def test_the_results_json_does_not_hold_the_drafts() -> None:
    data = to_result_json(
        [FixtureRun(passing_score(), None, None, None)],
        model="m",
        versions={"posting_analysis": "v1", "tailor_resume": "v1"},
        ran_at=datetime(2026, 11, 19, tzinfo=UTC),
    )

    assert "Built REST APIs" not in json.dumps(data)


# --- the run -------------------------------------------------------------------------------------


def test_all_fixtures_passing_exits_0_and_writes_the_results_file(tmp_path: Path) -> None:
    code, _ = run_eval(tmp_path, [tailored(), tailored()])

    assert code == 0
    written = tmp_path / "results" / "posting_analysis-v1_tailor_resume-v1_fake-model.json"
    data = json.loads(written.read_text())
    assert (data["passed"], data["total"]) == (2, 2)
    assert [f["name"] for f in data["fixtures"]] == ["a", "b"]


def test_any_failed_fixture_exits_1(tmp_path: Path) -> None:
    code, _ = run_eval(tmp_path, [tailored(), tailored(employer="Globex")])

    assert code == 1
    results = next((tmp_path / "results").glob("*.json"))
    assert [f["passed"] for f in json.loads(results.read_text())["fixtures"]] == [True, False]


def test_a_failed_call_fails_only_that_fixture_and_the_run_continues(tmp_path: Path) -> None:
    code, client = run_eval(tmp_path, [AIRefusalError, tailored()])

    assert code == 1
    assert client.calls == 4  # both fixtures got an analysis call and a tailoring call
    results = next((tmp_path / "results").glob("*.json"))
    first, second = json.loads(results.read_text())["fixtures"]
    assert not first["passed"] and "refus" in first["failures"][0].lower()
    assert second["passed"]


def test_the_run_prints_the_table(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_eval(tmp_path, [tailored(), tailored()])

    out = capsys.readouterr().out
    assert "fixture" in out and "2 of 2 passed" in out


def test_the_run_calls_analyze_then_tailor_once_per_fixture_with_no_examples(
    tmp_path: Path,
) -> None:
    _, client = run_eval(tmp_path, [tailored()], names=["only"])

    assert client.calls == 2


def test_tailoring_gets_the_keywords_from_the_analysis_and_an_empty_examples_section(
    tmp_path: Path,
) -> None:
    sinks: list[InMemoryLogSink] = []
    fixtures_dir = tmp_path / "fixtures"
    make_fixture(fixtures_dir, "only")

    def make_client(sink: InMemoryLogSink) -> ScriptedClient:
        sinks.append(sink)
        return ScriptedClient(sink, [tailored()])

    run.main(make_client=make_client, fixtures_dir=fixtures_dir, results_dir=tmp_path / "r")

    request = sinks[0].records[1].request_json["messages"][0]["content"]
    assert "- rest apis" in request
    assert "<examples>\n</examples>" in request
    assert sinks[0].records[1].retrieved_example_ids == []


def test_the_run_uses_the_in_memory_sink(tmp_path: Path) -> None:
    sinks: list[LogSink] = []
    fixtures_dir = tmp_path / "fixtures"
    make_fixture(fixtures_dir, "only")

    def make_client(sink: LogSink) -> ScriptedClient:
        sinks.append(sink)
        return ScriptedClient(sink, [tailored()])

    run.main(make_client=make_client, fixtures_dir=fixtures_dir, results_dir=tmp_path / "r")

    assert isinstance(sinks[0], InMemoryLogSink)
    assert len(sinks[0].records) == 2


def test_the_run_never_opens_a_database_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("the eval opened a database connection")

    monkeypatch.setattr("sqlalchemy.create_engine", refuse)
    monkeypatch.setattr("sqlalchemy.orm.Session.__init__", refuse)

    code, _ = run_eval(tmp_path, [tailored(), tailored()])

    assert code == 0


def test_importing_the_eval_does_not_import_the_database_module() -> None:
    script = "import sys, evals.run; sys.exit(int('app.core.db' in sys.modules))"
    backend = Path(run.__file__).resolve().parent.parent

    result = subprocess.run([sys.executable, "-c", script], cwd=backend, check=False)

    assert result.returncode == 0


def test_a_missing_key_exits_2_without_calling_anything(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Explicit values, because Settings also reads the shell's environment variables.
    settings = Settings(_env_file=None, anthropic_api_key=SecretStr(""), anthropic_model="")
    monkeypatch.setattr(run, "get_settings", lambda: settings)

    code = run.main(results_dir=tmp_path / "results")

    assert code == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().out
    assert not (tmp_path / "results").exists()


def test_a_missing_model_exits_2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = Settings(_env_file=None, anthropic_api_key=SecretStr("sk-test"), anthropic_model="")
    monkeypatch.setattr(run, "get_settings", lambda: settings)

    assert run.main(results_dir=tmp_path / "results") == 2


def test_the_key_never_appears_in_the_output_or_the_results(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_eval(tmp_path, [tailored(), tailored()])

    everything = capsys.readouterr().out + "".join(
        p.read_text() for p in (tmp_path / "results").glob("*.json")
    )
    assert "sk-ant" not in everything
