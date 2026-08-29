#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import ws23_generate_forge_vertical_provider as base


EXTRA_EXTERNAL = {
    "chooseTargetsFor",
    "payManaCost",
    "applyManaToCost",
    "confirmReplacementEffect",
    "declareAttackers",
    "declareBlockers",
}


BROKER_REF_METHOD = r'''
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

'''


def v2_method_body(original, name: str) -> list[str]:
    if name == "chooseSpellAbilityToPlay":
        return ["return Ws23ForgeAuthority.choosePriority(broker, player, getGame());"]
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
    return original(name)


def render_v2(source: str, forge_commit: str, forge_tree: str) -> tuple[str, dict]:
    original_body = base.method_body
    original_external = set(base.EXTERNALLY_IMPLEMENTED)
    try:
        base.method_body = lambda name: v2_method_body(original_body, name)
        base.EXTERNALLY_IMPLEMENTED |= EXTRA_EXTERNAL
        java, mapping = base.render(source, forge_commit, forge_tree)
    finally:
        base.method_body = original_body
        base.EXTERNALLY_IMPLEMENTED.clear()
        base.EXTERNALLY_IMPLEMENTED.update(original_external)

    marker = "        boolean chooseBoolean(String kind, Player actor, String trueLabel, String falseLabel) {"
    if marker not in java:
        raise RuntimeError("base broker marker changed")
    java = java.replace(marker, BROKER_REF_METHOD + marker, 1)

    old_start = "            match.startGame(game);"
    new_start = "            match.startGame(game, () -> Ws23ForgeAuthority.installScenario(game, broker));"
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
