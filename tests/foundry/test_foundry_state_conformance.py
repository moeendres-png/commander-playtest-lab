"""Conformance guard for tracked ``.foundry`` workstream state files.

**Authority: ``tools/foundry/state.py``.**

That is not a style preference. ``tools/foundry/safe_push.py`` runs

    if str(data.get("schema_version", "")) != "2.0":
        raise _PushReject("state schema 2.0 required (migrate first)")
    errors = state_mod.validate(data)
    if errors:
        raise _PushReject(f"invalid state: {errors[0]}")

so a state file that fails ``state.py`` **blocks the canonical push path**. A
state file in that condition is not a cosmetic problem; it is a workstream that
cannot push through the project's own gate. This test mirrors the validator the
project already enforces rather than inventing a second specification.

``.foundry/WORKSTREAM_STATE.schema.json`` is deliberately **not** used here. It
sets ``additionalProperties: false`` over a 43-field whitelist, so no real state
file — which necessarily carries the evidence trail the audit depends on — can
satisfy it without deleting that research. Enforcing it would discard recorded
work. Whether to narrow that schema, or retire it in favour of ``state.py``, is
a durable-state contract decision for the Coordinator; this test does not
pre-empt it, and the divergence is recorded in
``docs/test_signal_integrity_20260929/FOUNDRY_STATE_CONFORMANCE.md``.

The exemption table is rot-proof in both directions:

* a state file that is neither conformant nor registered fails, so a new
  non-conformant state file cannot be committed silently;
* a registered file that starts validating fails too, so an exemption cannot
  outlive the condition that justified it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "tools"))

from foundry import state as state_mod  # noqa: E402

FOUNDRY_DIR = REPO_ROOT / ".foundry"

# Non-conformant state files, each with the owner and the reason it is not this
# workstream's to rewrite. Every entry must still exist AND still fail; see the
# module docstring.
EXEMPTIONS: dict[str, tuple[str, str]] = {
    ".foundry/pb03-304-terminal-hardening-20260929.yaml": (
        "PB-03 workstream",
        "active foreign surface (PR #316 open, sol/pb03-current-main-runtime-v2-20260929 "
        "and siblings exist); rewriting another live workstream's state is not in scope here",
    ),
    ".foundry/wsr24-freeze-production-bootstrap-readiness-20260927.json": (
        "WSR24 workstream",
        "foreign workstream, merged as PR #274; this is a pre-schema artifact missing 11 "
        "required 2.0 fields including schema_version, so migration is its owner's action",
    ),
    ".foundry/project-hygiene-canonicalization-20260929.yaml": (
        "PROJECT-HYGIENE-CANONICALIZATION-20260929 (merged as PR #359)",
        "closed pre-contract record: in_scope/out_of_scope were never recorded as lists, so "
        "conforming would mean composing them rather than recovering them",
    ),
    ".foundry/legacy-donor-salvage-20260929.yaml": (
        "LAB-LEGACY-DONOR-SALVAGE-20260929 (merged as PR #344)",
        "closed pre-contract record, same category as the hygiene file above",
    ),
}


def _state_files() -> list[Path]:
    """Tracked top-level ``.foundry`` files that declare a workstream.

    Detection is by content (``objective`` or ``workstream``) rather than by
    filename, so a new state file under any naming convention is caught. Files
    that merely live in ``.foundry`` -- ``executor-profiles.json``,
    ``safe-auto-battery-*.json``, ``conformance-ledger-*.json``,
    ``repo-profiles/`` -- declare no workstream and are correctly skipped.
    """
    found: list[Path] = []
    for path in sorted(FOUNDRY_DIR.iterdir()):
        if not path.is_file() or path.suffix not in (".yaml", ".yml", ".json"):
            continue
        if path.name.endswith(".schema.json"):
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and ("objective" in data or "workstream" in data):
            found.append(path)
    return found


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def test_state_files_are_discovered() -> None:
    """Floor check: an empty sweep would make every assertion below vacuous."""
    names = {_rel(p) for p in _state_files()}
    assert len(names) >= 8, f"expected the known state files, found {sorted(names)}"


def test_evidence_receipt_is_not_discovered_as_workstream_state() -> None:
    """The runtime receipt is evidence; it must not masquerade as state.

    Detection is content-based, so the receipt staying out of this sweep means
    it declares no ``objective``/``workstream`` key. Registering it in
    EXEMPTIONS or padding it with schema-2.0 workstream fields would instead
    dress an evidence record as workstream state.
    """
    names = {_rel(p) for p in _state_files()}
    receipt = ".foundry/space-bunny-rebind-runtime-activation-20261006.json"
    assert receipt not in names, (
        "the evidence receipt is being swept as a workstream state file; keep its "
        "fields distinct from workstream-state keys instead of exempting it"
    )
    # Wrong-reason control: content detection must still sweep .json state
    # files, or the assertion above would pass merely because JSON is skipped
    # wholesale rather than because the receipt is shaped as evidence.
    assert any(name.endswith(".json") for name in names), sorted(names)


@pytest.mark.parametrize("path", _state_files(), ids=_rel)
def test_state_file_is_conformant_or_registered(path: Path) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    errors = state_mod.validate(data)
    key = _rel(path)

    if key in EXEMPTIONS:
        assert errors, (
            f"{key} now validates against state.py. That is an improvement, not a "
            "failure -- remove its entry from EXEMPTIONS so the guard covers it."
        )
        return

    assert not errors, (
        f"{key} fails state.py validation: {errors[0]}"
        + (f" (+{len(errors) - 1} more)" if len(errors) > 1 else "")
        + ". safe_push.py rejects pushes on this, so the workstream cannot push "
        "through the canonical gate. Add the required schema 2.0 fields, or register "
        "the file in EXEMPTIONS with an owner and a reason."
    )


def test_every_exemption_still_points_at_a_real_file() -> None:
    """A stale path in EXEMPTIONS would silently stop covering anything."""
    for key in EXEMPTIONS:
        assert (REPO_ROOT / key).is_file(), f"EXEMPTIONS names a file that does not exist: {key}"


def test_exemption_entries_carry_owner_and_reason() -> None:
    for key, entry in EXEMPTIONS.items():
        owner, reason = entry
        assert owner.strip(), f"{key}: exemption has no owner"
        assert len(reason.strip()) > 40, f"{key}: exemption reason is not substantive"
