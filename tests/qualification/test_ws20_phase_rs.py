import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROVIDER = ROOT / "qualification/providers/phase_rs/ws10r_provider.py"
PROTOCOL = "commander-lab.rules-service/1.1.0"
BASELINE = "c83e52ae79ff2242578757c0f517badbb1a2621c"
SOURCE = "5c87559082f4703c10c3f70692a02bb675c5e576"


def call_provider(request, extra_env=None):
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    cp = subprocess.run(
        [sys.executable, str(PROVIDER)],
        input=json.dumps(request) + "\n",
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    return json.loads(cp.stdout.strip())


def test_ws20_v2_source_lock_is_exact_and_post_ws17r():
    lock = json.loads(
        (ROOT / "qualification/providers/phase_rs/PINNED_SOURCE.json").read_text()
    )
    assert lock["selected_upstream"]["repository"] == "phase-rs/phase"
    assert lock["selected_upstream"]["commit"] == SOURCE
    assert lock["selected_upstream"]["tree"] == "f4c7abc087566979672097baadd259dc0040874d"
    assert lock["selected_upstream"]["workspace_version"] == "0.67.0"
    assert lock["prior_locks"]["ws15_commit"] == "92c67b872c2a7f69c4a2069f0d0c3cb1b6b0d4c6"
    assert lock["fresh_delta"]["from_ws15_ahead"] == 11
    assert lock["fresh_delta"]["from_pre_ws17r_ws20_ahead"] == 4
    assert lock["target_baseline"]["commit"] == BASELINE
    assert lock["commander_blocker"]["status"] == "PRESENT_UPSTREAM"


def test_ws20_v2_requested_jjarrie_mirror_is_recorded_not_silently_substituted():
    lock = json.loads(
        (ROOT / "qualification/providers/phase_rs/PINNED_SOURCE.json").read_text()
    )
    requested = lock["requested_repository_check"]
    assert requested["repository"] == "JJarrie/phase-rs"
    assert requested["commit"] == "df3518d2464826b222b2cb659d1426c9425094ed"
    assert "historical mirror" in requested["assessment"]


def test_ws20_provider_handshake_is_truthful_nonproduction_and_bound():
    r = call_provider(
        {
            "protocol": PROTOCOL,
            "message_type": "HANDSHAKE",
            "request_id": "t",
            "session_id": None,
            "payload": {},
        },
        {
            "WS20_PHASE_PATCHED_TREE": "abc",
            "WS20_PHASE_PATCH_SHA256": "def",
            "WS20_PROVIDER_SHA256": "ghi",
            "WS20_COMMON_MANIFEST_SHA256": "jkl",
        },
    )
    p = r["payload"]
    assert r["message_type"] == "HANDSHAKE_RESULT"
    assert p["production_capable"] is False
    assert p["target_baseline"] == BASELINE
    assert p["upstream_commit"] == SOURCE
    assert p["native_action_authority"].endswith("GameAction")
    assert p["unsupported_policy"] == "fail-closed"
    assert p["native_session_bridge"] is False
    assert p["actor_scoped_observation_bridge"] is False
    assert p["clean_process_rsp_replay_bridge"] is False
    assert p["patched_tree"] == "abc"


def test_ws20_provider_never_synthesizes_missing_fixture_pass():
    r = call_provider(
        {
            "protocol": PROTOCOL,
            "message_type": "RUN_FIXTURE",
            "request_id": "t",
            "session_id": None,
            "payload": {"fixture": {"fixture_id": "PLAYER_COUNT_4P"}},
        }
    )
    assert r["payload"]["verdict"] == "UNSUPPORTED"
    assert r["payload"]["evidence_class"] == "NOT_RUN"
    assert r["payload"]["artifact_hashes"] == {}


def test_ws20_provider_transports_engine_native_fixture_payload_without_rewriting(tmp_path):
    runtime_map = tmp_path / "runtime.json"
    native = {
        "verdict": "FAIL",
        "evidence_class": "RUNTIME_VERIFIED",
        "reason": "native probe result",
        "artifact_hashes": {"probe": "00" * 32},
    }
    runtime_map.write_text(json.dumps({"PLAYER_COUNT_4P": native}), encoding="utf-8")
    r = call_provider(
        {
            "protocol": PROTOCOL,
            "message_type": "RUN_FIXTURE",
            "request_id": "t",
            "session_id": None,
            "payload": {"fixture": {"fixture_id": "PLAYER_COUNT_4P"}},
        },
        {"WS20_RUNTIME_RESULT_MAP": str(runtime_map)},
    )
    assert r["payload"] == native


def test_ws20_provider_rejects_unimplemented_session_operation():
    r = call_provider(
        {
            "protocol": PROTOCOL,
            "message_type": "CREATE_SESSION",
            "request_id": "t",
            "session_id": None,
            "payload": {},
        }
    )
    assert r["message_type"] == "ERROR"
    assert r["payload"]["code"] == "UNSUPPORTED_OPERATION"


def test_ws20_provider_has_no_ai_autoplay_or_choice_fallback_dependency():
    text = PROVIDER.read_text(encoding="utf-8")
    for forbidden in [
        "phase_ai",
        "auto_play",
        "random.choice",
        "first option",
        "default yes",
        "default no",
    ]:
        assert forbidden not in text.lower()


def test_ws20_card_domains_are_exactly_frozen():
    d = json.loads((ROOT / "qualification/manifests/ACTUAL_CARD_DOMAIN_v1.json").read_text())
    assert len(d["regression_corpus_29"]) == 29
    assert len(d["current_rogshai_unique_identity_list"]) == 87
    assert d["known_actual_card_universe"] == 1385


def test_ws17r_repairs_remain_present_on_ws20_restart():
    workflow = (ROOT / ".github/workflows/production-qualification.yml").read_text()
    assert "python -m pip install -e '.[dev]'" in workflow
    assert "Verify qualification runtime imports" in workflow
    assert "qualification/aggregate/runtime/SHA256SUMS'" in workflow
    assert (ROOT / "tests/qualification/test_ws17r_exact_main_runtime.py").is_file()
