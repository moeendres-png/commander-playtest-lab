"""Tests for Issue #1818 product error surfaces (validation, CI at n=0, sanitized cards, titles)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, create_revision, games, launch
from commander_lab.studio.decks import RevisionCard
from commander_lab.studio.simulations import GameSummary, aggregate_batch_results
from commander_lab.studio.web import create_app
from tests.unit.test_studio_builder import _deck, _fill

STATIC = Path(__file__).resolve().parents[2] / "src" / "commander_lab" / "studio" / "static"


def _seed_studio_101_cards(tmp_path: Path) -> str:
    store = StudioStore.open(tmp_path)
    try:
        _fill(store, tmp_path)
        cards = list(_deck())
        cards[-1] = RevisionCard(cards[-1].card_id, cards[-1].quantity + 1)
        rev_id = create_revision(store, deck_id="test", name="Test 101", cards=cards)
        return rev_id
    finally:
        store.close()


def test_101_card_deck_rejected_with_german_validation_before_engine_start(tmp_path: Path) -> None:
    rev_id = _seed_studio_101_cards(tmp_path)
    opponents = [deck["deck_id"] for deck in launch.opponent_decks()[:3]]
    client = TestClient(create_app(tmp_path), headers={"X-Studio": "1"})

    with (
        patch.object(launch, "engine_command", return_value=("java", "-jar", "mock.jar")),
        patch.object(launch, "cards_unsupported_by_engine", return_value=[]),
        patch.object(launch, "cards_unknown_to_pilots", return_value=[]),
        patch.object(launch.subprocess, "Popen") as mock_popen,
    ):
        game_res = client.post(
            "/api/games",
            json={"revision_id": rev_id, "opponent_ids": opponents, "seed": 1},
        )
        batch_res = client.post(
            "/api/simulations/batch",
            json={"revision_id": rev_id, "pod": "precon", "games_count": 2, "base_seed": 1},
        )

    mock_popen.assert_not_called()
    assert game_res.status_code == 422, game_res.text
    game_detail = str(game_res.json()["detail"])
    assert "101 von 100 Karten" in game_detail
    assert "Traceback" not in game_detail
    assert batch_res.status_code == 422, batch_res.text
    batch_detail = str(batch_res.json()["detail"])
    assert "101 von 100 Karten" in batch_detail
    assert "Traceback" not in batch_detail


def test_aggregate_batch_results_zero_completed_returns_null_ci_and_failure_summary() -> None:
    failed = [
        GameSummary(
            game_id=f"b-{i}",
            seed=i,
            status="failed",
            failure_class="BRIDGE_TIMEOUT",
        )
        for i in range(5)
    ]
    summary = aggregate_batch_results(failed)
    assert summary["games_completed"] == 0
    assert summary["games_failed"] == 5
    assert summary["win_rate"] is None
    assert summary["confidence_interval_95"] == {
        "lower": None,
        "upper": None,
        "lower_percent": None,
        "upper_percent": None,
    }
    assert summary["failure_summary"] == [{"reason": "BRIDGE_TIMEOUT", "count": 5}]


def test_orphaned_out_failure_message_hides_raw_traceback(tmp_path: Path) -> None:
    folder = tmp_path / "games"
    folder.mkdir()
    out_file = folder / "crash-game.out"
    out_file.write_text(
        'Traceback (most recent call last):\n  File "/abs/secret/play.py", line 12\nValueError: deck\n',
        encoding="utf-8",
    )
    record = games.read_game(tmp_path, "crash-game", count=0)
    res = record["result"]
    assert res["status"] == "failed"
    assert res["failure_class"] == "start_failed"
    assert "Traceback" not in res["failure_message"]
    assert "/abs/secret" not in res["failure_message"]


def test_ui_error_classification_and_partie_titles_in_node() -> None:
    node = shutil.which("node")
    assert node is not None
    script = f"""
const fs = require('fs');
const path = require('path');
const staticDir = {json.dumps(str(STATIC))};
const windowObj = {{}};
const storage = new Map();
global.window = windowObj;
global.localStorage = {{ getItem: (k) => storage.get(k) ?? null, setItem: (k, v) => storage.set(k, v) }};
global.document = {{
  documentElement: {{ dataset: {{}}, setAttribute: () => {{}} }},
  addEventListener: () => {{}},
  getElementById: () => null,
}};
function mkEl(tag, attrs, ...children) {{
  const flat = children.flat(Infinity).filter((c) => c !== null && c !== undefined && c !== false);
  return {{ tag, attrs: attrs || {{}}, children: flat }};
}}
function textOnly(node) {{
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (!node || typeof node !== 'object') return '';
  if (node.tag === 'details') return '';
  return (node.children || []).map(textOnly).join(' ');
}}
global.h = mkEl;
const uiCode = fs.readFileSync(path.join(staticDir, 'ui.js'), 'utf8');
const StudioUI = new Function('window', 'document', 'localStorage', uiCode + '; return StudioUI;')(windowObj, global.document, global.localStorage);
const cohortCode = fs.readFileSync(path.join(staticDir, 'cohort.js'), 'utf8');
const StudioCohort = new Function(cohortCode + '; return StudioCohort;')();
const partieCode = fs.readFileSync(path.join(staticDir, 'partie.js'), 'utf8');
function grab(src, name) {{
  const start = src.indexOf('function ' + name + '(');
  let i = src.indexOf('{{', start), depth = 0;
  for (; i < src.length; i++) {{
    if (src[i] === '{{') depth++;
    else if (src[i] === '}}') {{ depth--; if (depth === 0) return src.slice(start, i + 1); }}
  }}
  throw new Error(name);
}}
const titleFn = new Function('StudioCohort', 'StudioUI', 'seatName', grab(partieCode, 'gameTitle') + '; return gameTitle;')(StudioCohort, StudioUI, (s) => 'Sitz ' + (s + 1));
const bridgeSpec = StudioUI.classifyError({{
  status: 'failed',
  failure_class: 'BRIDGE_ERROR',
  failure_message: 'ENGINE_FAILURE [BRIDGE_ERROR] (diagnostics sha256:abcdef1234567890abcdef)',
}}, {{ context: 'game' }});
const startSpec = StudioUI.classifyError({{
  status: 'failed',
  failure_class: 'start_failed',
  failure_message: 'Der Engine-Prozess konnte vor Spielbeginn nicht gestartet werden.',
  stdout: 'Traceback (most recent call last):\\n  File "/secret/path.py"',
}}, {{ context: 'game' }});
const orphanedTitle = titleFn({{
  game_id: 'orphan-1',
  header: {{ seats: [] }},
  frames: 0,
  running: false,
  cohort: 'UNKNOWN',
  result: {{ status: 'failed', failure_class: 'start_failed' }},
}});
const cancelledTitle = titleFn({{
  game_id: 'cancel-1',
  header: {{ seats: [{{ commanders: ['Chulane'] }}], seed: 9 }},
  frames: 4,
  running: false,
  cohort: 'PLAYED_GAME',
  result: {{ status: 'cancelled' }},
}});
console.log(JSON.stringify({{ bridgeSpec, startSpec, orphanedTitle, cancelledTitle }}));
"""
    raw = subprocess.check_output([node, "-e", script], text=True)
    out = json.loads(raw)
    assert "sha256" not in out["bridgeSpec"]["sentence"]
    assert "ENGINE_FAILURE" not in out["bridgeSpec"]["sentence"]
    assert len(out["bridgeSpec"]["nextSteps"]) >= 1
    assert "Traceback" not in out["startSpec"]["sentence"]
    assert "Traceback" in out["startSpec"]["details"]
    assert "undefined" not in out["orphanedTitle"].lower()
    assert "fehlgeschlagen" in out["orphanedTitle"]
    assert out["cancelledTitle"].endswith("abgebrochen")
