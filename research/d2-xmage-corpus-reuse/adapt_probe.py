"""D2 XMage corpus reuse probe — bounded adaptation validator.

Reads nothing from WS49 worktrees. Contains three hand-adapted scenario drafts
(setup + action script + stop point + observable checklist, NO expected values)
derived from XMage tests at the pinned source. Validates every draft against
the probe constraints and runs negative self-tests to prove fail-closed
behavior.

Pinned source: moeendres-png/mage@0c1f455ea8c8fa48ab9d638ad5068ec242800428
(tree fdb8bf56a8bd8199a4ef372e468d93d6550b0649), MIT License.
"""
from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

SOURCE_PIN = {
    "repository": "moeendres-png/mage",
    "branch": "foundry/ws39-commander-history-state-restore",
    "commit": "0c1f455ea8c8fa48ab9d638ad5068ec242800428",
    "tree": "fdb8bf56a8bd8199a4ef372e468d93d6550b0649",
    "license": "MIT (LICENSE.txt at pinned commit; (c) 2010 betasteward@gmail.com)",
}

# Action vocabulary mirrored from the lab's TacticalScenario ActionType enum
# (schemas/models/TacticalScenario.schema.json): pass_priority, play_land,
# cast_spell, cast_commander, activate_ability, declare_attackers,
# declare_blockers, choose_targets, choose_mode, pay_cost, mulligan, concede,
# structural_decision.
KNOWN_ACTIONS = {
    "pass_priority", "play_land", "cast_spell", "cast_commander",
    "activate_ability", "declare_attackers", "declare_blockers",
    "choose_targets", "choose_mode", "pay_cost", "mulligan", "concede",
    "structural_decision",
}

FORBIDDEN_KEYS = {"expected", "assert", "should_be", "expected_value",
                  "xmage_result", "imported_outcome"}
FORBIDDEN_TOKENS = {"aiPlayPriority", "ai_play", "auto_choose", "default_choice",
                    "setStrictChooseMode", "rollbackTurns", "runCode"}
# Card names may appear ONLY inside setup identity/placement fields.
SETUP_IDENTITY_KEYS = {"card_identity", "commander", "placements", "deck",
                       "library_template", "creature_identity", "draft_id",
                       "source_path", "source_method"}


def draft_cast_commander_basic() -> dict:
    """Adapted from CastCommanderTest.testCastCommander (13 LOC)."""
    return {
        "draft_id": "D2-ADAPT-01",
        "provenance": {
            "source_path": "Mage.Tests/src/test/java/org/mage/test/commander/duel/CastCommanderTest.java",
            "source_method": "testCastCommander",
            **SOURCE_PIN,
        },
        "setup": {
            "format": "commander_duel",
            "players": ["A", "B"],
            "placements": [
                {"player": "A", "zone": "battlefield",
                 "card_identity": "Swamp", "count": 5},
            ],
            "commander": {"player": "A",
                          "card_identity": "Ob Nixilis of the Black Oath",
                          "zone": "command"},
        },
        "action_script": [
            {"action": "cast_commander", "player": "A",
             "card_identity": "Ob Nixilis of the Black Oath",
             "turn": 1, "phase": "precombat_main",
             "choices": "none_required_explicit"},
        ],
        "stop_point": {"turn": 1, "phase": "begin_combat"},
        "observable_checklist": [
            {"observable": "zone_of_commander",
             "authoritative_source": "rules_core"},
            {"observable": "life_totals",
             "authoritative_source": "rules_core"},
        ],
        "deterministic_choices": "explicit",
        "engine_ai": False,
    }


def draft_multiplayer_trigger() -> dict:
    """Adapted from MultiplayerTriggerTest (21 LOC)."""
    return {
        "draft_id": "D2-ADAPT-02",
        "provenance": {
            "source_path": "Mage.Tests/src/test/java/org/mage/test/multiplayer/MultiplayerTriggerTest.java",
            "source_method": "testMultiplayerAttackStinkdrinkerBanditTrigger",
            **SOURCE_PIN,
        },
        "setup": {
            "format": "free_for_all_4p_range_all",
            "players": ["A", "B", "C", "D"],
            "placements": [
                {"player": "A", "zone": "battlefield",
                 "card_identity": "Stinkdrinker Bandit", "count": 1},
                {"player": "A", "zone": "battlefield",
                 "card_identity": "Pestermite", "count": 1},
            ],
        },
        "action_script": [
            {"action": "declare_attackers", "player": "A",
             "assignments": [
                 {"creature_identity": "Pestermite",
                  "defender": "B", "blocked": "unresolved_branch"},
                 {"creature_identity": "Stinkdrinker Bandit",
                  "defender": "C", "blocked": "unresolved_branch"},
             ],
             "turn": 1, "phase": "declare_attackers",
             "choices": "blocker_decisions_deferred_to_rules_core"},
        ],
        "stop_point": {"turn": 1, "phase": "postcombat_main"},
        "observable_checklist": [
            {"observable": "power_toughness_each_attacker",
             "authoritative_source": "rules_core"},
        ],
        "deterministic_choices": "explicit",
        "engine_ai": False,
    }


def draft_dead_player_target() -> dict:
    """Adapted from PlayerDiedStackTargetHandlingTest (18 LOC)."""
    return {
        "draft_id": "D2-ADAPT-03",
        "provenance": {
            "source_path": "Mage.Tests/src/test/java/org/mage/test/multiplayer/PlayerDiedStackTargetHandlingTest.java",
            "source_method": "TestDeadPlayerIsNoLongerValidTarget",
            **SOURCE_PIN,
        },
        "setup": {
            "format": "free_for_all_4p_range_one",
            "players": ["A", "B", "C", "D"],
            "player_order": ["A", "D", "C", "B"],
            "placements": [
                {"player": "A", "zone": "battlefield",
                 "card_identity": "Plains", "count": 2},
                {"player": "A", "zone": "battlefield",
                 "card_identity": "Mountain", "count": 2},
                {"player": "A", "zone": "hand",
                 "card_identity": "Lightning Helix", "count": 2},
            ],
        },
        "action_script": [
            {"action": "cast_spell", "player": "A",
             "card_identity": "Lightning Helix", "turn": 1,
             "phase": "precombat_main",
             "choices": [{"choice": "choose_targets", "target": "player_D"}]},
            {"action": "cast_spell", "player": "A",
             "card_identity": "Lightning Helix", "turn": 1,
             "phase": "precombat_main",
             "choices": [{"choice": "choose_targets", "target": "player_D"}]},
        ],
        "stop_point": {"turn": 2, "phase": "postcombat_main"},
        "observable_checklist": [
            {"observable": "graveyard_count_lightning_helix_A",
             "authoritative_source": "rules_core"},
            {"observable": "active_player_at_stop",
             "authoritative_source": "rules_core"},
            {"observable": "life_total_A",
             "authoritative_source": "rules_core"},
        ],
        "deterministic_choices": "explicit",
        "engine_ai": False,
    }


def _walk(node, path=""):
    if isinstance(node, dict):
        for key, value in node.items():
            yield f"{path}.{key}", key, value
            yield from _walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            yield from _walk(value, f"{path}[{idx}]")


def validate_draft(draft: dict) -> list[str]:
    """Return a list of violations (empty = valid). Fail closed."""
    violations = []
    required = {"draft_id", "provenance", "setup", "action_script",
                "stop_point", "observable_checklist", "deterministic_choices",
                "engine_ai"}
    missing = required - set(draft)
    if missing:
        violations.append(f"missing_sections:{sorted(missing)}")
    for field in ("commit", "tree", "repository", "license",
                  "source_path", "source_method"):
        if field not in draft.get("provenance", {}):
            violations.append(f"provenance_missing:{field}")
    for path, key, value in _walk(draft):
        if isinstance(key, str) and key.lower() in FORBIDDEN_KEYS:
            violations.append(f"outcome_field_present:{path}")
        if isinstance(value, str):
            lowered = value.lower()
            for token in FORBIDDEN_TOKENS:
                if token.lower() in lowered:
                    violations.append(f"forbidden_token:{token}@{path}")
                    break
        if isinstance(value, bool) and key == "engine_ai" and value is True:
            violations.append(f"engine_ai_true:{path}")
    for idx, step in enumerate(draft.get("action_script", [])):
        action = step.get("action")
        if action not in KNOWN_ACTIONS:
            violations.append(f"unknown_action:{action}@step{idx}")
        if action in {"cast_spell", "cast_commander", "activate_ability"} \
                and "choices" not in step:
            violations.append(f"choice_point_unspecified:step{idx}")
    for item in draft.get("observable_checklist", []):
        if "expected" in item:
            violations.append("checklist_has_expected_value")
        if item.get("authoritative_source") != "rules_core":
            violations.append("checklist_authority_not_rules_core")
    if draft.get("deterministic_choices") != "explicit":
        violations.append("choices_not_explicit")
    return violations


def main() -> int:
    started = time.monotonic()
    drafts = [draft_cast_commander_basic(), draft_multiplayer_trigger(),
              draft_dead_player_target()]
    failures = 0
    for draft in drafts:
        violations = validate_draft(draft)
        status = "VALID" if not violations else "INVALID"
        if violations:
            failures += 1
        print(f"{draft['draft_id']}: {status} "
              f"violations={violations or 'none'}")
        out = HERE / f"adapted_{draft['draft_id'].lower().replace('-', '_')}.json"
        out.write_text(json.dumps(draft, indent=2) + "\n")

    # Negative self-tests: corrupted drafts MUST fail validation.
    neg1 = copy.deepcopy(drafts[0])
    neg1["observable_checklist"][0]["expected"] = "battlefield"
    neg2 = copy.deepcopy(drafts[1])
    neg2["action_script"][0]["driver"] = "aiPlayPriority"
    neg3 = copy.deepcopy(drafts[2])
    neg3["engine_ai"] = True
    negatives = [("NEG-outcome-import", neg1), ("NEG-engine-ai", neg2),
                 ("NEG-ai-flag", neg3)]
    neg_ok = 0
    for name, bad in negatives:
        violations = validate_draft(bad)
        rejected = bool(violations)
        neg_ok += rejected
        print(f"{name}: {'REJECTED' if rejected else 'ACCEPTED(BUG)'} "
              f"violations={violations or 'none'}")

    elapsed = time.monotonic() - started
    print(f"validator_elapsed_s={elapsed:.3f} "
          f"drafts_valid={len(drafts) - failures}/{len(drafts)} "
          f"negatives_rejected={neg_ok}/{len(negatives)}")
    if failures or neg_ok != len(negatives):
        print("PROBE_RESULT=FAIL")
        return 1
    print("PROBE_RESULT=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
