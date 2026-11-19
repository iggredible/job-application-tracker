"""Rules that must never be broken, checked against the source.

`applications.stage` changes only through ApplicationService.change_stage(). Two documented
exceptions: creating an application (the column default applies) and the seed script
(feature 13), which lives outside `app/`.
"""

import ast
import inspect
import re
from pathlib import Path

from app.repositories.timeline import TimelineRepository
from app.schemas.application import ApplicationCreate, ApplicationUpdate

APP_DIR = Path(__file__).resolve().parent.parent / "app"
SETTER = "update_stage"


def _sources() -> list[tuple[Path, ast.Module]]:
    return [(p, ast.parse(p.read_text())) for p in sorted(APP_DIR.rglob("*.py"))]


def _enclosing_functions(tree: ast.Module) -> dict[int, str]:
    """Map each node id to the name of the function that contains it."""
    owner: dict[int, str] = {}
    for function in ast.walk(tree):
        if isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
            for node in ast.walk(function):
                owner[id(node)] = function.name
    return owner


WRITING_CALLS = {"Application", "values", "update", "insert", "setattr"}


def _call_name(node: ast.Call) -> str | None:
    return getattr(node.func, "id", None) or getattr(node.func, "attr", None)


# Raw SQL that writes the stage column of the applications table.
RAW_SQL_WRITE = re.compile(
    r"\b(update\s+applications|insert\s+into\s+applications)\b.*\bstage\b",
    re.IGNORECASE | re.DOTALL,
)
VARIABLE_SETATTR = "setattr(..., <variable>, ...)"
# ApplicationService.update() copies request fields with setattr(application, field, value).
# The scan cannot see the field names, so this is safe only because no schema carries `stage`
# (see test_the_unchecked_setattr_is_safe_because_no_schema_accepts_a_stage).
ALLOWED_VARIABLE_SETATTR = ("services/applications.py", "update")


def _writes_to_stage(tree: ast.Module) -> list[tuple[ast.AST, str]]:
    """Every place that could write a stage: an attribute assignment (`x.stage = ...`), a
    `stage=` keyword on a call that writes (Application(...), .values(...), .update(...),
    .insert(...)), setattr(x, "stage", ...), setattr with a variable field name, a dict with
    a "stage" key (`.values({"stage": ...})`, bulk updates) and raw SQL that sets the column.
    Reading calls such as list(stage=...) pass."""
    found: list[tuple[ast.AST, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            if any(isinstance(k, ast.Constant) and k.value == "stage" for k in node.keys):
                found.append((node, "dict with a 'stage' key"))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if RAW_SQL_WRITE.search(node.value):
                found.append((node, "raw SQL writes stage"))
        elif isinstance(node, ast.Assign | ast.AugAssign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and target.attr == "stage":
                    found.append((node, "assigns .stage"))
        elif isinstance(node, ast.Call):
            name = _call_name(node)
            if name in WRITING_CALLS - {"setattr"}:
                for keyword in node.keywords:
                    if keyword.arg == "stage":
                        found.append((node, f"{name}(stage=...)"))
            if name == "setattr" and len(node.args) >= 2:
                field = node.args[1]
                if not isinstance(field, ast.Constant):
                    found.append((node, VARIABLE_SETATTR))
                elif field.value == "stage":
                    found.append((node, "setattr(..., 'stage', ...)"))
    return found


def test_only_the_repository_setter_writes_application_stage() -> None:
    offenders = []
    for path, tree in _sources():
        owner = _enclosing_functions(tree)
        relative = path.relative_to(APP_DIR).as_posix()
        for node, how in _writes_to_stage(tree):
            function = owner.get(id(node))
            is_setter = relative == "repositories/applications.py" and function == SETTER
            is_checked_setattr = how == VARIABLE_SETATTR and (relative, function) == (
                ALLOWED_VARIABLE_SETATTR
            )
            if not (is_setter or is_checked_setattr):
                offenders.append(f"{relative}:{node.lineno} {how}")

    assert offenders == []


def test_only_change_stage_calls_the_repository_setter() -> None:
    callers = []
    for path, tree in _sources():
        owner = _enclosing_functions(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == SETTER:
                callers.append((path.relative_to(APP_DIR).as_posix(), owner.get(id(node))))

    assert callers == [("services/applications.py", "change_stage")]


def test_the_stage_endpoint_goes_through_change_stage() -> None:
    source = (APP_DIR / "api" / "applications.py").read_text()

    assert ".change_stage(" in source
    assert SETTER not in source


def test_the_architecture_scan_would_catch_a_violation() -> None:
    tree = ast.parse(
        "application.stage = Stage.OFFER\n"
        "Application(stage='offer')\n"
        "update(Application).values(stage='offer')\n"
        "setattr(application, 'stage', 'offer')\n"
        "update(Application).values({'stage': 'offer'})\n"
        "session.execute(update(Application), [{'id': 1, 'stage': 'offer'}])\n"
        "session.execute(text(\"UPDATE applications SET stage = 'offer' WHERE id = 1\"))\n"
        "session.execute(text('insert into applications (company, stage) values (1, 2)'))\n"
        "setattr(application, field, value)\n"
        # None of these write a stage.
        "service.list(stage='offer')\n"
        "counts = {s: 0 for s in Stage}\n"
        "session.execute(text('SELECT stage FROM applications'))\n"
        "session.execute(text('UPDATE applications SET role = 1'))\n"
    )

    assert len(_writes_to_stage(tree)) == 9


def test_the_unchecked_setattr_is_safe_because_no_schema_accepts_a_stage() -> None:
    # ApplicationService.update() copies request fields with setattr(application, field, ...).
    # The scan cannot see the field names, so it relies on the schemas never carrying `stage`.
    assert "stage" not in ApplicationCreate.model_fields
    assert "stage" not in ApplicationUpdate.model_fields


def test_timeline_repository_has_no_update_or_delete() -> None:
    methods = {name for name, _ in inspect.getmembers(TimelineRepository, inspect.isfunction)}

    assert not {m for m in methods if m.startswith(("update", "delete", "remove", "set"))}
    assert {"add", "list_for_application"} <= methods


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_the_resume_slice_follows_the_layering_rules() -> None:
    api = _imports(APP_DIR / "api" / "resume.py")
    service = _imports(APP_DIR / "services" / "resumes.py")
    repository = _imports(APP_DIR / "repositories" / "resumes.py")

    # api/ holds no queries and no tables. Like the applications router, it only passes the
    # session to the repository when it wires up the service.
    assert not {m for m in api if m.startswith("app.models") or m == "sqlalchemy"}
    # services/ import no FastAPI and write no SQL.
    assert not {m for m in service if m.startswith(("fastapi", "sqlalchemy"))}
    # repositories/ make no HTTP or business decisions.
    assert not {m for m in repository if m.startswith(("fastapi", "app.services", "app.api"))}


def test_the_resume_schema_cannot_carry_a_status() -> None:
    from app.schemas.resume import ResumeWrite

    assert set(ResumeWrite.model_fields) == {"content_markdown"}


# --- AI layer (feature 5) -----------------------------------------------------------------------


def test_the_ai_layer_follows_the_layering_rules() -> None:
    ai_files = sorted((APP_DIR / "ai").rglob("*.py"))
    assert ai_files, "app/ai/ is missing"

    for path in ai_files:
        imports = _imports(path)
        # ai/ is not HTTP, and it touches SQLAlchemy only in the database sink.
        assert not {m for m in imports if m.startswith(("fastapi", "app.api"))}, path
        uses_sqlalchemy = any(m == "sqlalchemy" or m.startswith("sqlalchemy.") for m in imports)
        assert path.name == "sinks.py" or not uses_sqlalchemy, path


def test_only_the_ai_package_imports_the_anthropic_sdk() -> None:
    offenders = [
        path.relative_to(APP_DIR).as_posix()
        for path in sorted(APP_DIR.rglob("*.py"))
        if any(m == "anthropic" or m.startswith("anthropic.") for m in _imports(path))
        and path.relative_to(APP_DIR).parts[0] != "ai"
    ]

    assert offenders == []


def test_services_and_api_do_not_depend_on_the_concrete_ai_client() -> None:
    for layer in ("services", "api"):
        for path in sorted((APP_DIR / layer).rglob("*.py")):
            concrete = {m for m in _imports(path) if m in {"app.ai.client", "app.ai.sinks"}}
            allowed = path.relative_to(APP_DIR).as_posix() == "api/ai.py"  # the provider wires it
            assert allowed or not concrete, path


def test_the_ai_call_repository_has_no_update_or_delete() -> None:
    from app.repositories.ai_calls import AICallRepository

    methods = {name for name, _ in inspect.getmembers(AICallRepository, inspect.isfunction)}

    assert not {m for m in methods if m.startswith(("update", "delete", "remove", "set"))}
    assert {"add", "get"} <= methods


def test_no_code_sets_a_temperature() -> None:
    offenders = []
    for path, tree in _sources():
        relative = path.relative_to(APP_DIR)
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "temperature":
                offenders.append(f"{relative}:{node.value.lineno} keyword")
            if isinstance(node, ast.Dict) and any(
                isinstance(k, ast.Constant) and k.value == "temperature" for k in node.keys
            ):
                offenders.append(f"{relative}:{node.lineno} dict key")

    assert offenders == []


MODEL_ID = re.compile(r"claude-(sonnet|opus|haiku|fable)|sk-ant")


def test_no_model_name_or_key_is_hard_coded_outside_the_price_table() -> None:
    offenders = []
    for path, tree in _sources():
        relative = path.relative_to(APP_DIR).as_posix()
        if relative == "core/config.py":  # the price table is keyed by model
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if MODEL_ID.search(node.value):
                    offenders.append(f"{relative}:{node.lineno}")

    assert offenders == []


# --- Posting analysis (feature 6) ---------------------------------------------------------------


def test_the_analysis_slice_follows_the_layering_rules() -> None:
    api = _imports(APP_DIR / "api" / "analysis.py")
    services = [
        _imports(APP_DIR / "services" / name)
        for name in ("analysis.py", "generation.py", "review.py")
    ]
    repositories = [
        _imports(APP_DIR / "repositories" / name) for name in ("posting_analyses.py", "locks.py")
    ]

    # api/ holds no queries and no tables.
    assert not {m for m in api if m.startswith("app.models") or m == "sqlalchemy"}
    # services/ import no FastAPI and write no SQL.
    for imports in services:
        assert not {m for m in imports if m.startswith(("fastapi", "sqlalchemy"))}
    # repositories/ make no HTTP or business decisions.
    for imports in repositories:
        assert not {m for m in imports if m.startswith(("fastapi", "app.services", "app.api"))}


def test_analyze_touches_no_database() -> None:
    imports = _imports(APP_DIR / "services" / "generation.py")

    forbidden = {m for m in imports if m.startswith(("sqlalchemy", "app.repositories"))}
    forbidden |= {m for m in imports if m in {"app.core.db", "app.ai.sinks"}}
    assert forbidden == set()


def test_only_the_review_rules_assign_a_status() -> None:
    allowed = {"services/review.py", "services/resumes.py"}  # resumes: the base resume is approved
    offenders = []
    for path, tree in _sources():
        relative = path.relative_to(APP_DIR).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign | ast.AugAssign | ast.AnnAssign):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    is_status = isinstance(target, ast.Attribute) and target.attr == "status"
                    if is_status and relative not in allowed:
                        offenders.append(f"{relative}:{node.lineno}")

    assert offenders == []


def test_an_analysis_is_never_created_with_a_status() -> None:
    # Every analysis is saved as a draft (the column default). Only approve or reject changes it.
    offenders = []
    for path, tree in _sources():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _call_name(node) == "PostingAnalysis":
                if any(keyword.arg == "status" for keyword in node.keywords):
                    offenders.append(f"{path.relative_to(APP_DIR)}:{node.lineno}")

    assert offenders == []


def test_the_analysis_repository_has_no_delete() -> None:
    from app.repositories.posting_analyses import PostingAnalysisRepository

    methods = {n for n, _ in inspect.getmembers(PostingAnalysisRepository, inspect.isfunction)}

    assert not {m for m in methods if m.startswith(("delete", "remove"))}
    assert {"add", "get", "list_for_application"} <= methods


# --- Tailored resume review (feature 10) --------------------------------------------------------


def test_the_resume_review_slice_follows_the_layering_rules() -> None:
    api = _imports(APP_DIR / "api" / "resumes.py")
    service = _imports(APP_DIR / "services" / "resume_review.py")
    repository = _imports(APP_DIR / "repositories" / "resumes.py")

    # api/ holds no queries and no tables.
    assert not {m for m in api if m.startswith("app.models") or m == "sqlalchemy"}
    # services/ import no FastAPI and write no SQL.
    assert not {m for m in service if m.startswith(("fastapi", "sqlalchemy"))}
    # repositories/ make no HTTP or business decisions.
    assert not {m for m in repository if m.startswith(("fastapi", "app.services", "app.api"))}


def test_no_code_assigns_the_generated_text_after_creation() -> None:
    # A resume is created with draft_markdown=...; nothing assigns the attribute afterwards.
    # (The database trigger is the second line of defence.)
    offenders = []
    for path, tree in _sources():
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign | ast.AugAssign | ast.AnnAssign):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Attribute) and target.attr == "draft_markdown":
                        offenders.append(f"{path.relative_to(APP_DIR)}:{node.lineno}")

    assert offenders == []


def test_the_outcome_and_the_edit_ratio_are_never_stored() -> None:
    from app.models import Resume

    columns = set(Resume.__table__.columns.keys())

    assert not columns & {"outcome", "edit_ratio", "edited", "displayed", "superseded"}
