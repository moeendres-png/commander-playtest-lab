"""Apply the qualification-only Primitive-A native-state materialization overlay."""

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

    old_preflight = '''        // Full preflight before any native mutation: malformed input must be retry-safe.
        for (int zero = 0; zero < players.size(); zero++) {
            Map<String, Integer> requested = new HashMap<>();
            JsonObject zones = bySeat.get(zero + 1).getAsJsonObject("zones");
            for (String zone : ZONES) {
                for (JsonElement element : optionalArray(zones, zone)) {
                    requested.merge(text(element.getAsJsonObject(), "card_name"), 1, Integer::sum);
                }
            }
            Map<String, List<Card>> available = available(game, players.get(zero).getId());
            for (Map.Entry<String, Integer> entry : requested.entrySet()) {
                if (available.getOrDefault(entry.getKey(), List.of()).size() < entry.getValue()) {
                    throw fail("STALE_OBJECT_OR_CARD_REFERENCE: " + entry.getKey());
                }
            }
        }

'''
    new_preflight = '''        // Full preflight before any native game mutation: malformed input must be retry-safe.
        // The imported Commander deck is only a legal bootstrap. Canonical NATIVE_STATE_LOAD
        // records are semantic states, not decklists, so requested objects that are absent from
        // that bootstrap are instantiated as real XMage cards and then loaded through Game.loadCards.
        Map<UUID, List<Card>> nativeMaterialization = new LinkedHashMap<>();
        for (int zero = 0; zero < players.size(); zero++) {
            Map<String, Integer> requested = new HashMap<>();
            JsonObject zones = bySeat.get(zero + 1).getAsJsonObject("zones");
            for (String zone : ZONES) {
                for (JsonElement element : optionalArray(zones, zone)) {
                    requested.merge(text(element.getAsJsonObject(), "card_name"), 1, Integer::sum);
                }
            }
            UUID ownerId = players.get(zero).getId();
            Map<String, List<Card>> nativeAvailable = available(game, ownerId);
            List<Card> additions = new ArrayList<>();
            for (Map.Entry<String, Integer> entry : requested.entrySet()) {
                int missing = entry.getValue() - nativeAvailable.getOrDefault(entry.getKey(), List.of()).size();
                if (missing <= 0) continue;
                List<CardInfo> infos = CardRepository.instance.findCards(entry.getKey(), 1);
                if (infos.size() != 1 || !entry.getKey().equals(infos.get(0).getName())) {
                    throw fail("STALE_OBJECT_OR_CARD_REFERENCE: " + entry.getKey());
                }
                for (int index = 0; index < missing; index++) {
                    Card card = infos.get(0).createCard();
                    if (card == null) throw fail("STALE_OBJECT_OR_CARD_REFERENCE: " + entry.getKey());
                    additions.add(card);
                }
            }
            nativeMaterialization.put(ownerId, additions);
        }
        for (Map.Entry<UUID, List<Card>> entry : nativeMaterialization.entrySet()) {
            if (!entry.getValue().isEmpty()) {
                game.loadCards(new LinkedHashSet<>(entry.getValue()), entry.getKey());
            }
        }

'''
    replace_exact(SCENARIO, old_preflight, new_preflight)

    # XMage's native payment transaction can expose either of two legitimate stages:
    # 1. activate the Mountain mana ability;
    # 2. commit the resulting red mana already present in the native mana pool.
    # The matcher still requires exactly one semantic match on every decision frame.
    replace_exact(
        RUNNER,
        '''                option = unique_option(
                    pending,
                    lambda item: item.get("option_type") == "mana_ability"
                    and _metadata(item).get("source_name") == "Mountain",
                    "mana:obj:pilot-mountain",
                )
''',
        '''                option = unique_option(
                    pending,
                    lambda item: (
                        item.get("option_type") == "mana_ability"
                        and _metadata(item).get("source_name") == "Mountain"
                    ) or (
                        item.get("option_type") == "mana_pool"
                        and str(_metadata(item).get("mana_type", "")).casefold() == "red"
                        and int(_metadata(item).get("mana_available", 0)) > 0
                    ),
                    "mana:native-red-payment-stage",
                )
''',
    )

    print("XMAGE_PRIMITIVE_A_NATIVE_STATE_OVERLAY=PASS")


if __name__ == "__main__":
    main()
