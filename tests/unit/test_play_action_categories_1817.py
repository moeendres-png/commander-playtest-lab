"""Tests for #1817: truthful play_land / cast_spell action categories across bridge & UI."""

from __future__ import annotations

import itertools
import json
import os
import shutil
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.semantic_replay.fingerprint import option_fingerprint
from commander_lab.studio.web import create_app

REPO_ROOT = Path(__file__).resolve().parents[2]
PARTIE_JS = REPO_ROOT / "src" / "commander_lab" / "studio" / "static" / "partie.js"
ENGINE_ENV = "COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD"
TURN_LIMIT = 8


def _extract_js_body(src: str, start_marker: str) -> str:
    start = src.index(start_marker)
    lines: list[str] = []
    depth = 0
    opened = False
    for line in src[start:].splitlines():
        lines.append(line)
        for ch in line:
            if ch == "{":
                depth += 1
                opened = True
            elif ch == "}":
                depth -= 1
        if opened and depth == 0:
            break
    return "\n".join(lines)


def test_option_fingerprint_preserves_metadata_for_play_land_and_cast_spell() -> None:
    land_opt = {
        "option_id": "land-1",
        "option_type": "play_land",
        "label": "Forest — Play Forest",
        "metadata": {
            "ability_type": "play_land",
            "source_name": "Forest",
            "mana_ability": False,
        },
    }
    spell_opt = {
        "option_id": "spell-1",
        "option_type": "cast_spell",
        "label": "Sol Ring — Cast Sol Ring",
        "metadata": {
            "ability_type": "spell",
            "source_name": "Sol Ring",
            "mana_ability": False,
        },
    }
    land_fp = option_fingerprint(land_opt)
    spell_fp = option_fingerprint(spell_opt)
    assert isinstance(land_fp, str) and len(land_fp) == 64
    assert isinstance(spell_fp, str) and len(spell_fp) == 64
    assert land_fp != spell_fp

    same_land_diff_id = {**land_opt, "option_id": "land-2"}
    assert option_fingerprint(same_land_diff_id) == land_fp

    diff_ability = {
        **spell_opt,
        "metadata": {**spell_opt["metadata"], "ability_type": "activated"},
    }
    assert option_fingerprint(diff_ability) != spell_fp


def test_partie_js_groups_and_localizes_priority_actions() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node binary unavailable")

    src = PARTIE_JS.read_text(encoding="utf-8")
    pool_line = next(line for line in src.splitlines() if line.startswith("const POOL_COLORS"))
    types_line = next(line for line in src.splitlines() if line.startswith("const OPTION_TYPES"))
    order_line = next(
        line for line in src.splitlines() if line.startswith("const PRIORITY_GROUP_ORDER")
    )
    resolve_fn = _extract_js_body(src, "function resolvePriorityOptionType(")
    localize_fn = _extract_js_body(src, "function localizeActionText(")
    suffix_fn = _extract_js_body(src, "function localizeActionSuffix(")

    script = "\n".join(
        [
            pool_line,
            types_line,
            order_line,
            resolve_fn,
            suffix_fn,
            localize_fn,
            """
const assert = require("assert");

assert.strictEqual(localizeActionText("Forest — Play Forest"), "Forest — Land spielen");
assert.strictEqual(localizeActionText("Crop Rotation — Cast Crop Rotation"), "Crop Rotation — Zauber wirken");
assert.strictEqual(
  localizeActionText("Forest — Play Forest from graveyard"),
  "Forest — Spiele Forest aus dem Friedhof"
);
assert.strictEqual(
  localizeActionText("Chulane, Teller of Tales — Cast Chulane, Teller of Tales from command zone"),
  "Chulane, Teller of Tales — Wirke Chulane, Teller of Tales aus der Kommandozone"
);
assert.strictEqual(localizeActionText("Play Island"), "Spiele Island");
assert.strictEqual(localizeActionText("Cast Sol Ring"), "Wirke Sol Ring");
assert.strictEqual(localizeActionText("Mind Stone — {1}, {T}: Draw a card"), "Mind Stone — {1}, {T}: Draw a card");
assert.strictEqual(localizeActionText("Pass priority"), "Priorität abgeben");

const sampleOptions = [
  { option_id: "pass-1", option_type: "pass_priority", label: "Pass priority", metadata: {} },
  { option_id: "mana-1", option_type: "mana_ability", label: "Forest — {T}: Add {G}.", metadata: { ability_type: "mana" } },
  { option_id: "act-1", option_type: "activated_ability", label: "Evolving Wilds — Activate: {T}, Sacrifice...", metadata: { ability_type: "activated" } },
  { option_id: "spell-1", option_type: "cast_spell", label: "Crop Rotation — Cast Crop Rotation", metadata: { ability_type: "spell" } },
  { option_id: "land-1", option_type: "play_land", label: "Forest — Play Forest", metadata: { ability_type: "play_land" } },
  { option_id: "legacy-spell", option_type: "activated_ability", label: "Sol Ring — Cast Sol Ring", metadata: { ability_type: "spell" } },
];

const other = sampleOptions.filter((opt) => opt.option_type !== "pass_priority");
const groups = new Map();
for (const opt of other) {
  const key = resolvePriorityOptionType(opt);
  if (!groups.has(key)) groups.set(key, []);
  groups.get(key).push(opt);
}
const orderedKeys = [...groups.keys()].sort((a, b) => {
  const ia = PRIORITY_GROUP_ORDER.indexOf(a);
  const ib = PRIORITY_GROUP_ORDER.indexOf(b);
  if (ia !== -1 && ib !== -1) return ia - ib;
  if (ia !== -1) return -1;
  if (ib !== -1) return 1;
  return 0;
});

assert.deepStrictEqual(orderedKeys, ["play_land", "cast_spell", "activated_ability", "mana_ability"]);
assert.deepStrictEqual(
  orderedKeys.map((k) => OPTION_TYPES[k]),
  ["Land spielen", "Zauber wirken", "Fähigkeit aktivieren", "Mana-Fähigkeit"]
);
assert.strictEqual(groups.get("cast_spell").length, 2);
assert.strictEqual(groups.get("activated_ability").length, 1);
assert.strictEqual(groups.get("play_land")[0].option_id, "land-1");
console.log(JSON.stringify({ orderedKeys, titles: orderedKeys.map((k) => OPTION_TYPES[k]) }));
""",
        ]
    )
    proc = subprocess.run([node, "-e", script], check=False, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    parsed = json.loads(proc.stdout.strip())
    assert parsed["orderedKeys"] == ["play_land", "cast_spell", "activated_ability", "mana_ability"]


def _scripted_choice_for_1817(
    pending: dict[str, object], chosen: Sequence[dict[str, object]]
) -> dict[str, object]:
    cls = str(pending["decision_class"])
    options = list(pending.get("legal_options") or pending.get("options") or [])  # type: ignore[arg-type]
    min_sel = int(pending.get("minimum_selections") or pending.get("min_selections") or 0)

    def by_types(*types: str) -> list[dict[str, object]]:
        return sorted(
            (o for o in options if o.get("option_type") in types),
            key=lambda o: str(o.get("label", "")),
        )

    selected: list[dict[str, object]] = []
    if chosen:
        selected = list(chosen)
    elif cls == "mulligan":
        selected = by_types("keep")[:1]
    elif cls == "priority":
        lands = by_types("play_land")
        if not lands:
            lands = [
                o
                for o in by_types("play_land_ability", "activated_ability")
                if (o.get("metadata") or {}).get("ability_type") == "play_land"  # type: ignore[union-attr]
            ]
        selected = (lands or by_types("pass_priority"))[:1]
    elif cls == "declare_attacker":
        selected = by_types("hold_attacker")[:1]
    elif cls == "mana_payment":
        selected = by_types("cancel_mana_payment")[:1]
    elif min_sel > 0:
        selected = sorted(options, key=lambda o: str(o.get("label", "")))[:min_sel]

    body: dict[str, object] = {
        "decision_id": pending["decision_id"],
        "selected_option_ids": [o["option_id"] for o in selected],
    }
    ctx = pending.get("context") or {}
    if isinstance(ctx, dict) and ctx.get("numeric_min") is not None:
        body["numeric_choice"] = int(ctx["numeric_min"])
    return body


@pytest.mark.external
def test_real_engine_4p_priority_payload_exposes_play_land_and_cast_spell_types(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real 4-player human-seat Studio PLAY verification for #1817."""
    from commander_lab.studio import launch

    command = launch.engine_command(tmp_path)
    if command is None:
        pytest.skip(f"NOT RUN (not a pass): set {ENGINE_ENV} with Java 21")
    jar = next((Path(a) for prev, a in itertools.pairwise(command) if prev == "-jar"), None)
    if jar is None or not jar.is_file():
        pytest.skip(f"NOT RUN (not a pass): missing bridge jar in {command!r}")

    precons = {deck_id: path for deck_id, _n, _c, _y, path in launch._precons()}
    decks = [
        precons["precon/2026/lorehold_spirit"],
        precons["precon/2024/animated_army"],
        precons["precon/2024/quick_draw"],
        precons["precon/2025/sultai_arisen"],
    ]
    monkeypatch.setattr(
        launch, "prepare_table_deck_paths", lambda *_a, **_k: ("real-engine-1817", decks)
    )
    client = TestClient(create_app(tmp_path), headers={"X-Studio": "1"})
    started = client.post(
        "/api/games",
        json={
            "revision_id": "r",
            "opponent_ids": ["o1", "o2", "o3"],
            "seed": 11,
            "human_seats": [0],
            "ai_delay_ms": 0,
        },
    )
    assert started.status_code == 200, started.text
    game_id = started.json()["game_id"]

    observed_play_land = False
    observed_cast_spell = False
    mislabeled: list[dict[str, object]] = []
    deadline = time.monotonic() + 240
    try:
        while time.monotonic() < deadline and not (observed_play_land and observed_cast_spell):
            state = client.get(f"/api/play/{game_id}?count=0").json()
            pending = state.get("pending_decision")
            if not pending:
                if not state.get("running"):
                    break
                time.sleep(0.15)
                continue
            assert isinstance(pending, dict)
            cls = str(pending["decision_class"])
            options = list(pending.get("legal_options") or pending.get("options") or [])
            if cls == "priority":
                for opt in options:
                    meta = opt.get("metadata") or {}
                    ab_type = meta.get("ability_type") if isinstance(meta, dict) else None
                    opt_type = opt.get("option_type")
                    if opt_type == "play_land":
                        observed_play_land = True
                    if opt_type == "cast_spell":
                        observed_cast_spell = True
                    if ab_type in {"play_land", "spell"} and opt_type == "activated_ability":
                        mislabeled.append(opt)
                # Ensure land plays happen early so castable spells become affordable before turn limit
                turn = (pending.get("pilot_state") or {}).get("turn_number", 1)
                if isinstance(turn, int) and turn >= TURN_LIMIT:
                    break
            chosen: list[dict[str, object]] = []
            if cls == "priority":
                lands = [o for o in options if o.get("option_type") == "play_land"]
                spells = [o for o in options if o.get("option_type") == "cast_spell"]
                chosen = (
                    lands
                    or spells
                    or [o for o in options if o.get("option_type") == "pass_priority"]
                )[:1]
            body = _scripted_choice_for_1817(pending, chosen)
            reply = client.post(f"/api/play/{game_id}/decision", json=body)
            assert reply.status_code == 200, (cls, body, reply.text)
    finally:
        client.app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]

    assert not mislabeled, (
        f"Found play_land/spell options mislabeled as activated_ability: {mislabeled}"
    )
    assert observed_play_land, (
        f"Expected option_type='play_land' in 4p real game (os.environ={os.environ.get(ENGINE_ENV)})"
    )
    assert observed_cast_spell, "Expected option_type='cast_spell' in 4p real game"
