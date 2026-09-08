#!/usr/bin/env python3
"""Add WS-49 request-independent readback fields required by G49-08.

This overlay is read-only evidence plumbing. It does not mutate game state,
calculate Magic legality, or choose player actions.

It adds:
- native natural-start deck identity/count/commander readback from XMage Deck;
- native Card.faceDown readback to the privileged semantic setup snapshot.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26Scenario.java"
REPLAY = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26ReplayRecorder.java"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"WS49_READBACK_EVIDENCE_ANCHOR_MISMATCH:{label}:count={count}")
    return text.replace(old, new, 1)


def patch_natural_deck_readback() -> None:
    text = SCENARIO.read_text(encoding="utf-8")
    old = '''    private static JsonObject validateNaturalStart(List<Deck> decks, Map<Integer, JsonObject> specs) {
        JsonArray checks = new JsonArray();
        for (int zero = 0; zero < decks.size(); zero++) {
            int seat = zero + 1;
            JsonObject spec = specs.get(seat);
            String expectedName = text(spec, "natural_library_card_name");
            int expectedCount = integer(spec, "natural_library_card_count");
            Deck deck = decks.get(zero);
            requireNative(deck.getCards().size() == expectedCount, "natural-deck-count:P" + seat);
            requireNative(
                    deck.getCards().stream().allMatch(card -> expectedName.equals(card.getName())),
                    "natural-deck-identity:P" + seat
            );
            JsonObject zones = object(spec, "zones");
            for (String zone : ZONES) {
                requireNative(optionalArray(zones, zone).isEmpty(), "natural-start-has-injected-zone:P" + seat);
            }
            checks.add("P" + seat + ":commander+natural-library");
        }
        JsonObject result = new JsonObject();
        result.addProperty("validator", "xmage-native-natural-start-preflight/1.0.0");
        result.addProperty("execution_entry_mode", NATURAL_GAME_START);
        result.addProperty("fail_closed", true);
        result.add("checks", checks);
        result.addProperty("valid", true);
        return result;
    }
'''
    new = '''    private static JsonObject validateNaturalStart(List<Deck> decks, Map<Integer, JsonObject> specs) {
        JsonArray checks = new JsonArray();
        JsonArray nativeDecks = new JsonArray();
        for (int zero = 0; zero < decks.size(); zero++) {
            int seat = zero + 1;
            JsonObject spec = specs.get(seat);
            String expectedName = text(spec, "natural_library_card_name");
            int expectedCount = integer(spec, "natural_library_card_count");
            Deck deck = decks.get(zero);
            requireNative(deck.getCards().size() == expectedCount, "natural-deck-count:P" + seat);
            requireNative(
                    deck.getCards().stream().allMatch(card -> expectedName.equals(card.getName())),
                    "natural-deck-identity:P" + seat
            );
            JsonObject zones = object(spec, "zones");
            for (String zone : ZONES) {
                requireNative(optionalArray(zones, zone).isEmpty(), "natural-start-has-injected-zone:P" + seat);
            }

            JsonObject nativeDeck = new JsonObject();
            nativeDeck.addProperty("player_id", "P" + seat);
            nativeDeck.addProperty("native_library_count", deck.getCards().size());
            JsonArray nativeLibraryNames = new JsonArray();
            deck.getCards().stream().map(Card::getName).distinct().sorted().forEach(nativeLibraryNames::add);
            nativeDeck.add("native_library_card_identities", nativeLibraryNames);
            JsonArray nativeCommanderNames = new JsonArray();
            deck.getSideboard().stream().map(Card::getName).sorted().forEach(nativeCommanderNames::add);
            nativeDeck.add("native_commander_card_identities", nativeCommanderNames);
            nativeDeck.addProperty("native_surface", "Deck.getCards/Deck.getSideboard");
            nativeDecks.add(nativeDeck);
            checks.add("P" + seat + ":commander+natural-library");
        }
        JsonObject result = new JsonObject();
        result.addProperty("validator", "xmage-native-natural-start-preflight/1.0.1");
        result.addProperty("execution_entry_mode", NATURAL_GAME_START);
        result.addProperty("fail_closed", true);
        result.add("checks", checks);
        result.add("native_decks", nativeDecks);
        result.addProperty("request_object_copied_as_readback", false);
        result.addProperty("valid", true);
        return result;
    }
'''
    SCENARIO.write_text(replace_once(text, old, new, "natural-native-decks"), encoding="utf-8")


def patch_privileged_card_face_down_readback() -> None:
    text = REPLAY.read_text(encoding="utf-8")
    old = '''            if (card != null) {
                item.addProperty("card_name", card.getName());
                item.addProperty("owner_seat", seat(card.getOwnerId()));
                item.addProperty("zone_change_counter", card.getZoneChangeCounter(game));
            }
'''
    new = '''            if (card != null) {
                item.addProperty("card_name", card.getName());
                item.addProperty("owner_seat", seat(card.getOwnerId()));
                item.addProperty("zone_change_counter", card.getZoneChangeCounter(game));
                item.addProperty("face_down", card.isFaceDown(game));
            }
'''
    REPLAY.write_text(replace_once(text, old, new, "privileged-card-face-down"), encoding="utf-8")


def main() -> int:
    patch_natural_deck_readback()
    patch_privileged_card_face_down_readback()
    print("WS49_READBACK_EVIDENCE_OVERLAY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
