"""Wrong-reason / regression controls for one-profile executor resolution.

Policy: DeepSeek V4.1 Flash (OpenCode Zen ``opencode/deepseek-v4.1-flash-free``, native
``max``) is the default and only active executor; it resolves only after live pinned-CLI
catalog inspection, otherwise fail closed. Step 5 Preview left the catalog and is not a
profile. No cross-family substitute and no post-selection fallback exists.
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

DEEPSEEK = "opencode/deepseek-v4.1-flash-free"
# Retired ids: the OpenCode Go DeepSeek record, Step 5 Preview (left the catalog),
# and the Token Harbor free route (retired 2026-10-16, Owner instruction).
DEEPSEEK_GO = "opencode-go/deepseek-v4.1-flash"
RETIRED_STEP = "opencode/step-5-preview-free"
DEEPSEEK_GO_FREE = "opencode-go/retired-free"


def _registry() -> ep.ExecutorRegistry:
    return ep.load_registry()


def test_deepseek_is_the_one_default_active_profile() -> None:
    registry = _registry()
    assert registry.default_profile == "deepseek"
    assert registry.logical_profiles == ("deepseek",)
    assert registry.active_profiles == ("deepseek",)
    assert registry.active_runtime_ids == (DEEPSEEK,)
    resolved = ep.resolve_executor(
        "deepseek", registry=registry, catalog=[RETIRED_STEP, DEEPSEEK_GO, DEEPSEEK]
    )
    assert resolved.resolved_model_id == DEEPSEEK
    assert resolved.model_alias_class == "CANONICAL"
    assert resolved.native_variant == "max"
    assert resolved.catalog_checked is True
    # Step is neither a profile nor resolvable, even when its id is listed.
    with pytest.raises(ep.ExecutorResolutionError, match="unknown execution profile"):
        ep.resolve_executor("step", registry=registry, catalog=[RETIRED_STEP, DEEPSEEK])


def test_suspended_default_or_unknown_status_fails_closed() -> None:
    doc = _drifted_registry_doc()
    doc["profiles"]["deepseek"]["runtime_status"] = "SUSPENDED"
    assert any("must be ACTIVE" in error for error in ep.validate_registry(doc))
    doc = _drifted_registry_doc()
    doc["profiles"]["deepseek"]["runtime_status"] = "PAUSED"
    assert any("runtime_status 'PAUSED'" in error for error in ep.validate_registry(doc))


def test_profile_is_pinned_to_its_native_variant_never_below_high() -> None:
    """One highest native variant per profile, exactly as its provider lists."""
    registry = _registry()
    expected = {"deepseek": "max"}
    checked = list(registry.logical_profiles)
    assert checked, "nothing was checked: registry.logical_profiles is empty"
    for name in checked:
        spec = registry.profiles[name]
        assert spec.native_variant == expected[name], name
        assert spec.native_variant not in ("none", "off", "minimal", "low", "medium")
        for admitted in spec.admitted:
            assert registry.runtime_identity[admitted.runtime_id].logical_profile == name
    drifted = _drifted_registry_doc()
    for lower in ("high", "medium", "low"):
        drifted["profiles"]["deepseek"]["native_variant"] = lower
        assert any("native_variant must be 'max'" in e for e in ep.validate_registry(drifted))


def test_canonical_deepseek_available_selects_canonical() -> None:
    resolved = ep.resolve_executor("deepseek", registry=_registry(), catalog=[DEEPSEEK])
    assert resolved.resolved_model_id == DEEPSEEK
    assert resolved.model_alias_class == "CANONICAL"
    assert resolved.native_variant == "max"
    assert resolved.catalog_checked is True


def test_zen_id_selected_even_when_retired_ids_are_listed_first() -> None:
    resolved = ep.resolve_executor(
        "deepseek", registry=_registry(), catalog=[DEEPSEEK_GO, DEEPSEEK_GO_FREE, DEEPSEEK]
    )
    assert resolved.resolved_model_id == DEEPSEEK
    assert resolved.model_alias_class == "CANONICAL"
    assert resolved.logical_executor_profile == "deepseek"
    assert resolved.resolved_provider == "opencode"
    assert resolved.native_variant == "max"


def test_retired_token_harbor_profile_is_unknown() -> None:
    """deepseek-th was retired 2026-10-16: it no longer resolves at all."""
    with pytest.raises(ep.ExecutorResolutionError, match="unknown execution profile"):
        ep.resolve_executor("deepseek-th", registry=_registry(), catalog=[DEEPSEEK])


def test_only_retired_ids_present_fails_closed() -> None:
    """The Go DeepSeek id and Step are not a fallback for the Zen id."""
    with pytest.raises(ep.ExecutorResolutionError, match="no admitted deepseek"):
        ep.resolve_executor(
            "deepseek",
            registry=_registry(),
            catalog=[RETIRED_STEP, DEEPSEEK_GO, DEEPSEEK_GO_FREE],
        )


def test_deepseek_id_absent_from_catalog_fails_closed() -> None:
    """Step left the live catalog; a catalog without the DeepSeek Zen id never resolves."""
    with pytest.raises(ep.ExecutorResolutionError, match="no admitted deepseek"):
        ep.resolve_executor("deepseek", registry=_registry(), catalog=["opencode/big-pickle"])


def test_longcat_present_without_deepseek_fails_closed_never_substitutes() -> None:
    with pytest.raises(ep.ExecutorResolutionError):
        ep.resolve_executor(
            "deepseek",
            registry=_registry(),
            catalog=["longcat/longcat-flash", DEEPSEEK_GO],
        )


def test_deepseek_without_catalog_inspection_fails_closed(monkeypatch) -> None:
    """No catalog listing means no DeepSeek selection: fail closed, never guess."""

    def unavailable(*args, **kwargs):
        raise ep.ExecutorResolutionError("live catalog inspection failed; fail closed")

    monkeypatch.setattr(ep, "load_live_catalog", unavailable)
    with pytest.raises(ep.ExecutorResolutionError, match="fail closed"):
        ep.resolve_executor("deepseek", registry=_registry(), catalog=None)


def test_catalog_parse_ignores_foreign_rows_and_malformed_lines() -> None:
    stdout = (
        "longcat/longcat-flash\n"
        "\n"
        "AUTH_REQUIRED\n"
        "opencode/deepseek-v4.1-flash-free\n"
        "other/provider/model extra metadata\n"
        "opencode-go/retired\n"
        "opencode/deepseek-v4.1-flash-free\n"
    )
    assert ep.parse_catalog_output(stdout) == (DEEPSEEK,)


class _Completed:
    def __init__(self, returncode: int, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


def test_load_live_catalog_uses_the_pinned_models_mechanism() -> None:
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        return _Completed(0, f"{DEEPSEEK_GO}\n{DEEPSEEK}\n")

    models, source = ep.load_live_catalog("pinned-opencode", runner=runner)
    assert calls == [["pinned-opencode", "models", "opencode"]]
    # Only Zen rows survive: the Go DeepSeek id is never parsed as a Zen model.
    assert models == (DEEPSEEK,)
    assert source == "cli:opencode"


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
        "resolved_provider": "opencode",
        "resolved_model_id": DEEPSEEK,
        "model_alias_class": "CANONICAL",
        "native_variant": "max",
        "catalog_checked": True,
        "catalog_source": "provided",
    }


def test_unknown_logical_profile_is_refused() -> None:
    for name in ("step", "longcat", "glm", "muse", "", "other"):
        with pytest.raises(ep.ExecutorResolutionError, match="unknown execution profile"):
            ep.resolve_executor(name, registry=_registry(), catalog=[DEEPSEEK])


def _drifted_registry_doc() -> dict:
    return json.loads(ep.DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))


def test_no_second_logical_executor_can_be_reachable(tmp_path: Path) -> None:
    doc = _drifted_registry_doc()
    doc["profiles"]["longcat"] = {
        "model": "longcat/longcat-flash",
        "native_variant": "max",
        "runtime_status": "ACTIVE",
    }
    errors = ep.validate_registry(doc)
    assert any("registry must expose exactly deepseek" in error for error in errors)
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
    doc["runtime_identity"]["opencode/deepseek"] = {
        "logical_profile": "deepseek",
        "alias_class": "LEGACY_ALIAS",
    }
    errors = ep.validate_registry(doc)
    assert any("admits no legacy alias" in error for error in errors)

    doc = _drifted_registry_doc()
    doc["runtime_identity"][DEEPSEEK_GO] = {
        "logical_profile": "deepseek",
        "alias_class": "LEGACY_ALIAS",
    }
    errors = ep.validate_registry(doc)
    # The OpenCode Go provider is retired: its ids are not even admitted providers.
    assert any("provider is not one of ['opencode']" in error for error in errors)

    doc = _drifted_registry_doc()
    doc["runtime_identity"][DEEPSEEK]["alias_class"] = "LEGACY_ALIAS"
    errors = ep.validate_registry(doc)
    assert any("canonical" in error for error in errors)


def test_registry_rejects_deepseek_alias_pointing_at_another_family() -> None:
    doc = _drifted_registry_doc()
    doc["runtime_identity"]["other-provider/model"] = {
        "logical_profile": "deepseek",
        "alias_class": "LEGACY_ALIAS",
    }
    errors = ep.validate_registry(doc)
    assert any("provider is not one of" in error for error in errors)


def test_live_catalog_inspection_matches_the_pinned_cli_when_available() -> None:
    """Integration guard: the supported catalog command lists the admitted id.

    Skips only when the qualified CLI is unavailable in this environment; the
    live check is never replaced by a guessed identity.
    """
    binary = Path.home() / ".opencode" / "bin" / "opencode"
    if not binary.exists():
        pytest.skip("qualified opencode CLI unavailable")
    result = subprocess.run(
        [str(binary), "models", "opencode"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:  # pragma: no cover - environment dependent
        pytest.skip("live catalog unavailable in this environment")
    models = ep.parse_catalog_output(result.stdout)
    assert DEEPSEEK in models


def test_just_retired_zen_executor_is_refused_everywhere() -> None:
    """Executors retired before 2026-10-16 are neither a profile nor an admitted id."""
    registry = _registry()
    for retired_id in ("opencode/space-bunny-free", RETIRED_STEP, DEEPSEEK_GO):
        assert registry.admitted_runtime(retired_id) is None
        assert retired_id not in registry.active_runtime_ids
        with pytest.raises(ep.ExecutorResolutionError):
            ep.resolve_executor("space-bunny", registry=registry, catalog=[retired_id, DEEPSEEK])
        # A catalog that lists only the retired id never resolves DeepSeek to it.
        with pytest.raises(ep.ExecutorResolutionError):
            ep.resolve_executor("deepseek", registry=registry, catalog=[retired_id])
