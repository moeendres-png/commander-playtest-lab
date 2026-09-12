"""Live Lab <-> qualified Forge Protocol-2 bridge integration (bounded H4F proof).

Drives the REAL Forge bridge process (built from an operator-supplied Forge
source checkout) through the GENERIC Lab JSONL transport
(``JsonLineBridgeClient``) — no second client, no duplicated rules logic, no
mocks. The bridge performs all legality, cost and state transitions; Lab only
routes versioned requests and validates the Lab pydantic model surface.

Bounded scope (mirrors the qualified H4F surface, never global capabilities):
handshake, provider identity, conservative capabilities, real deck import,
4-player Commander creation/start, external starting-player choice, mulligan
keeps, priority handoff with actor+revision binding, one external pass with
authoritative state change, principal-scoped observation, fail-closed
unsupported submission, clean shutdown.

Explicitly NOT covered here (documented adapter gaps for a later Lab
workstream): the high-level ``ExternalRulesAdapter`` convenience methods that
assume legacy capability flags (``get_legal_actions``/``submit_action`` require
``legal_actions_supported``/``action_submission_supported``),
revision plumbing in adapter proposals, ``resolve_mulligan`` capability gating,
and ``RulesGameRequest`` default seat/life fields (the hardened bridge rejects
injected seat/life). Those paths raise before touching the wire.

Requires:
  FORGE_SOURCE_DIR -- checkout of moeendres-png/forge containing the qualified
    forge-protocol2-bridge module (read-only use; the test only runs Maven
    package/classpath derivation and launches the bridge JVM);
  Java 17+ and Maven on PATH (for the module build + classpath).

Skipped (NOT_RUN) when unavailable. Never fabricates runtime evidence.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

from commander_lab.engine.rules.base import RulesEngineProtocolError
from commander_lab.engine.rules.bridge import JsonLineBridgeClient
from commander_lab.models import (
    ENGINE_PROTOCOL_VERSION,
    EngineCapabilityHandshake,
    GameState,
    LegalAction,
    RulesDeckHandle,
    RulesDeckInput,
)

pytestmark = pytest.mark.external

FORGE_RULES_COMMIT = "a37a865a53280dd8ad6fad3384d69611e8c5a42f"

# Bounded H4F-style fixture data (card NAMES only; the bridge resolves them
# against real Forge card data and rejects unknown names explicitly).
_COMMANDER = "Isamaru, Hound of Konda"
_VANILLAS = [
    "Silvercoat Lion",
    "Grizzly Bears",
    "Savannah Lions",
    "Elite Vanguard",
    "Eager Cadet",
    "Memnite",
    "Ornithopter",
    "Serra Angel",
    "Suntail Hawk",
    "Trained Caracal",
    "Valiant Guard",
    "Volunteer Militia",
]
_PLAINS = "Plains"


def _deck_input(deck_id: str) -> RulesDeckInput:
    mainboard = tuple(_VANILLAS + [_PLAINS] * (99 - len(_VANILLAS)))
    assert len(mainboard) == 99
    return RulesDeckInput(
        deck_id=deck_id,
        name=f"H4F Lab {deck_id}",
        commander_names=(_COMMANDER,),
        mainboard=mainboard,
    )


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
    """Writable JVM temp root: some runners have a full /tmp (hsperfdata needs it)."""
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
    """Build the bridge module (installing siblings) and return its launch vector.

    All Maven invocations run from the source root (never the module directory)
    so the repository ``.mvn/maven.config`` settings resolve. JVM temp is
    redirected off tiny/full tmpfs mounts when necessary. The JVM temp dir lives
    under ``_jvm_tmp_root()`` (not pytest tmp, which may itself be on tmpfs) and
    is removed by the fixture teardown.
    """
    jvm_tmp = Path(tempfile.mkdtemp(prefix="forge-live-jvm-", dir=str(_jvm_tmp_root())))
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
    cp_file = tmp_path / "forge-bridge-cp.txt"
    cp = subprocess.run(
        [
            "mvn",
            "-q",
            "dependency:build-classpath",
            f"-Dmdep.outputFile={cp_file}",
            "-DincludeScope=runtime",
        ],
        cwd=str(source / "forge-protocol2-bridge"),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert cp.returncode == 0, f"classpath derivation failed:\n{cp.stderr[-2000:]}"
    classpath = f"{source / 'forge-protocol2-bridge' / 'target' / 'classes'}"
    classpath += f":{cp_file.read_text(encoding='utf-8').strip()}"
    java_bin = shutil.which("java") or "java"
    return (
        java_bin,
        "-Djava.awt.headless=true",
        "-cp",
        classpath,
        "forge.bridge.BridgeMain",
    )


@pytest.fixture(scope="module")
def live_bridge(tmp_path_factory):
    source = _forge_source()
    if source is None:
        pytest.skip("FORGE_SOURCE_DIR with Java+Maven is required for the live Forge test")
    tmp_path = tmp_path_factory.mktemp("forge-live")
    command = _bridge_command(source, tmp_path)
    jvm_tmp = Path((tmp_path / "jvm-tmp-dir.txt").read_text(encoding="utf-8").strip())
    # The bridge JVM inherits these two operator-supplied bindings; the Rules
    # SHA is the audited H4F Rules-Core pin, the assets dir is the same source.
    old_sha = os.environ.get("FORGE_ENGINE_SHA")
    old_assets = os.environ.get("FORGE_ASSETS_DIR")
    os.environ["FORGE_ENGINE_SHA"] = FORGE_RULES_COMMIT
    os.environ["FORGE_ASSETS_DIR"] = str(source / "forge-gui")
    client = JsonLineBridgeClient(
        command,
        cwd=str(tmp_path),
        startup_timeout_seconds=30.0,
        request_timeout_seconds=60.0,
        engine="forge",
        protocol_version=ENGINE_PROTOCOL_VERSION,
        log_directory=tmp_path / "logs",
    )
    try:
        client.start()
        yield client
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


def _poll_frame(client: JsonLineBridgeClient, game_id: str) -> dict:
    """Return the first parked decision across seats (actor discovery by trial)."""
    import time

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


def test_live_forge_h4f_bounded_runtime(live_bridge) -> None:
    client = live_bridge

    # 1. Handshake: engine + truthful identity + conservative capabilities.
    started = client.request("start_engine")
    assert started.get("status") == "started"
    provider = client.request("get_provider_version")
    assert provider.get("provider") == "forge"
    assert provider.get("protocol_version") == ENGINE_PROTOCOL_VERSION
    assert provider.get("engine_commit") == FORGE_RULES_COMMIT
    caps_raw = client.request("get_capabilities")
    caps = EngineCapabilityHandshake.model_validate(caps_raw.get("capabilities", caps_raw))
    assert caps.runtime_kind == "external_rules_engine"
    assert caps.commander_supported and caps.multiplayer_supported
    assert caps.deck_import_supported and caps.headless_supported
    # Global bounded flags stay false (truthful DEGRADED basis for healthcheck).
    assert caps.legal_actions_supported is False
    assert caps.action_submission_supported is False
    assert caps.event_log_supported is False

    # 2. Real deck import (Lab model validation + engine resolution).
    handles: list[str] = []
    for index in range(1, 5):
        deck = _deck_input(f"h4f-lab-{index}")
        assert len(deck.mainboard) + len(deck.commander_names) == 100
        result = client.request(
            "import_deck", {"deck": deck.model_dump(mode="json", exclude_none=True)}
        )
        handle = RulesDeckHandle.model_validate(result.get("deck_handle", result))
        assert handle.backend.value == "forge"
        handles.append(handle.handle_id)
    assert len(set(handles)) == 4

    # 3. Four-player Commander creation + start (no injected seat/life).
    game_id = f"h4f-lab-{uuid.uuid4().hex[:8]}"
    created = client.request(
        "create_commander_game",
        {"request": {"game_id": game_id, "deck_handles": handles, "format": "commander"}},
        game_id=game_id,
    )
    assert created.get("player_count") == 4
    assert [seat["player_id"] for seat in created.get("seats", [])] == ["p1", "p2", "p3", "p4"]
    assert client.request("start_game", {}, game_id=game_id).get("status") == "started"

    # 4. External starting-player choice for Forge's selected chooser.
    frame = _poll_frame(client, game_id)
    assert frame["decision"]["kind"] == "STARTING_PLAYER"
    chooser = frame["decision"]["actor"]
    options = {
        action.source_object_id: action
        for action in frame["actions"]
        if action.action_type.value == "structural_decision"
    }
    assert set(options) == {"p1", "p2", "p3", "p4"}
    chosen = options["p3"]
    picked = client.request(
        "submit_action",
        {
            "revision": frame["decision"]["revision"],
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

    # 5. Mulligan keeps for every parked player.
    for _ in range(8):
        frame = _poll_frame(client, game_id)
        if frame["decision"]["kind"] != "MULLIGAN":
            break
        actor = frame["decision"]["actor"]
        answered = client.request(
            "resolve_mulligan",
            {
                "player_id": actor,
                "revision": frame["decision"]["revision"],
                "keep": True,
                "bottom_card_ids": [],
            },
            game_id=game_id,
        )
        assert answered is not None
    else:
        raise AssertionError("mulligan loop did not converge")

    # 6. Priority handoff with actor+revision binding + one external pass.
    frame = _poll_frame(client, game_id)
    assert frame["decision"]["kind"] == "PRIORITY"
    assert frame["decision"]["status"] == "SUPPORTED"
    actor = frame["decision"]["actor"]
    revision = frame["decision"]["revision"]
    assert frame["actions"], "SUPPORTED priority must offer options"
    assert any(a.action_type.value == "pass_priority" for a in frame["actions"])
    passed = client.request(
        "pass_priority", {"actor_id": actor, "revision": revision}, game_id=game_id
    )
    decision = passed.get("decision", {})
    assert decision.get("executed") is True
    assert decision.get("post_state_hash") != decision.get("pre_state_hash")

    # 7. Principal-scoped observation through the Lab GameState model.
    frame = _poll_frame(client, game_id)
    actor = frame["decision"]["actor"]
    observed = client.request("get_game_state", {"observer_player_id": actor}, game_id=game_id)
    state = GameState.model_validate(observed.get("state", observed))
    assert state.game_id == game_id
    assert len(state.players) == 4
    assert all(player.life == 40 for player in state.players)
    me = next(p for p in state.players if p.player_id == actor)
    others = [p for p in state.players if p.player_id != actor]
    assert me.zones.hand, "actor must observe its own hand"
    assert all(card != "<hidden>" for card in me.zones.hand)
    for other in others:
        assert other.zones.hand, "opponent hand size is public"
        assert all(card == "<hidden>" for card in other.zones.hand)
        assert other.zones.library == ()
    assert any(action.actor_id == actor for action in state.legal_actions)

    # 8. Fail-closed unsupported surface: unknown option rejected pre-execution.
    with pytest.raises(RulesEngineProtocolError):
        client.request(
            "submit_action",
            {
                "revision": frame["decision"]["revision"],
                "proposal": {
                    "proposal_id": str(uuid.uuid4()),
                    "actor_id": actor,
                    "legal_action_id": "opt-does-not-exist",
                    "action_type": "pass_priority",
                },
            },
            game_id=game_id,
        )

    # 9. Clean shutdown.
    down = client.request("shutdown_game", {}, game_id=game_id)
    assert down.get("game_id") == game_id
