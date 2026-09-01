"""Apply the qualification-only Primitive-A native-state materialization overlay.

The canonical NATIVE_STATE_LOAD fixtures intentionally describe only the semantic
objects present in the requested state; they are not Commander decklists. XMage's
normal import path must still receive a legal 100-card Commander deck. This overlay
therefore keeps import/bootstrap state separate from canonical semantic state and
materializes any requested non-commander cards as real XMage Card instances before
the existing native zone/state loader binds and validates them.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26Scenario.java"
CANONICAL = ROOT / "candidate-qualification/finalist-convergence-xmage/canonical_v101.py"
RUNNER = ROOT / "candidate-qualification/finalist-convergence-xmage/run_canonical_starter18.py"


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"overlay anchor mismatch for {path}: expected 1, observed {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    replace_exact(
        CANONICAL,
        '        mainboard = [item["card_identity"] for item in owned if item["zone"] != "command"]\n',
        '        # NATIVE_STATE_LOAD records are semantic states, not decklists. Keep the\n'
        '        # validated import bootstrap legal and inert; requested objects are loaded\n'
        '        # as real XMage cards by XmageWs26Scenario before native state binding.\n'
        '        mainboard = ["Mountain"] * 99\n',
    )

    replace_exact(
        SCENARIO,
        "import mage.cards.decks.Deck;\n",
        "import mage.cards.decks.Deck;\n"
        "import mage.cards.repository.CardInfo;\n"
        "import mage.cards.repository.CardRepository;\n",
    )

    old_preflight = '''        // Full preflight before any native mutation: malformed input must be retry-safe.\n        for (int zero = 0; zero < players.size(); zero++) {\n            Map<String, Integer> requested = new HashMap<>();\n            JsonObject zones = bySeat.get(zero + 1).getAsJsonObject("zones");\n            for (String zone : ZONES) {\n                for (JsonElement element : optionalArray(zones, zone)) {\n                    requested.merge(text(element.getAsJsonObject(), "card_name"), 1, Integer::sum);\n                }\n            }\n            Map<String, List<Card>> available = available(game, players.get(zero).getId());\n            for (Map.Entry<String, Integer> entry : requested.entrySet()) {\n                if (available.getOrDefault(entry.getKey(), List.of()).size() < entry.getValue()) {\n                    throw fail("STALE_OBJECT_OR_CARD_REFERENCE: " + entry.getKey());\n                }\n            }\n        }\n\n'''
    new_preflight = '''        // Full preflight before any native game mutation: malformed input must be retry-safe.\n        // The imported Commander deck is only a legal bootstrap. Canonical NATIVE_STATE_LOAD\n        // records are semantic states, not decklists, so requested objects that are absent from\n        // that bootstrap are instantiated as real XMage cards and then loaded through Game.loadCards.\n        Map<UUID, List<Card>> nativeMaterialization = new LinkedHashMap<>();\n        for (int zero = 0; zero < players.size(); zero++) {\n            Map<String, Integer> requested = new HashMap<>();\n            JsonObject zones = bySeat.get(zero + 1).getAsJsonObject("zones");\n            for (String zone : ZONES) {\n                for (JsonElement element : optionalArray(zones, zone)) {\n                    requested.merge(text(element.getAsJsonObject(), "card_name"), 1, Integer::sum);\n                }\n            }\n            UUID ownerId = players.get(zero).getId();\n            Map<String, List<Card>> nativeAvailable = available(game, ownerId);\n            List<Card> additions = new ArrayList<>();\n            for (Map.Entry<String, Integer> entry : requested.entrySet()) {\n                int missing = entry.getValue() - nativeAvailable.getOrDefault(entry.getKey(), List.of()).size();\n                if (missing <= 0) continue;\n                List<CardInfo> infos = CardRepository.instance.findCards(entry.getKey(), 1);\n                if (infos.size() != 1 || !entry.getKey().equals(infos.get(0).getName())) {\n                    throw fail("STALE_OBJECT_OR_CARD_REFERENCE: " + entry.getKey());\n                }\n                for (int index = 0; index < missing; index++) {\n                    Card card = infos.get(0).createCard();\n                    if (card == null) throw fail("STALE_OBJECT_OR_CARD_REFERENCE: " + entry.getKey());\n                    additions.add(card);\n                }\n            }\n            nativeMaterialization.put(ownerId, additions);\n        }\n        for (Map.Entry<UUID, List<Card>> entry : nativeMaterialization.entrySet()) {\n            if (!entry.getValue().isEmpty()) {\n                game.loadCards(new LinkedHashSet<>(entry.getValue()), entry.getKey());\n            }\n        }\n\n'''
    replace_exact(SCENARIO, old_preflight, new_preflight)

    # XMage's native payment transaction can expose either of two legitimate stages:\n    # (1) activate the Mountain mana ability, then (2) commit the resulting red pool mana.\n    # Depending on native transaction timing a request may observe either stage first.\n    # Each request must still have exactly one semantic match. If both or neither appear,\n    # unique_option fails closed; no index/default/random selection is ever used.\n    replace_exact(
        RUNNER,
        '''                option = unique_option(\n                    pending,\n                    lambda item: item.get("option_type") == "mana_ability"\n                    and _metadata(item).get("source_name") == "Mountain",\n                    "mana:obj:pilot-mountain",\n                )\n''',
        '''                option = unique_option(\n                    pending,\n                    lambda item: (\n                        item.get("option_type") == "mana_ability"\n                        and _metadata(item).get("source_name") == "Mountain"\n                    ) or (\n                        item.get("option_type") == "mana_pool"\n                        and str(_metadata(item).get("mana_type", "")).casefold() == "red"\n                        and int(_metadata(item).get("mana_available", 0)) > 0\n                    ),\n                    "mana:native-red-payment-stage",\n                )\n''',
    )
    print("XMAGE_PRIMITIVE_A_NATIVE_STATE_OVERLAY=PASS")


if __name__ == "__main__":
    main()
