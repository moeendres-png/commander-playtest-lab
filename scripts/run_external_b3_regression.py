#!/usr/bin/env python3
"""Fail-closed real XMage B3 regression through the Java JSONL process bridge.

This validates only already-proven B3 behavior. It must not be interpreted as
legal-action, action-submission, event-log, replay, mulligan, or production
provider evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "artifacts" / "external-engine"
RULES_PATH = ROOT / "config" / "rules_engines.json"
DECK_PATH = ROOT / "data" / "decks" / "rogshai_current.json"
PROTOCOL_VERSION = "2.0.0"

B3_TRUE = (
    "commander_supported",
    "partner_supported",
    "multiplayer_supported",
    "headless_supported",
    "deck_import_supported",
    "engine_shutdown_supported",
)
POST_B3_FALSE = (
    "seed_supported",
    "mulligan_supported",
    "legal_actions_supported",
    "action_submission_supported",
    "event_log_supported",
    "replay_supported",
    "stack_visible",
    "priority_visible",
    "target_selection_supported",
    "mode_selection_supported",
    "trigger_order_supported",
    "concede_supported",
    "game_shutdown_supported",
)


class RegressionError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_head(path: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def envelope(
    request_id: str,
    method: str,
    payload: dict[str, Any] | None = None,
    *,
    game_id: str | None = None,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": request_id,
        "engine": "xmage",
        "message_type": method,
        "method": method,
        "payload": payload or {},
        "params": {},
    }
    if game_id is not None:
        request["game_id"] = game_id
    return request


class BridgeProcess:
    def __init__(self, command: str) -> None:
        argv = shlex.split(command)
        if not argv:
            raise RegressionError("COMMANDER_LAB_XMAGE_BRIDGE_CMD is empty")
        self.process = subprocess.Popen(
            argv,
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        if self.process.stdin is None or self.process.stdout is None:
            raise RegressionError("failed to open bridge stdio")

    def call(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.process.poll() is not None:
            raise RegressionError(f"bridge exited early: {self.process.returncode}")
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        self.process.stdin.write(json.dumps(request, sort_keys=True) + "\n")
        self.process.stdin.flush()
        raw = self.process.stdout.readline()
        if not raw:
            raise RegressionError(f"bridge produced no response: {self.process.poll()}")
        try:
            response = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RegressionError(f"bridge stdout was not JSONL: {raw[:200]!r}") from exc
        if response.get("request_id") != request["request_id"]:
            raise RegressionError("bridge response request_id mismatch")
        if response.get("success") is not True:
            raise RegressionError(f"bridge request failed: {json.dumps(response, sort_keys=True)}")
        payload = response.get("payload")
        if not isinstance(payload, dict):
            raise RegressionError("bridge response payload is not an object")
        return payload

    def shutdown(self) -> None:
        payload = self.call(envelope("shutdown", "shutdown_engine"))
        if payload.get("shutdown") is not True:
            raise RegressionError("bridge did not acknowledge shutdown")
        try:
            self.process.wait(timeout=30)
        except subprocess.TimeoutExpired as exc:
            self.process.kill()
            self.process.wait(timeout=5)
            raise RegressionError("bridge did not exit after shutdown") from exc
        if self.process.returncode != 0:
            raise RegressionError(f"bridge exited non-zero: {self.process.returncode}")

    def abort(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=5)


def load_deck() -> tuple[dict[str, Any], str]:
    source = json.loads(DECK_PATH.read_text(encoding="utf-8"))
    if source.get("deck_id") != "rogshai/current":
        raise RegressionError("B3 regression source is not rogshai/current")
    mainboard: list[str] = []
    commanders: list[str] = []
    cards = source.get("cards")
    if not isinstance(cards, list):
        raise RegressionError("RogShai source lost cards array")
    for row in cards:
        if not isinstance(row, dict):
            raise RegressionError("RogShai card row is not an object")
        name = row.get("oracle_name")
        quantity = row.get("quantity")
        zone = row.get("zone")
        if not isinstance(name, str) or not name:
            raise RegressionError("invalid oracle_name in RogShai source")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
            raise RegressionError(f"invalid quantity for {name}")
        if zone == "main":
            mainboard.extend([name] * quantity)
        elif zone == "commander":
            commanders.extend([name] * quantity)
        else:
            raise RegressionError(f"unexpected RogShai zone: {zone!r}")
    if len(mainboard) != 98 or len(commanders) != 2:
        raise RegressionError(
            f"expected 98 main + 2 commanders; got {len(mainboard)} + {len(commanders)}"
        )
    deck_hash = source.get("deck_hash")
    if not isinstance(deck_hash, str) or len(deck_hash) != 64:
        raise RegressionError("RogShai source lost 64-character deck_hash")
    return (
        {
            "deck_id": "rogshai/current",
            "name": source.get("name"),
            "deck_hash": deck_hash,
            "mainboard": mainboard,
            "commander_names": commanders,
            "sideboard": [],
        },
        deck_hash,
    )


def validate_capabilities(capabilities: dict[str, Any]) -> None:
    if capabilities.get("runtime_kind") != "external_rules_engine":
        raise RegressionError("bridge lost external_rules_engine runtime kind")
    if capabilities.get("max_players") != 5:
        raise RegressionError("bridge max_players drifted from B3=5")
    for key in B3_TRUE:
        if capabilities.get(key) is not True:
            raise RegressionError(f"B3 capability unavailable: {key}")
    for key in POST_B3_FALSE:
        if capabilities.get(key) is not False:
            raise RegressionError(f"unproven post-B3 capability became true: {key}")


def run_real_process_smoke(command: str, xmage_commit: str) -> tuple[dict[str, Any], dict[str, Any]]:
    deck, deck_hash = load_deck()
    bridge = BridgeProcess(command)
    try:
        version = bridge.call(envelope("version", "get_provider_version"))
        if version.get("engine") != "xmage" or version.get("engine_commit") != xmage_commit:
            raise RegressionError("running XMage provider does not match pinned source")
        if version.get("protocol_version") != PROTOCOL_VERSION:
            raise RegressionError("bridge protocol version drifted")

        capability_payload = bridge.call(envelope("capabilities", "get_capabilities"))
        capabilities = capability_payload.get("capabilities")
        if not isinstance(capabilities, dict):
            raise RegressionError("capabilities payload is missing")
        validate_capabilities(capabilities)

        handles: list[str] = []
        for seat in range(4):
            imported = bridge.call(
                envelope(f"import-{seat}", "import_deck", {"deck": deck})
            )
            handle = imported.get("deck_handle")
            if not isinstance(handle, dict):
                raise RegressionError("deck import did not return deck_handle")
            if handle.get("backend") != "xmage" or handle.get("deck_hash") != deck_hash:
                raise RegressionError("deck import identity mismatch")
            if handle.get("accepted_cards") != 100:
                raise RegressionError("XMage did not accept exactly 100 cards")
            if handle.get("rejected_cards") != [] or handle.get("warnings") != []:
                raise RegressionError("XMage deck import produced rejection/warning")
            handle_id = handle.get("handle_id")
            if not isinstance(handle_id, str) or not handle_id.startswith("xmage-deck-"):
                raise RegressionError("invalid XMage deck handle")
            handles.append(handle_id)

        game_id = "b3-regression/four-player"
        created = bridge.call(
            envelope(
                "create",
                "create_commander_game",
                {
                    "request": {
                        "game_id": game_id,
                        "deck_handles": handles,
                        "format": "commander",
                        "seed": None,
                        "starting_player_seat": 0,
                        "starting_life": 40,
                        "deterministic_starting_state": None,
                    }
                },
                game_id=game_id,
            )
        )
        if created.get("game_id") != game_id or created.get("player_count") != 4:
            raise RegressionError("real four-player Commander construction failed")
        game_handle = created.get("game_handle")
        engine_game_id = created.get("engine_game_id")
        if not isinstance(game_handle, str) or not game_handle.startswith("xmage-game-"):
            raise RegressionError("game construction lost process-local handle")
        if not isinstance(engine_game_id, str) or not engine_game_id:
            raise RegressionError("game construction lost real engine_game_id")

        started = bridge.call(envelope("start", "start_game", {}, game_id=game_id))
        if started.get("game_handle") != game_handle or started.get("engine_game_id") != engine_game_id:
            raise RegressionError("game identity changed between create and start")
        if started.get("player_count") != 4 or started.get("turn_number") != 1:
            raise RegressionError("B3 game did not reach the bounded turn-1 handoff")
        if started.get("paused") is not True:
            raise RegressionError("B3 game was not paused at the bounded start handoff")

        scenario = {
            "pod_size": 4,
            "deck_imports": 4,
            "accepted_cards_per_deck": 100,
            "game_id": game_id,
            "game_handle": game_handle,
            "engine_game_id": engine_game_id,
            "turn_number": 1,
            "paused": True,
            "external_engine_execution": True,
        }
        return scenario, capabilities
    finally:
        try:
            bridge.shutdown()
        except Exception:
            bridge.abort()
            raise


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    command = os.environ.get("COMMANDER_LAB_XMAGE_BRIDGE_CMD", "").strip()
    bridge_jar_raw = os.environ.get("COMMANDER_LAB_XMAGE_BRIDGE_JAR", "").strip()
    xmage_commit = os.environ.get("XMAGE_COMMIT", "").strip()
    if not command or not bridge_jar_raw:
        raise RegressionError("real XMage bridge command/JAR environment is required")
    if len(xmage_commit) != 40 or any(ch not in "0123456789abcdef" for ch in xmage_commit):
        raise RegressionError("XMAGE_COMMIT must be exactly 40 lowercase hex characters")

    bridge_jar = Path(bridge_jar_raw).resolve()
    if not bridge_jar.is_file():
        raise RegressionError(f"bridge JAR not found: {bridge_jar}")

    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    primary = rules.get("primary_engine")
    runtime = rules.get("current_runtime")
    if not isinstance(primary, dict) or not isinstance(runtime, dict):
        raise RegressionError("rules engine config lost current provider/runtime objects")
    if primary.get("provider") != "xmage" or primary.get("commit") != xmage_commit:
        raise RegressionError("workflow XMage commit does not match current pinned provider")
    if primary.get("production_ready") is not False:
        raise RegressionError("B3 regression cannot run under production_ready=true")
    if rules.get("provider_decision") != "NO_PROVIDER_READY":
        raise RegressionError("NO_PROVIDER_READY boundary was unexpectedly removed")
    if runtime.get("provider_selected") is not False:
        raise RegressionError("B3 regression must not select a production provider")

    vendor_root = ROOT / "vendor" / "engine-source" / "xmage"
    if git_head(vendor_root) != xmage_commit:
        raise RegressionError("checked-out XMage source does not match XMAGE_COMMIT")

    _, deck_hash = load_deck()
    lab_head = git_head(ROOT)
    identity = {
        "schema_version": 1,
        "scope": "b3_external_regression_identity",
        "evidence_class": "external_rules_engine",
        "lab_commit": lab_head,
        "xmage_commit": xmage_commit,
        "protocol_version": PROTOCOL_VERSION,
        "bridge_jar_sha256": sha256_file(bridge_jar),
        "bridge_command_sha256": sha256_bytes(command.encode("utf-8")),
        "rules_engine_config_sha256": sha256_file(RULES_PATH),
        "deck_source": "data/decks/rogshai_current.json",
        "deck_source_sha256": sha256_file(DECK_PATH),
        "deck_id": "rogshai/current",
        "deck_hash": deck_hash,
        "provider_decision": "NO_PROVIDER_READY",
        "production_ready": False,
    }
    identity_path = ARTIFACT_DIR / "B3_RUNTIME_IDENTITY.json"
    write_json(identity_path, identity)

    scenario, capabilities = run_real_process_smoke(command, xmage_commit)
    result = {
        "schema_version": 1,
        "status": "PASS",
        "scope": "b3_regression_only",
        "evidence_class": "external_rules_engine",
        "runtime_identity_sha256": sha256_file(identity_path),
        "provider_decision": "NO_PROVIDER_READY",
        "production_ready": False,
        "canonical_mutation_performed": False,
        "tactical_oracle_substitution": False,
        "validated_b3_boundary": {
            "real_deck_import": True,
            "commander_partner": True,
            "four_player_game_construction": True,
            "game_start_to_bounded_turn_1_handoff": True,
            "engine_process_shutdown": True,
        },
        "post_b3_capabilities_claimed": False,
        "capabilities": capabilities,
        "scenario": scenario,
    }
    result_path = ARTIFACT_DIR / "B3_REGRESSION.json"
    write_json(result_path, result)

    print("B3_EXTERNAL_REGRESSION=PASS")
    print(f"LAB_COMMIT={lab_head}")
    print(f"XMAGE_COMMIT={xmage_commit}")
    print("NO_PROVIDER_READY=true")
    print("PRODUCTION_READY=false")
    print(f"RUNTIME_IDENTITY_SHA256={sha256_file(identity_path)}")
    print(f"B3_REGRESSION_SHA256={sha256_file(result_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
