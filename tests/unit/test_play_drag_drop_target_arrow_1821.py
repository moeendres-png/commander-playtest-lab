"""Tests for #1821: PLAY Drag & Drop and SVG Targeting Arrow Mode."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src" / "commander_lab" / "studio" / "static"


def _run_node(script: str) -> dict:
    proc = subprocess.run(
        ["node", "-"],
        input=script,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"node failed ({proc.returncode}):\n{proc.stderr}"
    return json.loads(proc.stdout)


def test_drag_target_ux_hand_and_permanent_classification_and_drop_guards() -> None:
    boardclick_js = (STATIC / "boardclick.js").read_text(encoding="utf-8")
    drag_js = (STATIC / "drag_target_ux.js").read_text(encoding="utf-8")

    out = _run_node(
        f"""
{boardclick_js}
{drag_js}

const pendingAttack = {{
  decision_id: "dec-atk-6p",
  decision_class: "declare_attacker",
  actor_id: "p0",
  seat: 0,
  minimum_selections: 1,
  maximum_selections: 1,
  pilot_state: {{
    players: [0, 1, 2, 3, 4, 5].map((s) => ({{
      seat: s,
      player_id: s === 0 ? "p0" : `op-${{s}}`,
      battlefield: s === 0 ? [{{ object_id: "atk-1", name: "Chulane, Teller of Tales" }}, {{ object_id: "other-1", name: "Llanowar Elves" }}] : [{{ object_id: `pw-${{s}}`, name: `Garruk ${{s}}` }}],
      hand: [], command: [], graveyard: [], exile: []
    }})),
    stack: []
  }},
  legal_options: [
    {{ option_id: "o-s1", option_type: "attacker", label: "Chulane, Teller of Tales attacks Full Game Seat 2", metadata: {{ object_id: "atk-1", name: "Chulane, Teller of Tales", defender_id: "seat2-id" }} }},
    {{ option_id: "o-s5", option_type: "attacker", label: "Chulane, Teller of Tales attacks Full Game Seat 6", metadata: {{ object_id: "atk-1", name: "Chulane, Teller of Tales", defender_id: "seat6-id" }} }},
    {{ option_id: "o-pw4", option_type: "attacker", label: "Chulane, Teller of Tales attacks Garruk 4", metadata: {{ object_id: "atk-1", name: "Chulane, Teller of Tales", defender_id: "pw-4" }} }},
    {{ option_id: "o-hold", option_type: "hold_attacker", label: "Do not attack with Chulane, Teller of Tales", metadata: {{ object_id: "atk-1" }} }}
  ]
}};
const atkModel = StudioBoardClick.build(pendingAttack);

const pendingBlock = {{
  decision_id: "dec-blk-6p",
  decision_class: "declare_blocker",
  seat: 0,
  minimum_selections: 0,
  maximum_selections: 2,
  pilot_state: {{
    players: [
      {{ seat: 0, battlefield: [{{ object_id: "blk-1", name: "Wall of Omens" }}], hand: [], command: [], graveyard: [], exile: [] }},
      {{ seat: 4, battlefield: [{{ object_id: "e-atk-4", name: "Colossal Dreadmaw" }}], hand: [], command: [], graveyard: [], exile: [] }}
    ],
    stack: []
  }},
  legal_options: [
    {{ option_id: "e-atk-4", option_type: "blocker", label: "Wall of Omens blocks Colossal Dreadmaw", metadata: {{ blocker_id: "blk-1", attacker_id: "e-atk-4" }} }}
  ]
}};
const blkModel = StudioBoardClick.build(pendingBlock);

const pendingTarget = {{
  decision_id: "dec-tgt-6p",
  decision_class: "target",
  seat: 0,
  minimum_selections: 1,
  maximum_selections: 1,
  source_object: {{ object_id: "stk-1", name: "Path to Exile" }},
  pilot_state: {{
    players: [0, 1, 2, 3, 4, 5].map((s) => ({{
      seat: s,
      battlefield: s === 5 ? [{{ object_id: "t-cr-5", name: "Craterhoof Behemoth" }}] : [],
      hand: [], command: [], graveyard: [], exile: []
    }})),
    stack: [{{ object_id: "stk-1", name: "Path to Exile" }}]
  }},
  legal_options: [
    {{ option_id: "t-cr-5", option_type: "target", label: "Craterhoof Behemoth", metadata: {{ object_id: "t-cr-5", name: "Craterhoof Behemoth" }} }},
    {{ option_id: "seat6-id", option_type: "target", label: "Full Game Seat 6", metadata: {{ object_id: "seat6-id", name: "Full Game Seat 6" }} }}
  ]
}};
const tgtModel = StudioBoardClick.build(pendingTarget);

const handLand = StudioDragTargetUX.classifyHandDrag({{ name: "Forest", objectId: "h-1", playableNow: true, primaryOptionId: "opt-land", actionKind: "play_land" }}, pendingAttack, true, false, false);
const handBlocked = StudioDragTargetUX.classifyHandDrag({{ name: "Cultivate", objectId: "h-2", playableNow: false, primaryOptionId: null, actionKind: "cast_spell" }}, pendingAttack, true, false, false);
const handReplay = StudioDragTargetUX.classifyHandDrag({{ name: "Forest", objectId: "h-1", playableNow: true, primaryOptionId: "opt-land", actionKind: "play_land" }}, pendingAttack, false, false, false);

const atkDragAsked = StudioDragTargetUX.classifyPermanentDrag("atk-1", "Chulane, Teller of Tales", pendingAttack, atkModel, true, false, false);
const atkDragOther = StudioDragTargetUX.classifyPermanentDrag("other-1", "Llanowar Elves", pendingAttack, atkModel, true, false, false);
const blkDragAsked = StudioDragTargetUX.classifyPermanentDrag("blk-1", "Wall of Omens", pendingBlock, blkModel, true, false, false);

const pendingPriorityAction = {{
  decision_id: "dec-prio-act",
  decision_class: "priority",
  seat: 0,
  minimum_selections: 1,
  maximum_selections: 1,
  pilot_state: {{
    players: [{{ seat: 0, battlefield: [{{ object_id: "b-sol", name: "Sol Ring" }}], hand: [], command: [], graveyard: [], exile: [] }}],
    stack: []
  }},
  legal_options: [
    {{ option_id: "opt-sol", option_type: "activated_ability", label: "Activate Sol Ring", metadata: {{ source_object_id: "b-sol" }} }}
  ]
}};
const prioActionModel = StudioBoardClick.build(pendingPriorityAction);
const prioDragAction = StudioDragTargetUX.classifyPermanentDrag("b-sol", "Sol Ring", pendingPriorityAction, prioActionModel, true, false, false);
const prioBoardDrop = StudioDragTargetUX.isLegalDropTarget(prioDragAction, {{ type: "board" }}, prioActionModel);
const prioTargetDropRejected = StudioDragTargetUX.isLegalDropTarget(prioDragAction, {{ type: "seat", seat: 1 }}, prioActionModel);

const legalSeat5Atk = StudioDragTargetUX.isLegalDropTarget(atkDragAsked, {{ type: "seat", seat: 5 }}, atkModel);
const illegalSeat3Atk = StudioDragTargetUX.isLegalDropTarget(atkDragAsked, {{ type: "seat", seat: 3 }}, atkModel);
const legalPw4Atk = StudioDragTargetUX.isLegalDropTarget(atkDragAsked, {{ type: "object", id: "pw-4" }}, atkModel);
const legalBlock = StudioDragTargetUX.isLegalDropTarget(blkDragAsked, {{ type: "object", id: "e-atk-4" }}, blkModel);
const illegalBlock = StudioDragTargetUX.isLegalDropTarget(blkDragAsked, {{ type: "seat", seat: 4 }}, blkModel);
const legalBoardDrop = StudioDragTargetUX.isLegalDropTarget(handLand, {{ type: "board" }}, atkModel);

const tmActive = StudioDragTargetUX.resolveTargetMode(pendingTarget, tgtModel, {{ stack: ["Path to Exile"] }}, null);
const tmPaused = StudioDragTargetUX.resolveTargetMode(pendingTarget, tgtModel, {{ stack: ["Path to Exile"] }}, "dec-tgt-6p");
const tmNotTarget = StudioDragTargetUX.resolveTargetMode(pendingAttack, atkModel, {{ stack: [] }}, null);

const arrowLong = StudioDragTargetUX.computeCurvedArrowPath(80, 900, 1480, 140);
const arrowZero = StudioDragTargetUX.computeCurvedArrowPath(50, 50, 50, 50);

console.log(JSON.stringify({{
  handLand,
  handBlocked,
  handReplay,
  atkDragAsked,
  atkDragOther,
  blkDragAsked,
  prioDragAction,
  prioBoardDrop,
  prioTargetDropRejected,
  legalSeat5Atk,
  illegalSeat3Atk,
  legalPw4Atk,
  legalBlock,
  illegalBlock,
  legalBoardDrop,
  tmActive,
  tmPaused,
  tmNotTarget,
  arrowLong,
  arrowZero
}}));
"""
    )

    assert out["handLand"]["draggable"] is True
    assert out["handLand"]["dropMode"] == "board"
    assert out["handLand"]["arrowKind"] == "land"
    assert out["handBlocked"]["draggable"] is False
    assert out["handReplay"]["draggable"] is False

    assert out["atkDragAsked"]["draggable"] is True
    assert out["atkDragAsked"]["kind"] == "attacker"
    assert out["atkDragAsked"]["arrowKind"] == "attack"
    assert out["atkDragOther"]["draggable"] is False
    assert out["blkDragAsked"]["draggable"] is True
    assert out["blkDragAsked"]["kind"] == "blocker"

    assert out["prioDragAction"]["draggable"] is True
    assert out["prioDragAction"]["kind"] == "permanent_action"
    assert out["prioDragAction"]["dropMode"] == "board"
    assert out["prioBoardDrop"] is True
    assert out["prioTargetDropRejected"] is False

    assert out["legalSeat5Atk"] is True
    assert out["illegalSeat3Atk"] is False
    assert out["legalPw4Atk"] is True
    assert out["legalBlock"] is True
    assert out["illegalBlock"] is False
    assert out["legalBoardDrop"] is True

    assert out["tmActive"]["active"] is True
    assert out["tmActive"]["paused"] is False
    assert out["tmActive"]["sourceAnchor"] == {"type": "object", "id": "stk-1"}
    assert out["tmActive"]["targetCount"] == 2
    assert out["tmPaused"]["active"] is False
    assert out["tmPaused"]["paused"] is True
    assert out["tmNotTarget"]["active"] is False

    assert out["arrowLong"]["d"].startswith("M 80 900 Q ")
    assert out["arrowLong"]["length"] > 1500
    assert out["arrowZero"]["length"] == 0


def test_drag_target_html_css_js_hygiene_and_hooks() -> None:
    html = (STATIC / "partie.html").read_text(encoding="utf-8")
    css = (STATIC / "partie.css").read_text(encoding="utf-8")
    js = (STATIC / "partie.js").read_text(encoding="utf-8")
    drag_js = (STATIC / "drag_target_ux.js").read_text(encoding="utf-8")

    assert 'id="drag-ghost"' in html
    assert html.index('src="drag_target_ux.js"') < html.index('src="partie.js"')

    for selector in (
        ".drag-ghost",
        ".board-arrow",
        ".dragging-source",
        ".target-aimed",
        ".drop-target-hover",
    ):
        assert selector in css

    assert "innerHTML" not in drag_js
    assert "eval(" not in drag_js
    assert '"data-seat": String(player.seat)' in js
    assert '"data-stack-object-id"' in js
    assert "bindPointerDrag" in js
    assert "dismissTargetMode" in js
    assert "appendCurvedArrow" in js
    assert '$("side").addEventListener("scroll"' in js


def test_dismiss_target_mode_preserves_staged_selected_options() -> None:
    partie_js = (STATIC / "partie.js").read_text(encoding="utf-8")
    start = partie_js.index("function dismissTargetMode(")
    depth = 0
    idx = partie_js.index("{", start)
    for i in range(idx, len(partie_js)):
        if partie_js[i] == "{":
            depth += 1
        elif partie_js[i] == "}":
            depth -= 1
            if depth == 0:
                fn_src = partie_js[start : i + 1]
                break
    else:
        raise AssertionError("unterminated dismissTargetMode")

    out = _run_node(
        f"""
const state = {{
  pendingDecision: {{ decision_id: "dec-multi-tgt" }},
  selectedOptions: ["t-1", "t-2"],
  hoveredTarget: {{ type: "object", id: "t-1" }},
  targetPointer: {{ x: 10, y: 20 }},
  targetModeDismissedId: null,
}};
const currentTargetMode = () => ({{ active: true }});
let renders = 0;
const render = () => {{ renders += 1; }};
const syncHoverHighlights = () => {{}};
const toast = () => {{}};
{fn_src}
const dismissed = dismissTargetMode();
console.log(JSON.stringify({{
  dismissed,
  dismissedId: state.targetModeDismissedId,
  selectedOptions: state.selectedOptions,
  renders
}}));
"""
    )
    assert out["dismissed"] is True
    assert out["dismissedId"] == "dec-multi-tgt"
    assert out["selectedOptions"] == ["t-1", "t-2"]
    assert out["renders"] == 1
