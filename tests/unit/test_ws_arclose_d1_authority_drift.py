"""WS91 re-integration of the WS-ARCLOSE-D1 current-authority drift-closure battery.

Structural only (no Docker, no network, no engine builds). Each test locks
the remediated current-authority wording so the six audit findings cannot
silently regress, while historical evidence stays preserved verbatim.

Rebased onto current canonical main (WS78/WS88/WS90): the canonical XMage pin
is the WS88 integrated successor (cfc36f...), the manifest wording is the WS88
addendum, the retention appendix carries both the WS88 resolution and the
WS-ARCLOSE-D1 addendum, and the historical root-state bytes are archived under
the WS91 evidence path. No test here changes Rules behavior, engine pins,
provider selection, or qualification credit.
"""

from __future__ import annotations

import json
from pathlib import Path

# Live pin: multiplayer candidate after the deterministic commander-zone ask order
# (mage#57), the card-scanner bulk lookup (mage#58) and the precon card coverage
# (mage#59) and the lazy playable-calculation card copy (mage#60), repin v7.
CANONICAL_XMAGE_PIN = "f4d12f6e8066203fba7aa38bd35ea3358117393d"
STALE_XMAGE_PIN = "06d166b098ad36b277edef01116472203d5a047e"
STALE_FORGE_PIN = "852066bf4f761b302ed17cb011999d8a8fe08ad6"


def _flat(text: str) -> str:
    """Collapse all whitespace so line-wrapped Markdown still matches."""
    return " ".join(text.split())


def _manifest(repo_root: Path) -> dict:
    return json.loads((repo_root / "config/rules_engines.json").read_text(encoding="utf-8"))


def test_manifest_pins_protocol_capabilities_untouched(repo_root: Path) -> None:
    manifest = _manifest(repo_root)
    assert manifest["primary_engine"]["commit"] == CANONICAL_XMAGE_PIN
    assert "secondary_engine" not in manifest
    assert manifest["protocol_version"] == "2.0.0"
    # Selection follows the Owner-signed Freeze and the D5 runtime switch.
    assert manifest["provider_decision"] == "XMAGE_SELECTED"
    assert manifest["current_runtime"]["provider_selected"] is True
    assert manifest["current_runtime"]["production_provider"] == "xmage"


def test_manifest_records_ws88_successor_pin_authority(repo_root: Path) -> None:
    """Current-main authority: WS88 integrated successor wording, not D1's draft."""
    note = _manifest(repo_root)["authority_note"]["known_stale_pointers"]
    assert CANONICAL_XMAGE_PIN in note
    assert "pin-free by design" in note
    assert "phase85.py" in note  # historical template provenance preserved
    assert "PIN_DIVERGENCE_DOCKERFILES" in note  # gate reference preserved


def test_dockerfiles_carry_no_stale_default_pins(repo_root: Path) -> None:
    for rel in ("docker/xmage/Dockerfile",):
        text = _flat((repo_root / rel).read_text(encoding="utf-8"))
        assert STALE_XMAGE_PIN not in text, rel
        assert STALE_FORGE_PIN not in text, rel
        assert "ARG ENGINE_COMMIT" in text, rel
        assert "intentionally no" in text and "defaults" in text, rel


def test_retention_appendix_g_preserves_history_and_records_successors(
    repo_root: Path,
) -> None:
    text = (repo_root / "docs/RETENTION_AND_LIFECYCLE_POLICY.md").read_text(encoding="utf-8")
    # Original WS-A1R/WS-A1D record untouched.
    assert "docker/forge/Dockerfile` defaults to `852066bf`" in text
    assert "NOT_RUN on the WS-A1D execution host: no Docker client there" in text
    # WS88 resolution preserved (canonical pin migration, pin-free flow).
    assert "Resolution (WS88)" in text
    assert "cfc36f445f917f101fa2ed588770e043f53bc44c" in text
    # Dated WS-ARCLOSE-D1 addendum re-integrated without rewriting history.
    assert "WS-ARCLOSE-D1 addendum (2026-09-13" in text
    assert "h4-docker-materialization.yml" in text
    assert "H4 PARTIAL" in text
    assert "H4B-Forge" in text and "UNKNOWN/NOT_RUN" in text


def test_fork_pointer_spec_preserves_design_and_records_supersession(
    repo_root: Path,
) -> None:
    text = (repo_root / "docs/FORK_AGENT_POINTER_SPEC.md").read_text(encoding="utf-8")
    # Original WS-A1R design record untouched.
    assert "WS-A1R-F1 (mage pointer)" in text
    assert "WS-A1R-F2 (forge pointer)" in text
    assert "NOT executed by WS-A1R" in text
    # Dated disposition appended.
    assert "## 5. Disposition (WS-ARCLOSE-D1, 2026-09-13" in text
    assert "SUPERSEDED" in text
    assert "never executed" in text
    assert "drift_check.py" in text


def test_agents_policy_keeps_its_load_bearing_statements(repo_root: Path) -> None:
    """Statements other tests used to pin before the lane tooling was removed."""
    agents = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
    assert "Rules Core" in agents
    assert "## 9. Reuse-first gate" in agents
    assert "no implicit active repository-root state" in agents.lower()
    authority = (repo_root / "docs/CURRENT_EXECUTION_AUTHORITY.md").read_text(encoding="utf-8")
    assert "A pushed WIP is never qualification PASS" in authority
