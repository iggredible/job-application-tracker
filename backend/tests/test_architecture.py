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
