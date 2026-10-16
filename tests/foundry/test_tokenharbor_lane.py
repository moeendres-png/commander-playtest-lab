"""Token Harbor (`/oc-th`) lane invariants: second ACTIVE profile, Zen default, no fallback."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "foundry"))
sys.path.insert(0, str(ROOT / "tests" / "unit"))

import executor_profiles as executor_mod  # noqa: E402
import launcher  # noqa: E402

TH_MODEL = "tokenharbor/deepseek-v4.1-flash"
ZEN_MODEL = "opencode/deepseek-v4.1-flash-free"


def _json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_registry_has_two_active_profiles_and_zen_default() -> None:
    doc = _json(".foundry/executor-profiles.json")
    assert doc["current_runtime_default"] == "deepseek"
    assert {n: (s["model"], s["runtime_status"]) for n, s in doc["profiles"].items()} == {
        "deepseek": (ZEN_MODEL, "ACTIVE"),
        "deepseek-th": (TH_MODEL, "ACTIVE"),
    }
    assert doc["profiles"]["deepseek-th"]["native_variant"] == "provider_default"
    assert doc["profiles"]["deepseek-th"]["effort_control"] == "NONE_EXPOSED"
    assert doc["policy"]["automatic_fallback"] is False
    evidence = doc["activation_gate"]["activation_evidence_2026_10_16_tokenharbor"]
    assert evidence["authenticated_runtime_smoke"].startswith("NOT_RUN")
    assert "logged" in evidence["data_note"]
    reg = executor_mod.load_registry()
    assert reg.default_profile == "deepseek"
    assert reg.active_profiles == ("deepseek", "deepseek-th")
    assert "tokenharbor" in executor_mod.ADMITTED_PROVIDERS


def test_th_profile_resolves_from_registry_and_zen_still_needs_its_catalog() -> None:
    th = executor_mod.resolve_executor("deepseek-th")
    assert (th.resolved_provider, th.resolved_model_id) == ("tokenharbor", TH_MODEL)
    assert th.native_variant == "provider_default"
    # Zen never resolves to the Token Harbor id (no fallback between providers).
    with pytest.raises(executor_mod.ExecutorResolutionError):
        executor_mod.resolve_executor("deepseek", catalog=[TH_MODEL])
    zen = executor_mod.resolve_executor("deepseek", catalog=[ZEN_MODEL, TH_MODEL])
    assert zen.resolved_model_id == ZEN_MODEL and zen.native_variant == "max"


def test_registry_rejects_a_token_harbor_id_under_the_zen_provider() -> None:
    doc = _json(".foundry/executor-profiles.json")
    doc["runtime_identity"]["opencode/deepseek-v4.1-flash"] = doc["runtime_identity"].pop(TH_MODEL)
    doc["profiles"]["deepseek-th"]["model"] = "opencode/deepseek-v4.1-flash"
    assert executor_mod.validate_registry(doc)


def test_opencode_json_key_only_via_env_and_default_stays_zen() -> None:
    raw = (ROOT / "opencode.json").read_text(encoding="utf-8")
    config = json.loads(raw)
    assert config["model"] == ZEN_MODEL
    assert config["enabled_providers"] == ["opencode", "tokenharbor"]
    th = config["provider"]["tokenharbor"]
    assert th["options"]["apiKey"] == "{env:TOKENHARBOR_API_KEY}"
    assert th["options"]["baseURL"] == "https://tokenharbor.ai/v1"
    assert list(th["models"]) == ["deepseek-v4.1-flash"]
    assert "variants" not in th["models"]["deepseek-v4.1-flash"]
    assert not re.search(r"thk_[A-Za-z0-9]", raw)


def test_launcher_pins_exactly_one_provider_per_run() -> None:
    th = launcher.execution_identity(None, "high", "deepseek-th")
    assert (th["provider"], th["model"]) == ("tokenharbor", TH_MODEL)
    bundle = launcher.build_content_bundle(str(ROOT), [], None, "deepseek-th")
    assert bundle["model"] == bundle["small_model"] == TH_MODEL
    assert bundle["enabled_providers"] == ["tokenharbor"]
    assert list(bundle["provider"]) == ["tokenharbor"]
    assert bundle["provider"]["tokenharbor"]["options"]["apiKey"] == "{env:TOKENHARBOR_API_KEY}"
    assert all(agent == {"model": TH_MODEL} for agent in bundle["agent"].values())
    allow = [p for p in bundle["experimental"]["policies"] if p["effect"] == "allow"]
    assert allow[-1]["resource"] == "tokenharbor"
    # Default stays Zen, with the native max pin and no Token Harbor provider.
    default = launcher.build_content_bundle(
        str(ROOT), [], None, None, catalog=[ZEN_MODEL], catalog_source="test"
    )
    assert default["model"] == ZEN_MODEL
    assert default["enabled_providers"] == ["opencode"]
    assert "tokenharbor" not in default["provider"]
    assert all(a["variant"] == "max" for a in default["agent"].values())
    assert launcher.DEFAULT_EXECUTION_PROFILE == "deepseek"


def test_launcher_refuses_a_literal_token_harbor_key(tmp_path: Path) -> None:
    config = _json("opencode.json")
    config["provider"]["tokenharbor"]["options"]["apiKey"] = "literal-key"
    (tmp_path / "opencode.json").write_text(json.dumps(config), encoding="utf-8")
    (tmp_path / ".opencode" / "agents").mkdir(parents=True)
    with pytest.raises(ValueError, match="env reference"):
        launcher.build_content_bundle(str(tmp_path), [], None, "deepseek-th")


# --- workflow: /oc and /oc-th are mutually exclusive -------------------------------------


def _wf() -> dict:
    return yaml.safe_load((ROOT / ".github/workflows/opencode.yml").read_text(encoding="utf-8"))


def _fires(job: str, body: str, commenter: str = "OWNER") -> bool:
    from test_workflow_security import _event_context, condition_result

    ctx = _event_context(commenter=commenter, target="OWNER", target_login="m", body=body)
    return condition_result(str(_wf()["jobs"][job]["if"]), ctx)


@pytest.mark.parametrize(
    ("body", "oc", "th"),
    [
        ("/oc do the task", True, False),
        ("please /oc do the task", True, False),
        ("/oc-th do the task", False, True),
        ("please /oc-th do the task", False, True),
        ("/opencode run", True, False),
        ("unrelated comment", False, False),
    ],
)
def test_oc_and_oc_th_fire_only_on_their_own_command(body: str, oc: bool, th: bool) -> None:
    assert _fires("opencode", body) is oc
    assert _fires("opencode-th", body) is th


def test_oc_th_job_mirrors_oc_with_token_harbor_model_and_key_only_there() -> None:
    jobs = _wf()["jobs"]
    assert _fires("opencode-th", "/oc-th x", commenter="NONE") is False
    oc_steps, th_steps = jobs["opencode"]["steps"], jobs["opencode-th"]["steps"]
    assert [s.get("name") for s in oc_steps] == [s.get("name") for s in th_steps]
    assert jobs["opencode"]["permissions"] == jobs["opencode-th"]["permissions"]
    run = next(s for s in th_steps if s.get("name") == "Run opencode")
    assert run["env"]["MODEL"] == TH_MODEL
    assert run["env"]["MENTIONS"] == "/oc-th"
    assert run["env"]["TOKENHARBOR_API_KEY"] == "${{ secrets.TOKENHARBOR_API_KEY }}"
    assert "OPENCODE_API_KEY" not in run["env"]
    assert run.get("timeout-minutes") == 55
    text = (ROOT / ".github/workflows/opencode.yml").read_text(encoding="utf-8")
    assert text.count("secrets.TOKENHARBOR_API_KEY") == 1
    for name, job in jobs.items():
        if name != "opencode-th":
            assert "TOKENHARBOR" not in json.dumps(job)
