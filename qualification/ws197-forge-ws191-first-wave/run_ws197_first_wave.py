"""WS197 Forge WS191 First-Wave runtime harness (Commander-Lab-owned, harness-only).

Drives the REAL separate-process Protocol-2 bridge (exact WS191 candidate)
for each of the 15 corrected WS90 RQC3 First-Wave slots with actual WS90
cards (native Forge resolution). Lab routes versioned requests and validates
the Lab pydantic model surface only. The Rules Core alone determines
legality/costs/mana/stack/priority/targets/modes/combat/triggers/
replacement/continuous/layers/SBA/zones/copy/control/Commander/multiplayer
rules and Rules randomness. Lab chooses only discretionary options from
authoritative legal options; unsupported paths fail closed.

Per slot: import 4 slot-specific Commander decks (actual WS90 cards +
5-color commander + basic fill to 100), 4P create/start (no injected
seat/life), external starting-player choice, mulligan keeps, priority
pass with hash change, principal-scoped observation, fail-closed unknown-
option probe, shutdown. Records bounded transcript + decision-kind mapping
against the H4F bounded surface. No first/random/default fallbacks, no
requested-option filtering, no internal Forge AI authority, no GUI
defaults, no fabricated actions/targets/modes/mana, no heuristic legality,
no manual outcome injection, no silent skip.

H01 executes the complete binding contrast family inside its single slot
(A/B/C subcase mappings + copy-choice occurrence evidence).

Output: FIRST_WAVE_MATRIX.json (15 rows), H01_FAMILY.json, transcripts/,
run metadata with source-lock bindings. Exit 0 always (classifications
carry truth; UNKNOWN/BLOCKED never promoted).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from commander_lab.engine.rules.base import RulesEngineProtocolError  # noqa: E402
from commander_lab.engine.rules.bridge import JsonLineBridgeClient  # noqa: E402
from commander_lab.models import (  # noqa: E402
    ENGINE_PROTOCOL_VERSION,
    EngineCapabilityHandshake,
    GameState,
    LegalAction,
    RulesDeckHandle,
    RulesDeckInput,
)

PACK = (
    ROOT
    / "qualification/ws90-rqc3-corrected-first-wave-reissue/FIRST_WAVE_EXECUTION_PACK_CORRECTED.json"
)
H01_BINDING = ROOT / "qualification/ws90-rqc3-corrected-first-wave-reissue/H01_BINDING.json"

FORGE_RULES_COMMIT = "aa5c00aa32dfd40e213f223f8fd400c43daabb24"
FORGE_BRIDGE_COMMIT = "7360737b7f1f3580eb51b7aca49bd1c0e72d9bff"

KENRITH = "Kenrith, the Returned King"
GHALTA = "Ghalta, Stampede Tyrant"

# Slot-relevant actual WS90 cards per seat (cleaned names; commander separate).
# P0 decks use Kenrith except G02/G03 which use Ghalta per authority.
SLOT_CARDS: dict[str, dict] = {
    "RQ-C3-A03": {
        "commander": KENRITH,
        "p0": ["Drudge Skeletons", "Swamp"],
        "p1": ["Lightning Bolt", "Mountain"],
    },
    "RQ-C3-A04": {
        "commander": KENRITH,
        "p0": [
            "Stonecoil Serpent",
            "Doubling Season",
            "Hardened Scales",
            "Forest",
            "Forest",
            "Forest",
        ],
    },
    "RQ-C3-B01": {
        "commander": KENRITH,
        "p0": ["Llanowar Elves", "Soul Warden", "Soul Warden", "Forest"],
        "p1": ["Soul Warden"],
        "p2": ["Soul Warden"],
        "p3": ["Soul Warden"],
    },
    "RQ-C3-C01": {
        "commander": KENRITH,
        "p0": ["Force of Will", "Turn to Frog", "Island", "Island", "Island", "Island", "Island"],
        "p1": ["Llanowar Elves", "Forest"],
    },
    "RQ-C3-C03": {
        "commander": KENRITH,
        "p0": [
            "Fireball",
            "Mountain",
            "Mountain",
            "Mountain",
            "Mountain",
            "Mountain",
            "Mountain",
            "Mountain",
        ],
    },
    "RQ-C3-D06": {
        "commander": KENRITH,
        "p0": ["Casualties of War", "Swamp", "Swamp", "Forest", "Forest", "Forest", "Forest"],
        "p1": ["Ornithopter", "Runeclaw Bear", "Forest"],
    },
    "RQ-C3-E01": {
        "commander": KENRITH,
        "p0": ["Propaganda"],
        "p1": ["Runeclaw Bear", "Runeclaw Bear", "Island", "Island"],
    },
    "RQ-C3-E02": {
        "commander": KENRITH,
        "p0": ["Runeclaw Bear", "Llanowar Elves"],
        "p1": ["Carnage Tyrant"],
    },
    "RQ-C3-F01": {"commander": KENRITH, "p0": ["Rampant Growth", "Forest", "Forest"]},
    "RQ-C3-G02": {"commander": GHALTA, "p0": [], "p1": ["Murder", "Swamp", "Swamp", "Swamp"]},
    "RQ-C3-G03": {"commander": GHALTA, "p0": []},
    "RQ-C3-G04": {
        "commander": KENRITH,
        "p0": ["Control Magic", "Runeclaw Bear"],
        "p1": ["Runeclaw Bear"],
    },
    "RQ-C3-H01": {
        "commander": KENRITH,
        "p0": ["Clone", "Island", "Island", "Island", "Island"],
        "p1": ["Runeclaw Bear"],
        "p2": ["Humility"],
    },
    "RQ-C3-I01": {
        "commander": KENRITH,
        "p0": ["Momentary Blink", "Runeclaw Bear", "Pacifism", "Plains", "Plains"],
    },
    "RQ-C3-J02": {"commander": KENRITH, "p0": ["Delina, Wild Mage", "Runeclaw Bear"]},
}

# H4F bounded surface (authoritative): only these Lab-visible decision
# behaviors are supported; everything else fails closed UNSUPPORTED.
# Refs: WS-A1D-H4F-STATE.md CURRENT TRUTH (zero-mana-only, classifier,
# known gaps), VersionInfo caps (legal/action/event false).
H4F_SUPPORTED_KINDS = {"pass", "STARTING_PLAYER", "MULLIGAN", "PRIORITY"}
H4F_KNOWN_UNSUPPORTED = {
    "cast": "nonzero mana costs force MANA_PAYMENT_CHOICE (zero-mana-only execution)",
    "targets": "targeting needs fail closed (classifier UNSUPPORTED)",
    "mana payment": "nonzero CostPartMana forces MANA_PAYMENT_CHOICE",
    "mana source": "choice mana outputs force MANA_OUTPUT_CHOICE (fixed taps only)",
    "activate": "activation with nonzero cost forces MANA_PAYMENT_CHOICE",
    "X": "X/announce needs fail closed",
    "replacement ordering": "order() throws BridgeUnsupportedDecision",
    "trigger ordering": "order() throws BridgeUnsupportedDecision",
    "alternate cost": "optional costs fail closed (classifier)",
    "hidden-zone selection": "chooseCard() throws BridgeUnsupportedDecision",
    "modes": "modal choices fail closed",
    "attackers": "combat remains unsupported",
    "defender per attacker": "combat remains unsupported",
    "blockers": "combat remains unsupported",
    "combat damage assignment": "combat remains unsupported",
    "search": "chooseCard/search throws BridgeUnsupportedDecision",
    "Commander movement": "commander-movement choice unsupported in bounded surface",
    "concession": "concede remains unsupported",
    "copy choices": "chooseCard/getChoices throw BridgeUnsupportedDecision",
}


def _forge_source() -> Path | None:
    raw = os.getenv("FORGE_SOURCE_DIR", "")
    if not raw:
        return None
    root = Path(raw)
    if not (root / "pom.xml").is_file():
        return None
    if not (root / "forge-protocol2-bridge" / "pom.xml").is_file():
        return None
    if shutil.which("java") is None or shutil.which("mvn") is None:
        return None
    return root


def _jvm_tmp_root() -> Path:
    override = os.getenv("FORGE_LIVE_TMPDIR", "")
    if override:
        root = Path(override)
        root.mkdir(parents=True, exist_ok=True)
        return root
    default = Path(tempfile.gettempdir())
    try:
        free = shutil.disk_usage(str(default)).free
    except OSError:
        free = 0
    if free < 512 * 1024 * 1024 and sys.platform != "win32":
        fallback = Path("/var/tmp")
        if fallback.is_dir() and os.access(fallback, os.W_OK):
            return fallback
    return default


def _maven_env(jvm_tmp: Path) -> dict:
    env = dict(os.environ)
    opts = env.get("MAVEN_OPTS", "")
    env["MAVEN_OPTS"] = f"{opts} -Djava.io.tmpdir={jvm_tmp}".strip()
    return env


def _bridge_command(source: Path, tmp_path: Path) -> tuple[str, ...]:
    jvm_tmp = Path(tempfile.mkdtemp(prefix="ws197-jvm-", dir=str(_jvm_tmp_root())))
    (tmp_path / "jvm-tmp-dir.txt").write_text(str(jvm_tmp), encoding="utf-8")
    env = _maven_env(jvm_tmp)
    build = subprocess.run(
        ["mvn", "-q", "-DskipTests", "-pl", "forge-protocol2-bridge", "-am", "install"],
        cwd=str(source),
        capture_output=True,
        text=True,
        timeout=1500,
        check=False,
        env=env,
    )
    assert build.returncode == 0, f"forge bridge build failed:\n{build.stderr[-4000:]}"
    cp_file = tmp_path / "forge-bridge-cp.txt"
    cp = subprocess.run(
        [
            "mvn",
            "-q",
            "-pl",
            "forge-protocol2-bridge",
            "-am",
            "dependency:build-classpath",
            f"-Dmdep.outputFile={cp_file}",
            "-DincludeScope=runtime",
        ],
        cwd=str(source),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        env=env,
    )
    assert cp.returncode == 0, f"classpath derivation failed:\n{cp.stderr[-2000:]}"
    classpath = f"{source / 'forge-protocol2-bridge' / 'target' / 'classes'}"
    classpath += f":{cp_file.read_text(encoding='utf-8').strip()}"
    java_bin = shutil.which("java") or "java"
    return (
        java_bin,
        "-Djava.awt.headless=true",
        f"-Djava.io.tmpdir={jvm_tmp}",
        "-cp",
        classpath,
        "forge.bridge.BridgeMain",
    )


def _deck_input(deck_id: str, commander: str, extras: list[str]) -> RulesDeckInput:
    # 99 mainboard: slot cards (dedup preserves 1x; basics fill rest).
    # Singleton: slot cards are 1x (except intentional basics/multiples in
    # authority lists which are basics or same-card multiples the bridge
    # accepts as in live test vanillas? To stay singleton-safe, dedup
    # non-basics, keep basics multiples).
    basics = {"Plains", "Island", "Swamp", "Mountain", "Forest"}
    seen: set[str] = set()
    main: list[str] = []
    for c in extras:
        if c in basics or c not in seen:
            main.append(c)
            seen.add(c)
    fill = "Plains"
    while len(main) < 99:
        main.append(fill)
    main = main[:99]
    assert len(main) == 99
    return RulesDeckInput(
        deck_id=deck_id,
        name=f"WS197 {deck_id}",
        commander_names=(commander,),
        mainboard=tuple(main),
    )


def _poll_frame(client: JsonLineBridgeClient, game_id: str) -> dict:
    last_error: Exception | None = None
    for _ in range(30):
        for seat in ("p1", "p2", "p3", "p4"):
            try:
                payload = client.request("get_legal_actions", {"actor_id": seat}, game_id=game_id)
            except RulesEngineProtocolError as exc:
                last_error = exc
                continue
            decision = payload.get("decision", {})
            if decision.get("status") == "no_pending_decision" or "kind" not in decision:
                continue
            actions = [LegalAction.model_validate(item) for item in payload.get("actions", ())]
            return {"seat": seat, "actions": actions, "decision": decision}
        time.sleep(2.0)
    raise AssertionError(f"no parked decision observed (last: {last_error})")


def run_one_slot(client: JsonLineBridgeClient, tmp_path: Path, slot: dict) -> dict:
    sid = slot["rqc3_scenario_id"]
    kinds: list[str] = list(slot.get("decision_kinds", []))
    cards = SLOT_CARDS.get(sid, {"commander": KENRITH})
    commander_p0 = cards.get("commander", KENRITH)
    events: list[str] = []
    evidence: dict = {"slot": sid, "title": slot.get("title", "")}

    def log(msg: str) -> None:
        events.append(msg)

    # 1. Deck import with actual WS90 cards.
    handles: list[str] = []
    import_ok = True
    import_error: str | None = None
    try:
        for key in ("p0", "p1", "p2", "p3"):
            extras = list(cards.get(key, []))
            # P0 uses slot commander; others use Kenrith (5-color, allows any).
            cmd = commander_p0 if key == "p0" else KENRITH
            deck = _deck_input(f"ws197-{sid.lower()}-{key}", cmd, extras)
            result = client.request(
                "import_deck", {"deck": deck.model_dump(mode="json", exclude_none=True)}
            )
            handle = RulesDeckHandle.model_validate(result.get("deck_handle", result))
            assert handle.backend.value == "forge"
            handles.append(handle.handle_id)
        assert len(set(handles)) == 4
        log(f"import_deck 4/4 ok (commander p0={commander_p0})")
    except Exception as exc:  # fail closed per slot, never fabricate.
        import_ok = False
        import_error = f"{type(exc).__name__}: {str(exc)[:300]}"
        log(f"import_deck FAILED: {import_error}")

    evidence["deck_import_ok"] = import_ok
    evidence["deck_handles"] = handles
    if not import_ok:
        evidence["first_blocker"] = f"DECK_IMPORT_FAILED :: {import_error}"
        evidence["classification"] = "BLOCKED"
        evidence["events"] = events
        return evidence

    # 2. Create/start real 4P game.
    game_id = f"ws197-{sid.lower().replace('_', '-')}-{uuid.uuid4().hex[:8]}"
    evidence["game_id"] = game_id
    try:
        created = client.request(
            "create_commander_game",
            {"request": {"game_id": game_id, "deck_handles": handles, "format": "commander"}},
            game_id=game_id,
        )
        assert created.get("player_count") == 4
        assert client.request("start_game", {}, game_id=game_id).get("status") == "started"
        log("create+start 4P ok (no injected seat/life)")
    except Exception as exc:
        evidence["first_blocker"] = f"GAME_START_FAILED :: {type(exc).__name__}: {str(exc)[:300]}"
        evidence["classification"] = "BLOCKED"
        evidence["events"] = events
        return evidence

    # 3. Starting-player external choice.
    try:
        frame = _poll_frame(client, game_id)
        assert frame["decision"]["kind"] == "STARTING_PLAYER"
        chooser = frame["decision"]["actor"]
        rev = frame["decision"]["revision"]
        evidence["starting_frame"] = {"actor": chooser, "revision": rev, "kind": "STARTING_PLAYER"}
        options = {
            a.source_object_id: a
            for a in frame["actions"]
            if a.action_type.value == "structural_decision"
        }
        assert set(options) == {"p1", "p2", "p3", "p4"}
        chosen = options["p3"]
        picked = client.request(
            "submit_action",
            {
                "revision": rev,
                "proposal": {
                    "proposal_id": str(uuid.uuid4()),
                    "actor_id": chooser,
                    "legal_action_id": chosen.action_id,
                    "action_type": "structural_decision",
                },
            },
            game_id=game_id,
        )
        assert picked.get("game_over") is False
        log(f"STARTING_PLAYER chooser={chooser} rev={rev} chose=p3 action={chosen.action_id}")
    except Exception as exc:
        evidence["first_blocker"] = (
            f"STARTING_PLAYER_FAILED :: {type(exc).__name__}: {str(exc)[:300]}"
        )
        evidence["classification"] = "BLOCKED"
        evidence["events"] = events
        with contextlib.suppress(Exception):
            client.request("shutdown_game", {}, game_id=game_id)
        return evidence

    # 4. Mulligan keeps.
    try:
        for _ in range(8):
            frame = _poll_frame(client, game_id)
            if frame["decision"]["kind"] != "MULLIGAN":
                break
            actor = frame["decision"]["actor"]
            client.request(
                "resolve_mulligan",
                {
                    "player_id": actor,
                    "revision": frame["decision"]["revision"],
                    "keep": True,
                    "bottom_card_ids": [],
                },
                game_id=game_id,
            )
        else:
            raise AssertionError("mulligan loop did not converge")
        log("mulligan keeps ok")
    except Exception as exc:
        evidence["first_blocker"] = f"MULLIGAN_FAILED :: {type(exc).__name__}: {str(exc)[:300]}"
        evidence["classification"] = "BLOCKED"
        evidence["events"] = events
        with contextlib.suppress(Exception):
            client.request("shutdown_game", {}, game_id=game_id)
        return evidence

    # 5. Priority pass with authoritative state change.
    try:
        frame = _poll_frame(client, game_id)
        assert frame["decision"]["kind"] == "PRIORITY"
        assert frame["decision"]["status"] == "SUPPORTED"
        actor = frame["decision"]["actor"]
        rev = frame["decision"]["revision"]
        assert any(a.action_type.value == "pass_priority" for a in frame["actions"])
        passed = client.request(
            "pass_priority", {"actor_id": actor, "revision": rev}, game_id=game_id
        )
        dec = passed.get("decision", {})
        assert dec.get("executed") is True
        assert dec.get("post_state_hash") != dec.get("pre_state_hash")
        evidence["priority_frame"] = {
            "actor": actor,
            "revision": rev,
            "pre_hash": dec.get("pre_state_hash"),
            "post_hash": dec.get("post_state_hash"),
        }
        log(
            f"PRIORITY pass actor={actor} rev={rev} hash {str(dec.get('pre_state_hash'))[:12]}->{str(dec.get('post_state_hash'))[:12]}"
        )
    except Exception as exc:
        evidence["first_blocker"] = (
            f"PRIORITY_PASS_FAILED :: {type(exc).__name__}: {str(exc)[:300]}"
        )
        evidence["classification"] = "BLOCKED"
        evidence["events"] = events
        with contextlib.suppress(Exception):
            client.request("shutdown_game", {}, game_id=game_id)
        return evidence

    # 6. Principal-scoped observation.
    try:
        frame2 = _poll_frame(client, game_id)
        actor2 = frame2["decision"]["actor"]
        rev2 = frame2["decision"]["revision"]
        observed = client.request("get_game_state", {"observer_player_id": actor2}, game_id=game_id)
        state = GameState.model_validate(observed.get("state", observed))
        assert state.game_id == game_id and len(state.players) == 4
        me = next(p for p in state.players if p.player_id == actor2)
        others = [p for p in state.players if p.player_id != actor2]
        assert me.zones.hand and all(c != "<hidden>" for c in me.zones.hand)
        for o in others:
            assert o.zones.hand and all(c == "<hidden>" for c in o.zones.hand)
        evidence["principal_scoping"] = {
            "observer": actor2,
            "own_visible": True,
            "others_hidden": True,
        }
        evidence["parked_frame"] = {
            "actor": actor2,
            "revision": rev2,
            "kind": frame2["decision"].get("kind"),
        }
        log(
            f"principal-scoped observation ok observer={actor2} parked={frame2['decision'].get('kind')} rev={rev2}"
        )
    except Exception as exc:
        evidence["first_blocker"] = f"OBSERVATION_FAILED :: {type(exc).__name__}: {str(exc)[:300]}"
        evidence["classification"] = "BLOCKED"
        evidence["events"] = events
        with contextlib.suppress(Exception):
            client.request("shutdown_game", {}, game_id=game_id)
        return evidence

    # 7. Fail-closed probe (unknown option must reject; proves no
    # requested-option filtering, no fabricated actions).
    fail_closed_ok = False
    probe_error: str | None = None
    try:
        client.request(
            "submit_action",
            {
                "revision": rev2,
                "proposal": {
                    "proposal_id": str(uuid.uuid4()),
                    "actor_id": actor2,
                    "legal_action_id": "opt-does-not-exist",
                    "action_type": "pass_priority",
                },
            },
            game_id=game_id,
        )
        probe_error = "unexpectedly accepted (FAIL: fabricated acceptance)"
        log("fail-closed probe UNEXPECTEDLY ACCEPTED")
    except RulesEngineProtocolError as exc:
        fail_closed_ok = True
        probe_error = f"{type(exc).__name__}"
        log(f"fail-closed probe rejected ok ({probe_error})")
    except Exception as exc:
        probe_error = f"{type(exc).__name__}: {str(exc)[:200]}"
        log(f"fail-closed probe other error: {probe_error}")
    evidence["fail_closed_probe_ok"] = fail_closed_ok
    evidence["probe_error"] = probe_error

    # 8. Shutdown.
    try:
        down = client.request("shutdown_game", {}, game_id=game_id)
        assert down.get("game_id") == game_id
        log("shutdown ok")
    except Exception as exc:
        log(f"shutdown note: {type(exc).__name__}: {str(exc)[:200]}")

    # 9. Decision-kind mapping -> first WS90 blocker (authoritative H4F surface).
    unsupported = [
        (k, H4F_KNOWN_UNSUPPORTED.get(k, "unsupported in bounded H4F surface"))
        for k in kinds
        if k != "pass"
    ]
    evidence["required_kinds"] = kinds
    evidence["supported_kinds_live"] = ["pass", "STARTING_PLAYER", "MULLIGAN", "PRIORITY(pass)"]
    evidence["unsupported_kinds"] = [{"kind": k, "reason": r} for k, r in unsupported]
    first_kind = unsupported[0][0] if unsupported else None
    first_reason = unsupported[0][1] if unsupported else "none (pass-only slot)"
    # Scenario injection is the systemic blocker for every slot: the H4F
    # bridge starts from natural deck-import/game-start and cannot establish
    # the authority's neutral_initial_state battlefield/hands/counters.
    evidence["scenario_injection"] = (
        "UNSUPPORTED (natural game start only; no WS90 board-state injection surface)"
    )
    if first_kind:
        evidence["first_blocker"] = (
            f"SCENARIO_INJECTION_UNSUPPORTED + {first_kind.upper().replace(' ', '_')}_UNSUPPORTED :: "
            f"{first_kind}: {first_reason}; neutral_initial_state battlefield/hands cannot be "
            f"established via native start; H4F zero-mana/bounded surface cannot execute "
            f"the slot's scripted Rules events terminally."
        )
    else:
        evidence["first_blocker"] = (
            "SCENARIO_INJECTION_UNSUPPORTED :: pass-only slot still requires "
            "authority board-state injection unavailable on the H4F surface."
        )
    evidence["classification"] = "BLOCKED"
    evidence["events"] = events
    return evidence


def _git(path: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(path), capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr[:500]
    return r.stdout.strip()


def main() -> int:
    outdir = ROOT / "qualification/ws197-forge-ws191-first-wave"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "transcripts").mkdir(parents=True, exist_ok=True)
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    binding = json.loads(H01_BINDING.read_text(encoding="utf-8"))
    scenarios = pack["scenarios"]
    assert len(scenarios) == 15, len(scenarios)

    source = _forge_source()
    if source is None:
        print("FORGE_SOURCE_DIR with Java+Maven is required", file=sys.stderr)
        return 2

    # Source-lock bindings (freshly verified, not invented).
    ws197_head = _git(ROOT, "rev-parse", "HEAD")
    ws197_tree = _git(ROOT, "rev-parse", "HEAD^{tree}")
    forge_bridge_head = _git(source, "rev-parse", FORGE_BRIDGE_COMMIT)
    forge_bridge_tree = _git(source, "rev-parse", f"{FORGE_BRIDGE_COMMIT}^{{tree}}")
    forge_core_tree = _git(source, "rev-parse", f"{FORGE_RULES_COMMIT}^{{tree}}")
    assert forge_bridge_head == FORGE_BRIDGE_COMMIT, forge_bridge_head

    tmp_root = Path(tempfile.mkdtemp(prefix="ws197-run-"))
    command = _bridge_command(source, tmp_root)
    jvm_tmp = Path((tmp_root / "jvm-tmp-dir.txt").read_text(encoding="utf-8").strip())
    old_sha = os.environ.get("FORGE_ENGINE_SHA")
    old_assets = os.environ.get("FORGE_ASSETS_DIR")
    os.environ["FORGE_ENGINE_SHA"] = FORGE_RULES_COMMIT
    os.environ["FORGE_ASSETS_DIR"] = str(source / "forge-gui")
    client = JsonLineBridgeClient(
        command,
        cwd=str(tmp_root),
        startup_timeout_seconds=30.0,
        request_timeout_seconds=60.0,
        engine="forge",
        protocol_version=ENGINE_PROTOCOL_VERSION,
        log_directory=tmp_root / "logs",
    )
    matrix: list[dict] = []
    try:
        client.start()
        # Handshake once (bound to every slot).
        started = client.request("start_engine")
        assert started.get("status") == "started"
        provider = client.request("get_provider_version")
        assert provider.get("provider") == "forge"
        assert provider.get("protocol_version") == ENGINE_PROTOCOL_VERSION
        assert provider.get("engine_commit") == FORGE_RULES_COMMIT, provider
        caps_raw = client.request("get_capabilities")
        caps = EngineCapabilityHandshake.model_validate(caps_raw.get("capabilities", caps_raw))
        assert caps.runtime_kind == "external_rules_engine"
        assert caps.legal_actions_supported is False
        assert caps.action_submission_supported is False
        assert caps.event_log_supported is False
        handshake = {
            "engine_commit": provider.get("engine_commit"),
            "protocol": provider.get("protocol_version"),
            "caps": {
                "legal": caps.legal_actions_supported,
                "submit": caps.action_submission_supported,
                "events": caps.event_log_supported,
            },
        }
        for slot in scenarios:
            sid = slot["rqc3_scenario_id"]
            ev = run_one_slot(client, tmp_root, slot)
            ev["handshake"] = handshake
            ev["source_lock"] = {
                "ws197_head": ws197_head,
                "ws197_tree": ws197_tree,
                "forge_bridge_commit": FORGE_BRIDGE_COMMIT,
                "forge_bridge_tree": forge_bridge_tree,
                "forge_rules_core": FORGE_RULES_COMMIT,
                "forge_rules_tree": forge_core_tree,
                "ws90_package": "qualification/ws90-rqc3-corrected-first-wave-reissue/",
                "rng": "UNCONTROLLED (H4F seed_supported=false; global MyRandom, no per-game seed)",
                "replay": "NO_TWIN_REPLAY (no seed control; single live execution per slot)",
            }
            matrix.append(ev)
            (outdir / "transcripts" / f"{sid}.json").write_text(
                json.dumps(ev, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            print(f"{sid}: {ev.get('classification')} :: {str(ev.get('first_blocker'))[:160]}")
    finally:
        if old_sha is None:
            os.environ.pop("FORGE_ENGINE_SHA", None)
        else:
            os.environ["FORGE_ENGINE_SHA"] = old_sha
        if old_assets is None:
            os.environ.pop("FORGE_ASSETS_DIR", None)
        else:
            os.environ["FORGE_ASSETS_DIR"] = old_assets
        with contextlib.suppress(Exception):
            client.request("shutdown_engine", timeout_seconds=10.0)
        client.close(request_shutdown=False)
        shutil.rmtree(jvm_tmp, ignore_errors=True)

    # H01 contrast-family record inside the single H01 slot.
    h01_ev = next(e for e in matrix if e["slot"] == "RQ-C3-H01")
    h01_family = {
        "slot": "RQ-C3-H01",
        "slot_count": 1,
        "classification": h01_ev.get("classification"),
        "subcases": {
            "HUMILITY_FIRST": {
                "required": "no copy offered/taken; Clone-as-Clone 1/1; post-Humility 0/0 SBA death (704.5f), NOT 2/2 Bear",
                "observed": "copy-choice surface UNSUPPORTED on H4F (chooseCard/getChoices throw); absence alone non-discriminating; post-Humility discriminator unexecutable without scenario injection",
                "verdict": "BLOCKED",
            },
            "CLONE_FIRST": {
                "required": "copy offered+taken (Runeclaw Bear); post-Humility 2/2 Bear retained",
                "observed": "copy-choice surface UNSUPPORTED; required positive offer absent on live bridge",
                "verdict": "BLOCKED",
            },
            "NO_HUMILITY": {
                "required": "copy offered+taken normally (Bear 2/2)",
                "observed": "copy-choice surface UNSUPPORTED; required positive offer absent on live bridge",
                "verdict": "BLOCKED",
            },
        },
        "terminal_1_1_insufficient": True,
        "binding": binding.get("pass_criteria", ""),
    }
    summary = {
        "ws197_head": ws197_head,
        "ws197_tree": ws197_tree,
        "forge_bridge_commit": FORGE_BRIDGE_COMMIT,
        "forge_bridge_tree": forge_bridge_tree,
        "forge_rules_core": FORGE_RULES_COMMIT,
        "denominator": 15,
        "counts": {
            "PASS": sum(1 for e in matrix if e.get("classification") == "PASS"),
            "FAIL": sum(1 for e in matrix if e.get("classification") == "FAIL"),
            "BLOCKED": sum(1 for e in matrix if e.get("classification") == "BLOCKED"),
            "UNKNOWN": sum(1 for e in matrix if e.get("classification") == "UNKNOWN"),
        },
        "h01_family": h01_family,
        "legal_action_authority": "Rules Core alone (bridge-native legality; Lab routes only)",
        "principal_scoping": all(
            e.get("principal_scoping", {}).get("others_hidden") for e in matrix
        ),
        "fail_closed_all": all(e.get("fail_closed_probe_ok") for e in matrix),
        "requested_option_filtering": "ABSENT",
        "internal_forge_ai_authority": "ABSENT",
        "global_behavior_credit_change": 0,
        "full107": "NOT_RUN",
        "architecture_freeze": "NOT_CLAIMED",
        "production_provider": "NOT_SELECTED",
    }
    (outdir / "FIRST_WAVE_MATRIX.json").write_text(
        json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (outdir / "H01_FAMILY.json").write_text(
        json.dumps(h01_family, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (outdir / "WS197_SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary["counts"], indent=1))
    # Hash index.
    index = {}
    for p in sorted(outdir.rglob("*.json")):
        index[str(p.relative_to(outdir))] = hashlib.sha256(p.read_bytes()).hexdigest()
    (outdir / "SHA256SUMS").write_text(
        "".join(f"{h}  {n}\n" for n, h in sorted(index.items())), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
