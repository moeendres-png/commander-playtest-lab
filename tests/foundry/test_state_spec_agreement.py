"""Pin where the two state specifications must agree, and record where they diverge.

Two specifications describe the workstream state file:

* ``tools/foundry/state.py`` -- the **enforced** one. ``safe_push.py`` calls
  ``state_mod.validate`` and raises ``_PushReject`` on any error, so a file that
  fails it cannot leave the machine through the canonical push path.
* ``.foundry/WORKSTREAM_STATE.schema.json`` -- JSON Schema, read by no
  production code path.

Two specifications is worse than one. **Choosing between them is a durable-state
contract decision that belongs to the Coordinator and this file does not make
it.** What it does instead is make the situation *monitored* rather than
unmonitored, which is the part that does not require that decision:

* every part of the overlap that must agree is asserted **in both directions**,
  so editing one vocabulary without mirroring it in the other fails here;
* every known divergence is listed with its reason and asserted to still hold,
  so a divergence cannot quietly vanish from the record and the Coordinator's
  decision list cannot rot;
* the premise this file rests on -- that ``safe_push`` really does enforce
  ``state.py`` -- is itself asserted, so the rationale cannot silently become
  false.

``state.py``'s module docstring claims it "mirrors" the schema. Where that claim
is checkable, this file checks it. Where it is not -- the cases listed under
``DIVERGENCE_CHECKS`` -- it is recorded rather than silently assumed.

Context and the open contract question:
``docs/test_signal_integrity_20260929/FOUNDRY_STATE_CONFORMANCE.md``.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "tools"))

from foundry import state as state_mod  # noqa: E402

SCHEMA_PATH = REPO_ROOT / ".foundry" / "WORKSTREAM_STATE.schema.json"
SAFE_PUSH_PATH = REPO_ROOT / "tools" / "foundry" / "safe_push.py"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# state.py attribute -> schema property. Both sides must hold the same members.
SHARED_ENUMS = {
    "STATUS_VOCABULARY": "status",
    "FAILURE_CLASSES": "failure_class",
    "REASONING_TIERS": "current_reasoning_tier",
}


# --- the premise: state.py is enforced, the schema is not ------------------- #


def test_safe_push_really_does_enforce_state_py() -> None:
    """If this fails, the whole rationale for mirroring state.py here is void."""
    source = SAFE_PUSH_PATH.read_text(encoding="utf-8")
    assert "state_mod.validate" in source, (
        "safe_push.py no longer calls state_mod.validate, so state.py is no longer the "
        "enforced specification. Re-derive which validator the push path actually uses "
        "before trusting tests/foundry/test_foundry_state_conformance.py either."
    )
    assert "invalid state:" in source, (
        "safe_push.py no longer rejects the push on state validation errors; the claim that a "
        "failing state file cannot push through the canonical gate needs re-checking."
    )


def _string_literals_outside_docstrings(path: Path) -> list[str]:
    """String literals in a module, excluding docstrings.

    Docstrings are excluded deliberately: ``state.py`` names the schema file in
    its module docstring to say it mirrors it. That is a claim about the schema,
    not a read of it, and counting it as a reader would invert the finding.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            found = ast.get_docstring(node, clean=False)
            if found is not None:
                docstrings.add(found)
    literals: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value not in docstrings
        ):
            literals.append(node.value)
    return literals


def test_schema_is_read_by_no_production_code_path() -> None:
    """Pins the *unenforced* status of the schema.

    If this fails, something started reading the schema at runtime. That is not
    necessarily wrong -- it may be the contract question being answered -- but it
    means the two-specification situation has changed and this file plus
    FOUNDRY_STATE_CONFORMANCE.md must be revisited rather than left describing a
    state of affairs that no longer holds.
    """
    needle = "WORKSTREAM_STATE.schema.json"
    readers: list[str] = []
    for base in ("src", "tools"):
        for path in (REPO_ROOT / base).rglob("*.py"):
            rel = path.relative_to(REPO_ROOT).as_posix()
            if "/tests/" in rel or path.name.startswith("test_"):
                continue
            if any(needle in lit for lit in _string_literals_outside_docstrings(path)):
                readers.append(rel)
    assert not readers, (
        f"the schema now has production reader(s): {readers}. The contract question between "
        "state.py and the schema is no longer purely hypothetical; revisit this file and "
        "docs/test_signal_integrity_20260929/FOUNDRY_STATE_CONFORMANCE.md."
    )


# --- the overlap that must agree -------------------------------------------- #


def test_required_field_sets_agree_in_both_directions() -> None:
    schema = _schema()
    py_required = set(state_mod.REQUIRED_V2)
    json_required = set(schema["required"])
    assert py_required == json_required, (
        "state.py REQUIRED_V2 and the schema's required list have diverged.\n"
        f"  only in state.py: {sorted(py_required - json_required)}\n"
        f"  only in schema:   {sorted(json_required - py_required)}\n"
        "A field required by one and optional in the other means a file can be valid "
        "under the enforced validator and invalid under the schema, or vice versa."
    )


@pytest.mark.parametrize("attr,prop", sorted(SHARED_ENUMS.items()))
def test_shared_enum_vocabularies_agree(attr: str, prop: str) -> None:
    schema = _schema()
    py_values = {str(v) for v in getattr(state_mod, attr)}
    json_prop = schema["properties"].get(prop)
    assert json_prop is not None, f"{prop} is no longer a schema property; update SHARED_ENUMS"
    assert "enum" in json_prop, f"{prop} lost its enum in the schema; update SHARED_ENUMS"
    json_values = {str(v) for v in json_prop["enum"] if v is not None}
    assert py_values == json_values, (
        f"{attr} and the schema's {prop} enum have diverged.\n"
        f"  only in state.py: {sorted(py_values - json_values)}\n"
        f"  only in schema:   {sorted(json_values - py_values)}"
    )


def test_failure_classes_also_govern_root_cause_class() -> None:
    """One vocabulary, two properties -- both must track it."""
    schema = _schema()
    json_values = {str(v) for v in schema["properties"]["root_cause_class"]["enum"]}
    py_values = {str(v) for v in state_mod.FAILURE_CLASSES}
    assert py_values == json_values, (
        "state.py FAILURE_CLASSES and the schema's root_cause_class enum have diverged.\n"
        f"  only in state.py: {sorted(py_values - json_values)}\n"
        f"  only in schema:   {sorted(json_values - py_values)}\n"
        "These are one vocabulary across two properties; a value admitted by one and refused by "
        "the other means the same classification is valid under the enforced validator and "
        "invalid under the schema."
    )


@pytest.mark.parametrize("field", sorted(state_mod.LIST_FIELDS))
def test_list_fields_are_arrays_in_both(field: str) -> None:
    schema = _schema()
    prop = schema["properties"].get(field)
    assert prop is not None, f"{field} is in state.py LIST_FIELDS but absent from the schema"
    assert prop.get("type") == "array", (
        f"{field} must be a list per state.py LIST_FIELDS but is {prop.get('type')!r} in the "
        "schema, so the same file could be valid under one and invalid under the other"
    )


# --- the divergences, recorded and kept honest ------------------------------ #

DIVERGENCE_CHECKS: dict[str, object] = {
    "additionalProperties": lambda s: s.get("additionalProperties") is False,
    "schema_version_pattern": lambda s: (
        "pattern" in s["properties"]["schema_version"]
        and "enum" not in s["properties"]["schema_version"]
    ),
    "schema_only_executor_enums": lambda s: (
        "enum" in s["properties"]["execution_profile"]
        and "enum" in s["properties"]["native_variant"]
    ),
    "no_schema_model_for_v1": lambda s: (
        "current_head" not in s["properties"] and "current_head" in state_mod.REQUIRED_V1
    ),
}

DIVERGENCE_REASONS = {
    "additionalProperties": (
        "the schema sets additionalProperties: false over a 43-field whitelist, so it rejects "
        "any extra key; state.py accepts extras. The three tracked .json state files happen to "
        "stay inside the whitelist, but every hand-written .yaml one needs keys the schema "
        "forbids, so enforcing the schema would delete recorded research."
    ),
    "schema_version_pattern": (
        "the schema accepts any '<digits>.<digits>' by pattern; state.py accepts only "
        "SUPPORTED_VERSIONS, so a version such as 1.5 validates against one and not the other."
    ),
    "schema_only_executor_enums": (
        "the schema constrains execution_profile and native_variant by enum; state.py carries no "
        "vocabulary for either, so the same value can be schema-invalid and state.py-valid."
    ),
    "no_schema_model_for_v1": (
        "state.py models schema 1.0 separately, requiring current_head; the schema has no 1.0 "
        "model at all, so no 1.0 file can validate against it."
    ),
}


def test_every_recorded_divergence_is_still_real() -> None:
    """Rot-proof in both directions, like the exemption table next door.

    A divergence that stops being true must be removed from the record rather
    than left asserted; a divergence discovered but not recorded fails the key
    check below.
    """
    schema = _schema()
    for name, check in DIVERGENCE_CHECKS.items():
        assert check(schema), (
            f"recorded divergence {name!r} no longer holds. Either the specifications have been "
            "reconciled -- in which case delete it from DIVERGENCE_CHECKS, DIVERGENCE_REASONS and "
            "FOUNDRY_STATE_CONFORMANCE.md -- or the check itself is wrong."
        )


def test_divergence_record_and_checks_cover_the_same_set() -> None:
    assert set(DIVERGENCE_CHECKS) == set(DIVERGENCE_REASONS), (
        "DIVERGENCE_CHECKS and DIVERGENCE_REASONS disagree:\n"
        f"  checks without a reason: {sorted(set(DIVERGENCE_CHECKS) - set(DIVERGENCE_REASONS))}\n"
        f"  reasons without a check: {sorted(set(DIVERGENCE_REASONS) - set(DIVERGENCE_CHECKS))}"
    )
    for name, reason in DIVERGENCE_REASONS.items():
        assert len(reason.strip()) > 60, f"{name}: divergence reason is not substantive"
