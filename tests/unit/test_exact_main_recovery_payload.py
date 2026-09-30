"""Exact-main recovery must not carry a stale engine identity or unproven runtime claims.

The workflow used to write a historical XMage pin literal as
``xmage_pinned_commit`` and literal ``True`` for runtime claims the recovery
run never checks. The payload is now built from the pin authority, and claims
without a same-commit receipt are NOT_BOUND.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "exact-main-recovery.yml"
COMMIT = "a" * 40
TREE = "b" * 40


@pytest.fixture(scope="module")
def builder() -> Any:
    spec = importlib.util.spec_from_file_location(
        "exact_main_recovery_payload", ROOT / "scripts" / "build_exact_main_recovery_payload.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_pin_is_read_from_the_pin_authority(builder: Any) -> None:
    authority = json.loads((ROOT / "config" / "rules_engines.json").read_text(encoding="utf-8"))
    assert builder.current_xmage_pin(ROOT) == authority["primary_engine"]["commit"]


@pytest.mark.parametrize("commit", [None, "", "9375f35a", "Z" * 40])
def test_a_missing_or_malformed_pin_fails_closed(builder: Any, tmp_path: Path, commit: Any) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "rules_engines.json").write_text(
        json.dumps({"primary_engine": {"commit": commit}}), encoding="utf-8"
    )
    with pytest.raises(builder.RecoveryPayloadError):
        builder.current_xmage_pin(tmp_path)


def test_a_missing_authority_fails_closed(builder: Any, tmp_path: Path) -> None:
    with pytest.raises(builder.RecoveryPayloadError):
        builder.current_xmage_pin(tmp_path)


def test_unchecked_runtime_claims_are_not_bound(builder: Any) -> None:
    closeout = builder.build_closeout(
        commit=COMMIT, tree=TREE, version="1.0", focused_tests=["pytest -q x"]
    )
    for claim in builder.UNBOUND_RUNTIME_CLAIMS:
        assert claim not in closeout, f"{claim} must not be a top-level literal"
        assert closeout["runtime_claims"][claim]["status"] == builder.NOT_BOUND
    assert closeout["observed_in_this_run"]["focused_architecture_tests"]["commands"] == [
        "pytest -q x"
    ]
    assert "declarations" in closeout["declared_architecture"]["note"]


@pytest.mark.parametrize(("commit", "tree"), [("abc", TREE), (COMMIT, "")])
def test_identity_must_be_exact(builder: Any, commit: str, tree: str) -> None:
    with pytest.raises(builder.RecoveryPayloadError):
        builder.build_provenance(commit=commit, tree=tree, version="1.0", xmage_pin=COMMIT)


def test_the_cli_writes_both_documents(builder: Any, tmp_path: Path) -> None:
    inner = tmp_path / "inner"
    assert (
        builder.main(
            [
                "--root",
                str(ROOT),
                "--inner",
                str(inner),
                "--commit",
                COMMIT,
                "--tree",
                TREE,
                "--version",
                "1.0",
            ]
        )
        == 0
    )
    provenance = json.loads((inner / "PROVENANCE.json").read_text(encoding="utf-8"))
    assert provenance["xmage_pinned_commit"] == builder.current_xmage_pin(ROOT)
    assert provenance["xmage_pin_source"] == "config/rules_engines.json#primary_engine.commit"
    assert (inner / "EXACT_MAIN_FINAL_CLOSEOUT.json").is_file()


def test_the_workflow_carries_no_engine_sha_literal() -> None:
    """Only pinned actions may carry a 40-hex literal; an engine pin must come from the authority."""
    offenders = [
        (number, line.strip())
        for number, line in enumerate(WORKFLOW.read_text(encoding="utf-8").splitlines(), start=1)
        if re.search(r"\b[0-9a-f]{40}\b", line)
        and not line.strip().startswith(("- uses:", "uses:"))
    ]
    assert offenders == []


def test_the_workflow_builds_the_payload_with_the_builder() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "scripts/build_exact_main_recovery_payload.py" in text
    assert "full_game_hidden_information_actor_scoped" not in text
