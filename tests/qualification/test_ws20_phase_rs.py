import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROVIDER = ROOT / "qualification/providers/phase_rs/ws10r_provider.py"
PROTOCOL = "commander-lab.rules-service/1.1.0"


def call_provider(request, env=None):
    cp = subprocess.run(
        [sys.executable, str(PROVIDER)],
        input=json.dumps(request) + "\n",
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    return json.loads(cp.stdout.strip())


def test_ws20_source_lock_is_exact():
    lock = json.loads(
        (ROOT / "qualification/providers/phase_rs/PINNED_SOURCE.json").read_text()
    )
    assert lock["upstream_commit"] == "bc218c51cec9cc2cec56f5c4de7c72be3d8e331c"
    assert lock["upstream_tree"] == "6e3f70d7de25c1f28919b73b2ee32654ee866ac0"
    assert lock["ws15_commit"] == "92c67b872c2a7f69c4a2069f0d0c3cb1b6b0d4c6"
    assert lock["ws15_to_fresh_ahead"] == 7
    assert lock["ws15_to_fresh_behind"] == 0


def test_ws20_provider_handshake_is_truthful_and_nonproduction():
    r = call_provider(
        {
            "protocol": PROTOCOL,
            "message_type": "HANDSHAKE",
            "request_id": "t",
            "session_id": None,
            "payload": {},
        }
    )
    assert r["message_type"] == "HANDSHAKE_RESULT"
    assert r["payload"]["production_capable"] is False
    assert r["payload"]["native_action_authority"].endswith("GameAction")
    assert r["payload"]["unsupported_policy"] == "fail-closed"


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


def test_ws20_provider_has_no_ai_or_autoplay_dependency():
    text = PROVIDER.read_text(encoding="utf-8")
    assert "phase_ai" not in text
    assert "auto_play" not in text
    assert "random.choice" not in text


def test_ws20_card_domains_are_exactly_frozen():
    d = json.loads((ROOT / "qualification/manifests/ACTUAL_CARD_DOMAIN_v1.json").read_text())
    assert len(d["regression_corpus_29"]) == 29
    assert len(d["current_rogshai_unique_identity_list"]) == 87
    assert d["known_actual_card_universe"] == 1385
