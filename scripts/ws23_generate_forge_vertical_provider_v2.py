#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path

base = importlib.import_module("ws23_generate_forge_vertical_provider")


EXTRA_EXTERNAL = {
    "getAbilityToPlay",
    "getCostDecisionMaker",
    "chooseTargetsFor",
    "payManaCost",
    "applyManaToCost",
    "confirmReplacementEffect",
    "declareAttackers",
    "declareBlockers",
    "orderSimultaneousSa",
}

EXTRA_AUTOMATIC = {"assignCombatDamage", "playSpellAbilityNoStack"}

COST_VISITOR_TYPES = (
    "CostBehold",
    "CostBeholdExile",
    "CostGainControl",
    "CostChooseColor",
    "CostChooseCreatureType",
    "CostCollectEvidence",
    "CostDiscard",
    "CostDamage",
    "CostDraw",
    "CostExile",
    "CostExileFromStack",
    "CostExiledMoveToGrave",
    "CostExert",
    "CostEnlist",
    "CostFlipCoin",
    "CostForage",
    "CostRollDice",
    "CostMill",
    "CostAddMana",
    "CostPayLife",
    "CostPayEnergy",
    "CostGainLife",
    "CostPartMana",
    "CostPromiseGift",
    "CostPutCardToLib",
    "CostTap",
    "CostSacrifice",
    "CostReturn",
    "CostReveal",
    "CostRevealChosen",
    "CostRemoveAnyCounter",
    "CostRemoveCounter",
    "CostPutCounter",
    "CostPutCounterYou",
    "CostUntapType",
    "CostUntap",
    "CostUnattach",
    "CostTapType",
    "CostPayShards",
    "CostBlight",
)


BROKER_REF_METHOD = r"""
        String chooseRefs(String kind, Player actor, java.util.List<String> labels, java.util.List<String> publicRefs) {
            if (labels.size() != publicRefs.size()) throw new ControlledStop("WS23_OPTION_METADATA_SIZE_MISMATCH");
            long seq = ++decisionSeq;
            String did = "d" + seq;
            java.util.List<String> ids = new ArrayList<>();
            StringBuilder opts = new StringBuilder();
            for (int i = 0; i < labels.size(); i++) {
                String id = "o" + i;
                ids.add(id);
                if (i > 0) opts.append(',');
                opts.append("{\"option_id\":").append(esc(id))
                    .append(",\"kind\":").append(esc(labels.get(i)))
                    .append(",\"public_ref\":").append(esc(publicRefs.get(i))).append("}");
            }
            out.println("{\"protocol\":" + esc(PROTOCOL)
                + ",\"message_type\":\"DECISION_FRAME\",\"request_id\":" + esc(did)
                + ",\"session_id\":" + esc(SESSION_ID)
                + ",\"actor_id\":" + esc(actor.getName())
                + ",\"state_revision\":" + revision
                + ",\"payload\":{\"decision_id\":" + esc(did)
                + ",\"decision_kind\":" + esc(kind)
                + ",\"options_digest\":" + esc(digest(ids))
                + ",\"options\":[" + opts + "]}}");
            out.flush();
            try {
                String answer = in.readLine();
                if (answer == null) throw new ControlledStop("WS23_EXTERNAL_EOF");
                if (!"SUBMIT_DECISION".equals(field(answer, "message_type"))) throw new ControlledStop("WS23_EXPECTED_SUBMIT_DECISION");
                if (!did.equals(field(answer, "decision_id"))) throw new ControlledStop("WS23_STALE_OR_WRONG_DECISION_ID");
                String choice = field(answer, "option_id");
                if (choice == null || !ids.contains(choice)) throw new ControlledStop("WS23_OPTION_NOT_OFFERED");
                revision++;
                return choice;
            } catch (IOException e) {
                throw new RuntimeException(e);
            }
        }

"""

COST_DECISION_MAKER_TEMPLATE = r"""
    static final class Ws23CostDecisionMaker extends CostDecisionMakerBase {
        final Broker broker;

        Ws23CostDecisionMaker(Broker broker, Player actor, SpellAbility ability, boolean effect) {
            super(actor, effect, ability, ability == null ? null : ability.getHostCard());
            this.broker = broker;
        }

        @Override
        public boolean paysRightAfterDecision() {
            return false;
        }

__VISITS__
    }

"""


def cost_decision_maker_java() -> str:
    methods: list[str] = []
    for cost_type in COST_VISITOR_TYPES:
        if cost_type == "CostPartMana":
            body = (
                'broker.recordAutomatic("costDecision:CostPartMana:DEFER_TO_CONTROLLER");\n'
                "            return PaymentDecision.number(0);"
            )
        else:
            body = (
                'throw new UnsupportedOperationException("WS23_FAIL_CLOSED_UNSUPPORTED:costPart:'
                + cost_type
                + '");'
            )
        methods.append(
            "        @Override\n"
            f"        public PaymentDecision visit({cost_type} cost) {{\n"
            f"            {body}\n"
            "        }"
        )
    return COST_DECISION_MAKER_TEMPLATE.replace("__VISITS__", "\n\n".join(methods))


def v2_method_body(original, name: str) -> list[str]:
    if name == "getAbilityToPlay":
        return [
            "return Ws23ForgeAuthority.chooseAbilityToPlay(broker, player, hostCard, abilities);"
        ]
    if name == "getCostDecisionMaker":
        return ["return new Ws23CostDecisionMaker(broker, player, ability, effect);"]
    if name == "playSpellAbilityNoStack":
        return [
            'broker.recordAutomatic("playSpellAbilityNoStack:FORGE_CORE");',
            'if (!PlaySpellAbility.playSpellAbilityNoStack(this, player, effectSA, !mayChoseNewTargets)) throw new ControlledStop("WS23_FORGE_NO_STACK_EXECUTION_REJECTED");',
            "return;",
        ]
    if name == "chooseSpellAbilityToPlay":
        return [
            "java.util.List<SpellAbility> choices = Ws23ForgeAuthority.choosePriority(broker, player, getGame());",
            "return choices == null || choices.isEmpty() ? null : choices;",
        ]
    if name == "playChosenSpellAbility":
        return [
            "return Ws23ForgeAuthority.playChosenSpellAbility(this, broker, player, sa, getGame());"
        ]
    if name == "chooseTargetsFor":
        return ["return Ws23ForgeAuthority.chooseTargets(broker, player, currentAbility);"]
    if name == "payManaCost":
        return [
            "return Ws23ForgeAuthority.payManaCost(this, toPay, costPartMana, sa, player, prompt, matrix, effect);"
        ]
    if name == "applyManaToCost":
        return [
            "return Ws23ForgeAuthority.applyManaToCost(broker, player, toPay, ability, matrix);"
        ]
    if name == "confirmReplacementEffect":
        return [
            "return Ws23ForgeAuthority.confirmReplacement(broker, player, replacementEffect, effectSA, affected, question);"
        ]
    if name == "declareAttackers":
        return ["Ws23ForgeAuthority.declareAttackers(broker, player, attacker, combat);", "return;"]
    if name == "declareBlockers":
        return ["Ws23ForgeAuthority.declareBlockers(broker, player, defender, combat);", "return;"]
    if name == "assignCombatDamage":
        return [
            "if (blockers == null || blockers.size() != 1 || defender != null || overrideOrder || (remaining != null && remaining.size() > 1)) throw failClosed(\"assignCombatDamage:NON_UNIQUE\");",
            'broker.recordAutomatic("assignCombatDamage:UNIQUE_SINGLE_BLOCKER");',
            "java.util.Map<Card, Integer> assigned = new java.util.HashMap<>();",
            "assigned.put(blockers.get(0), damageDealt);",
            "return assigned;",
        ]
    if name == "orderSimultaneousSa":
        return ["return Ws23ForgeAuthority.orderSimultaneous(broker, player, activePlayerSAs);"]
    return original(name)


def render_v2(source: str, forge_commit: str, forge_tree: str) -> tuple[str, dict]:
    original_body = base.method_body
    original_external = set(base.EXTERNALLY_IMPLEMENTED)
    original_automatic = set(base.AUTOMATIC)
    try:
        base.method_body = lambda name: v2_method_body(original_body, name)
        base.EXTERNALLY_IMPLEMENTED |= EXTRA_EXTERNAL
        base.AUTOMATIC |= EXTRA_AUTOMATIC
        java, mapping = base.render(source, forge_commit, forge_tree)
    finally:
        base.method_body = original_body
        base.EXTERNALLY_IMPLEMENTED.clear()
        base.EXTERNALLY_IMPLEMENTED.update(original_external)
        base.AUTOMATIC.clear()
        base.AUTOMATIC.update(original_automatic)

    marker = "        boolean chooseBoolean(String kind, Player actor, String trueLabel, String falseLabel) {"
    if marker not in java:
        raise RuntimeError("base broker marker changed")
    java = java.replace(marker, BROKER_REF_METHOD + marker, 1)

    controller_marker = "    static final class Ws23Controller extends PlayerController {"
    if controller_marker not in java:
        raise RuntimeError("base controller marker changed")
    java = java.replace(controller_marker, cost_decision_maker_java() + controller_marker, 1)

    old_rules = "        GameRules rules = new GameRules(GameType.Constructed);"
    new_rules = (
        "        GameRules rules = new GameRules(GameType.Constructed);\n"
        "        rules.addAppliedVariant(GameType.Commander);"
    )
    if old_rules not in java:
        raise RuntimeError("base GameRules construction changed")
    java = java.replace(old_rules, new_rules, 1)

    old_start = "            match.startGame(game);"
    new_start = (
        "            match.startGame(game, () -> Ws23ForgeAuthority.installScenario(game, broker));"
    )
    if old_start not in java:
        raise RuntimeError("base Match.startGame call changed")
    java = java.replace(old_start, new_start, 1)

    old_budget = "        Broker broker = new Broker(in, out, 16);"
    if old_budget not in java:
        raise RuntimeError("base broker construction changed")
    java = java.replace(old_budget, "        Broker broker = new Broker(in, out, 128);", 1)

    mapping["schema_version"] = "ws23-player-controller-mapping/2.0.0"
    mapping["authority_helper"] = "Ws23ForgeAuthority"
    mapping["gate_a_base_preserved"] = True
    mapping["support_scope"] = "BOUNDED_VERTICAL_SLICE_ONLY"
    mapping["cost_decision_policy"] = "MANA_DEFERRED_TO_EXTERNAL_CONTROLLER_OTHER_COSTS_FAIL_CLOSED"
    return java, mapping


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--player-controller", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--forge-commit", required=True)
    ap.add_argument("--forge-tree", required=True)
    args = ap.parse_args()

    source = args.player_controller.read_text(encoding="utf-8")
    java, mapping = render_v2(source, args.forge_commit, args.forge_tree)
    out = args.output_dir
    java_dir = out / "java" / "forge" / "game" / "player"
    java_dir.mkdir(parents=True, exist_ok=True)
    (java_dir / "Ws23ForgeVerticalProvider.java").write_text(java, encoding="utf-8")
    (out / "player_controller_mapping_v2.json").write_text(
        json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "abstract_method_count": mapping["abstract_method_count"],
                "externally_implemented": sum(
                    x["classification"] == "EXTERNALLY_IMPLEMENTED" for x in mapping["callbacks"]
                ),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
