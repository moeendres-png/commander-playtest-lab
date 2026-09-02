#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import finalist_generate_forge_provider as base


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"WS40_PROVIDER_OVERLAY_EXPECTED_ONE:{label}:{count}")
    return text.replace(old, new, 1)


def render(source: str, forge_commit: str, forge_tree: str) -> tuple[str, dict]:
    java, mapping = base.render(source, forge_commit, forge_tree)

    marker = "        RuntimeException failClosed(String method) {\n            return new UnsupportedOperationException(\"WS23_FAIL_CLOSED_UNSUPPORTED:\" + method);\n        }\n\n"
    methods = r'''        static String ws40EntityLabel(final GameEntity entity) {
            if (entity instanceof Card card) return "CARD:" + card.getName();
            if (entity instanceof Player p) return "PLAYER:" + p.getName();
            return "ENTITY:" + String.valueOf(entity);
        }

        @Override
        public CombatDamageSelection chooseCombatDamage(final CombatDamageDecisionView decision) {
            if (decision == null || decision.getSources().isEmpty()) {
                throw failClosed("chooseCombatDamage:EMPTY_CORE_VIEW");
            }
            final java.util.List<CombatDamageSelection> nativeOptions = new ArrayList<>();
            final java.util.List<String> semanticOptions = new ArrayList<>();
            for (CombatDamageDecisionView.SourceView source : decision.getSources()) {
                for (CombatDamageDecisionView.RecipientView recipient : source.getRecipients()) {
                    for (int amount = recipient.getMinDamage(); amount <= recipient.getMaxDamage(); amount++) {
                        nativeOptions.add(new CombatDamageSelection(source.getSource(), recipient.getRecipient(), amount));
                        semanticOptions.add("COMBAT_DAMAGE|source=" + ws40EntityLabel(source.getSource())
                                + "|recipient=" + ws40EntityLabel(recipient.getRecipient())
                                + "|amount=" + amount
                                + "|remaining=" + source.getRemainingDamage()
                                + "|lethal_remaining=" + recipient.getLethalDamageRemaining()
                                + "|defender=" + recipient.isDefender()
                                + "|first_strike_step=" + decision.isFirstStrikeDamage());
                    }
                }
            }
            if (nativeOptions.isEmpty()) throw failClosed("chooseCombatDamage:NO_CORE_OPTIONS");
            if (nativeOptions.size() == 1) {
                broker.recordAutomatic("SINGLE_CORE_COMBAT_DAMAGE_OPTION");
                return nativeOptions.get(0);
            }
            final String id = broker.choose("combatDamage", this.player, semanticOptions);
            final int idx = Integer.parseInt(id.substring(1));
            if (idx < 0 || idx >= nativeOptions.size()) throw failClosed("chooseCombatDamage:STALE_OPTION");
            return nativeOptions.get(idx);
        }

        @Override
        public AmountDistributionSelection chooseAmountDistribution(final AmountDistributionDecisionView decision) {
            if (decision == null || decision.getRecipients().isEmpty()) {
                throw failClosed("chooseAmountDistribution:EMPTY_CORE_VIEW");
            }
            final java.util.List<AmountDistributionSelection> nativeOptions = new ArrayList<>();
            final java.util.List<String> semanticOptions = new ArrayList<>();
            for (AmountDistributionDecisionView.RecipientView recipient : decision.getRecipients()) {
                for (int amount = recipient.getMinAmount(); amount <= recipient.getMaxAmount(); amount++) {
                    nativeOptions.add(new AmountDistributionSelection(recipient.getRecipient(), amount));
                    semanticOptions.add("AMOUNT_DISTRIBUTION|recipient=" + ws40EntityLabel(recipient.getRecipient())
                            + "|amount=" + amount + "|remaining=" + decision.getRemainingAmount());
                }
            }
            if (nativeOptions.isEmpty()) throw failClosed("chooseAmountDistribution:NO_CORE_OPTIONS");
            if (nativeOptions.size() == 1) {
                broker.recordAutomatic("SINGLE_CORE_AMOUNT_DISTRIBUTION_OPTION");
                return nativeOptions.get(0);
            }
            final String id = broker.choose("amountDistribution", this.player, semanticOptions);
            final int idx = Integer.parseInt(id.substring(1));
            if (idx < 0 || idx >= nativeOptions.size()) throw failClosed("chooseAmountDistribution:STALE_OPTION");
            return nativeOptions.get(idx);
        }

'''
    java = replace_once(java, marker, marker + methods, "Ws23Controller insertion marker")

    mapping = dict(mapping)
    callbacks = list(mapping.get("callbacks", []))
    callbacks.extend([
        {
            "name": "chooseCombatDamage",
            "classification": "EXTERNALLY_IMPLEMENTED_FROM_CORE_AUTHORIZED_OPTIONS",
            "authority": "CombatDamageDecisionView",
            "selection": "CombatDamageSelection",
        },
        {
            "name": "chooseAmountDistribution",
            "classification": "EXTERNALLY_IMPLEMENTED_FROM_CORE_AUTHORIZED_OPTIONS",
            "authority": "AmountDistributionDecisionView",
            "selection": "AmountDistributionSelection",
        },
    ])
    mapping["callbacks"] = callbacks
    mapping["schema_version"] = "ws40-forge-provider-overlay/1.0.0"
    mapping["combat_damage_authority"] = {
        "legality_owner": "FORGE_RULES_CORE",
        "view": "CombatDamageDecisionView",
        "provider_behavior": "ENUMERATE_ONLY_CORE_AUTHORIZED_SOURCE_RECIPIENT_AMOUNT_TUPLES",
        "pilot_submission": "OPAQUE_OPTION_ID_ONLY",
        "provider_legality_reconstruction": False,
        "forge_ai_fallback": False,
        "forge_gui_fallback": False,
    }
    mapping["noncombat_amount_distribution_authority"] = {
        "legality_owner": "FORGE_RULES_CORE",
        "view": "AmountDistributionDecisionView",
        "provider_legality_reconstruction": False,
    }
    return java, mapping


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--player-controller", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--forge-commit", required=True)
    ap.add_argument("--forge-tree", required=True)
    args = ap.parse_args()

    source = args.player_controller.read_text(encoding="utf-8")
    java, mapping = render(source, args.forge_commit, args.forge_tree)
    out = args.output_dir
    java_dir = out / "java" / "forge" / "game" / "player"
    java_dir.mkdir(parents=True, exist_ok=True)
    (java_dir / "Ws23ForgeVerticalProvider.java").write_text(java, encoding="utf-8")
    (out / "ws40_forge_provider_mapping.json").write_text(
        json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "schema_version": mapping["schema_version"],
        "forge_commit": args.forge_commit,
        "forge_tree": args.forge_tree,
        "callback_count": len(mapping["callbacks"]),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
