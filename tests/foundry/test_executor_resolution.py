"""Wrong-reason / regression controls for two-profile executor resolution.

Policy (Owner directive 2026-10-13): DeepSeek V4.1 Flash on OpenCode Go
(``opencode-go/deepseek-v4.1-flash``, native max) is the default and only active
executor; when a catalog is supplied or inspected its canonical id must be listed,
otherwise fail closed. Step 5 Preview (OpenCode Zen ``opencode/step-5-preview-free``)
is SUSPENDED; if a registry ever reactivated it, it would resolve only after live
pinned-CLI Zen catalog inspection. No cross-family substitute and no post-selection
fallback exists.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from foundry import executor_profiles as ep  # noqa: E402

DEEPSEEK = "opencode-go/deepseek-v4.1-flash"
STEP = "opencode/step-5-preview-free"
# Go ids share the exhausted Go monthly quota and are no longer admitted.
STEP_GO = "opencode-go/retired"
STEP_GO_FREE = "opencode-go/retired-free"


def _registry() -> ep.ExecutorRegistry:
    return ep.load_registry()


def _step_reactivated_registry(tmp_path: Path) -> ep.ExecutorRegistry:
    """Hypothetical registry in which a later Owner instruction reactivated Step.

    Keeps the Zen catalog fail-closed properties under test although the shipped
    registry suspends Step.
    """
    doc = _drifted_registry_doc()
    doc["profiles"]["step"]["runtime_status"] = "ACTIVE"
    doc["profiles"]["step"].pop("suspension")
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return ep.load_registry(path)


def test_deepseek_is_default_and_step_is_suspended() -> None:
    registry = _registry()
    assert registry.default_profile == "deepseek"
    assert registry.logical_profiles == ("deepseek", "step")
    assert registry.active_profiles == ("deepseek",)
    assert registry.active_runtime_ids == (DEEPSEEK,)
    resolved = ep.resolve_executor("deepseek", registry=registry, catalog=[DEEPSEEK, STEP])
    assert resolved.resolved_model_id == DEEPSEEK
    assert resolved.resolved_provider == "opencode-go"
    assert resolved.model_alias_class == "CANONICAL"
    assert resolved.native_variant == "max"
    assert resolved.catalog_checked is True
    # A SUSPENDED profile never resolves, even when its model is listed.
    with pytest.raises(ep.ExecutorResolutionError, match="SUSPENDED") as excinfo:
        ep.resolve_executor("step", registry=registry, catalog=[DEEPSEEK, STEP])
    # The refusal names the 2026-10-13 directive and never claims "Step only".
    assert "2026-10-13" in str(excinfo.value)
    assert "Step 5 Preview only" not in str(excinfo.value)


def test_deepseek_without_catalog_resolves_to_pinned_id_without_inspection() -> None:
    resolved = ep.resolve_executor("deepseek", registry=_registry())
    assert resolved.resolved_model_id == DEEPSEEK
    assert resolved.catalog_checked is False
    assert resolved.catalog_source == "not_inspected"


def test_deepseek_absent_from_inspected_catalog_fails_closed() -> None:
    with pytest.raises(ep.ExecutorResolutionError, match="absent from the inspected catalog"):
        ep.resolve_executor("deepseek", registry=_registry(), catalog=[STEP, "longcat/x"])


def test_suspended_default_or_unknown_status_fails_closed() -> None:
    doc = _drifted_registry_doc()
    doc["profiles"]["deepseek"]["runtime_status"] = "SUSPENDED"
    assert any("must be ACTIVE" in error for error in ep.validate_registry(doc))
    doc = _drifted_registry_doc()
    doc["profiles"]["step"]["runtime_status"] = "PAUSED"
    assert any("runtime_status 'PAUSED'" in error for error in ep.validate_registry(doc))


def test_each_logical_profile_is_pinned_to_its_native_variant() -> None:
    """One highest native variant per profile, exactly as its provider lists."""
    registry = _registry()
    expected = {"deepseek": "max", "step": "high"}
    for name in registry.logical_profiles:
        spec = registry.profiles[name]
        assert spec.native_variant == expected[name], name
        for admitted in spec.admitted:
            assert registry.runtime_identity[admitted.runtime_id].logical_profile == name


def test_canonical_step_available_selects_canonical(tmp_path: Path) -> None:
    resolved = ep.resolve_executor(
        "step", registry=_step_reactivated_registry(tmp_path), catalog=[STEP]
    )
    assert resolved.resolved_model_id == STEP
    assert resolved.model_alias_class == "CANONICAL"
    assert resolved.native_variant == "high"
    assert resolved.catalog_checked is True


def test_zen_step_selected_even_when_go_ids_are_listed_first(tmp_path: Path) -> None:
    resolved = ep.resolve_executor(
        "step", registry=_step_reactivated_registry(tmp_path), catalog=[STEP_GO, STEP_GO_FREE, STEP]
    )
    assert resolved.resolved_model_id == STEP
    assert resolved.model_alias_class == "CANONICAL"
    assert resolved.logical_executor_profile == "step"
    assert resolved.resolved_provider == "opencode"
    assert resolved.native_variant == "high"


def test_only_go_step_ids_present_fails_closed(tmp_path: Path) -> None:
    """The Go ids are not a fallback for the Zen id."""
    with pytest.raises(ep.ExecutorResolutionError, match="no admitted step"):
        ep.resolve_executor(
            "step",
            registry=_step_reactivated_registry(tmp_path),
            catalog=[DEEPSEEK, STEP_GO, STEP_GO_FREE],
        )


def test_neither_step_id_present_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ep.ExecutorResolutionError, match="no admitted step"):
        ep.resolve_executor(
            "step", registry=_step_reactivated_registry(tmp_path), catalog=[DEEPSEEK]
        )


def test_longcat_present_without_deepseek_fails_closed_never_substitutes() -> None:
    with pytest.raises(ep.ExecutorResolutionError):
        ep.resolve_executor(
            "deepseek",
            registry=_registry(),
            catalog=["longcat/longcat-flash", STEP],
        )


def test_step_without_catalog_inspection_fails_closed(monkeypatch, tmp_path: Path) -> None:
    """No catalog listing means no Step selection: fail closed, never guess."""

    def unavailable(*args, **kwargs):
        raise ep.ExecutorResolutionError("live catalog inspection failed; fail closed")

    monkeypatch.setattr(ep, "load_live_catalog", unavailable)
    with pytest.raises(ep.ExecutorResolutionError, match="fail closed"):
        ep.resolve_executor("step", registry=_step_reactivated_registry(tmp_path), catalog=None)


def test_catalog_parse_ignores_foreign_rows_and_malformed_lines() -> None:
    stdout = (
        "longcat/longcat-flash\n"
        "\n"
        "AUTH_REQUIRED\n"
        "opencode-go/deepseek-v4.1-flash\n"
        "other/provider/model extra metadata\n"
        "opencode/step-5-preview-free\n"
        "opencode-go/deepseek-v4.1-flash\n"
    )
    assert ep.parse_catalog_output(stdout) == (DEEPSEEK,)
    assert ep.parse_catalog_output(stdout, ep.ZEN_PROVIDER) == (STEP,)


class _Completed:
    def __init__(self, returncode: int, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


def test_load_live_catalog_uses_the_pinned_models_mechanism() -> None:
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        return _Completed(0, f"{DEEPSEEK}\n{STEP}\n")

    models, source = ep.load_live_catalog("pinned-opencode", runner=runner)
    assert calls == [["pinned-opencode", "models", "opencode-go"]]
    # Only Go rows survive: the Zen Step id is never parsed as a Go model.
    assert models == (DEEPSEEK,)
    assert source == "cli:opencode-go"
    # The suspended Zen profile inspects the Zen provider catalog instead.
    calls.clear()
    zen_models, zen_source = ep.load_live_catalog(
        "pinned-opencode", runner=runner, provider=ep.ZEN_PROVIDER
    )
    assert calls == [["pinned-opencode", "models", "opencode"]]
    assert zen_models == (STEP,)
    assert zen_source == "cli:opencode"


def test_load_live_catalog_failure_is_fail_closed() -> None:
    def runner_nonzero(command, **kwargs):
        return _Completed(7, "")

    with pytest.raises(ep.ExecutorResolutionError, match="fail closed"):
        ep.load_live_catalog(runner=runner_nonzero)

    def runner_raises(command, **kwargs):
        raise OSError("binary missing")

    with pytest.raises(ep.ExecutorResolutionError, match="fail closed"):
        ep.load_live_catalog(runner=runner_raises)

    def runner_empty(command, **kwargs):
        return _Completed(0, "longcat/only\n")

    with pytest.raises(ep.ExecutorResolutionError):
        ep.load_live_catalog(runner=runner_empty)


def test_post_selection_runtime_failure_can_only_block_never_fallback() -> None:
    """A failure AFTER selection must not re-resolve to another executor family."""
    resolved = ep.resolve_executor("deepseek", registry=_registry(), catalog=[DEEPSEEK])
    pin = ep.ExecutorPin(executor=resolved)
    outcome = pin.on_failure("RUNTIME_QUOTA", "provider returned 429")
    assert outcome.verdict == "BLOCKED"
    assert outcome.failure_class == "RUNTIME_QUOTA"
    assert outcome.fallback_attempted is False
    assert outcome.executor is resolved
    assert outcome.executor.resolved_model_id == DEEPSEEK
    # The outcome surface carries no alternate executor at all.
    assert not hasattr(outcome, "fallback_executor")


def test_resolved_exact_model_id_is_persisted_in_provenance() -> None:
    resolved = ep.resolve_executor("deepseek", registry=_registry(), catalog=[DEEPSEEK])
    provenance = resolved.to_provenance()
    assert provenance == {
        "logical_executor_profile": "deepseek",
        "resolved_provider": "opencode-go",
        "resolved_model_id": DEEPSEEK,
        "model_alias_class": "CANONICAL",
        "native_variant": "max",
        "catalog_checked": True,
        "catalog_source": "provided",
    }


def test_unknown_logical_profile_is_refused() -> None:
    for name in ("longcat", "glm", "muse", "", "other"):
        with pytest.raises(ep.ExecutorResolutionError, match="unknown execution profile"):
            ep.resolve_executor(name, registry=_registry(), catalog=[DEEPSEEK])


def _drifted_registry_doc() -> dict:
    return json.loads(ep.DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))


def test_no_third_logical_executor_can_be_reachable(tmp_path: Path) -> None:
    doc = _drifted_registry_doc()
    doc["profiles"]["longcat"] = {
        "model": "longcat/longcat-flash",
        "native_variant": "max",
        "runtime_status": "ACTIVE",
    }
    errors = ep.validate_registry(doc)
    assert any("exactly deepseek+step" in error for error in errors)
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ep.ExecutorResolutionError, match="registry invalid"):
        ep.load_registry(path)


def test_registry_default_drift_and_alias_on_unknown_profile_fail_closed() -> None:
    doc = _drifted_registry_doc()
    doc["current_runtime_default"] = "step"
    assert any("default must be deepseek" in error for error in ep.validate_registry(doc))

    doc = _drifted_registry_doc()
    doc["runtime_identity"]["longcat/model"] = {
        "logical_profile": "longcat",
        "alias_class": "CANONICAL",
    }
    errors = ep.validate_registry(doc)
    assert any("unknown logical profile" in error for error in errors)


def test_registry_rejects_alias_drift_and_canonical_reclassification() -> None:
    doc = _drifted_registry_doc()
    doc["runtime_identity"]["opencode/step"] = {
        "logical_profile": "step",
        "alias_class": "LEGACY_ALIAS",
    }
    errors = ep.validate_registry(doc)
    assert any("admits no legacy alias" in error for error in errors)

    doc = _drifted_registry_doc()
    doc["runtime_identity"][STEP_GO] = {
        "logical_profile": "step",
        "alias_class": "LEGACY_ALIAS",
    }
    errors = ep.validate_registry(doc)
    assert any("must use 'opencode' (Zen)" in error for error in errors)

    doc = _drifted_registry_doc()
    doc["runtime_identity"]["opencode/deepseek-v4.1-flash"] = {
        "logical_profile": "deepseek",
        "alias_class": "CANONICAL",
    }
    errors = ep.validate_registry(doc)
    assert any("must use 'opencode-go' (Go)" in error for error in errors)

    doc = _drifted_registry_doc()
    doc["runtime_identity"][STEP]["alias_class"] = "LEGACY_ALIAS"
    errors = ep.validate_registry(doc)
    assert any("canonical" in error for error in errors)


def test_registry_rejects_step_alias_pointing_at_another_family() -> None:
    doc = _drifted_registry_doc()
    doc["runtime_identity"]["other-provider/model"] = {
        "logical_profile": "step",
        "alias_class": "LEGACY_ALIAS",
    }
    errors = ep.validate_registry(doc)
    assert any("provider is not one of" in error for error in errors)


def test_live_catalog_inspection_matches_the_pinned_cli_when_available() -> None:
    """Integration guard: the supported catalog command lists the active admission.

    Skips only when the qualified CLI is unavailable in this environment; the
    live check is never replaced by a guessed identity.
    """
    binary = Path.home() / ".opencode" / "bin" / "opencode"
    if not binary.exists():
        pytest.skip("qualified opencode CLI unavailable")
    result = subprocess.run(
        [str(binary), "models", "opencode-go"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:  # pragma: no cover - environment dependent
        pytest.skip("live catalog unavailable in this environment")
    models = ep.parse_catalog_output(result.stdout)
    assert DEEPSEEK in models


def test_just_retired_zen_executor_is_refused_everywhere() -> None:
    """The executor retired on 2026-10-12 is neither a profile nor an admitted id."""
    registry = _registry()
    retired_id = "opencode/space-bunny-free"
    assert registry.admitted_runtime(retired_id) is None
    assert retired_id not in registry.active_runtime_ids
    with pytest.raises(ep.ExecutorResolutionError):
        ep.resolve_executor("space-bunny", registry=registry, catalog=[retired_id, DEEPSEEK])
    # A catalog that lists only the retired id never resolves DeepSeek to it.
    with pytest.raises(ep.ExecutorResolutionError):
        ep.resolve_executor("deepseek", registry=registry, catalog=[retired_id])
