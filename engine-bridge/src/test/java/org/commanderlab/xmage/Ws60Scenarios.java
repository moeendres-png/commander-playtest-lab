package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Predicate;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * WS60 RQ-C3 first-wave scenario specifications.
 *
 * <p>Each spec wires singleton Commander decks, a principal-disciplined pilot,
 * an omniscient completion predicate, terminal assertions straight from the
 * RQ-C3 execution pack, and principal-scoped hidden-info audits. Engine
 * legalities are never computed here; every choice answers an
 * engine-authoritative frame.</p>
 */
final class Ws60Scenarios {

    private Ws60Scenarios() {
    }

    static final List<String> RAINBOW = List.of(
            "Command Tower", "Exotic Orchard", "Reflecting Pool", "Gemstone Mine",
            "Tendo Ice Bridge");

    static Ws60Driver.SeatDeck seat1(String commander, Object... pairs) {
        return Ws60Decks.seat(List.of(commander), Ws60Decks.mainboard(pairs));
    }

    static Ws60Driver.SeatDeck seat2(String first, String second, Object... pairs) {
        List<String> main = Ws60Decks.mainboard(pairs);
        if (main.size() != 98) {
            throw new IllegalArgumentException("2-commander mainboard must be 98, was "
                    + main.size());
        }
        return Ws60Decks.seat(List.of(first, second), main);
    }

    static Ws60Driver.SeatDeck idleMountain() {
        return Ws60Decks.idle("Mountain", Ws60Decks.ROGRAKH);
    }

    static Ws60Driver.SeatDeck idlePlains() {
        return Ws60Decks.idle("Plains", Ws60Decks.ISHAI);
    }

    static Ws60Driver.SeatDeck idleSwamp() {
        return Ws60Decks.idle("Swamp", Ws60Decks.AYARA);
    }

    static void commandersAll(Ws60Pilot pilot, List<Ws60Driver.SeatDeck> seats) {
        for (int seat = 0; seat < seats.size(); seat++) {
            pilot.commanders(seat, seats.get(seat).commanders());
        }
    }

    static Ws60Driver.Completion publicComplete(Predicate<JsonObject> test) {
        return harness -> {
            JsonObject view;
            try {
                view = XmageFullGameStateRedactor.actorView(
                        harness.game, harness.players().get(0));
            } catch (RuntimeException exc) {
                return false;
            }
            try {
                return test.test(view);
            } catch (RuntimeException exc) {
                return false;
            }
        };
    }

    static Ws60Suite.CheckpointSet captureSet(Object... nameAndPredicate) {
        if (nameAndPredicate.length % 2 != 0) {
            throw new IllegalArgumentException("name/predicate pairs required");
        }
        Map<String, List<JsonObject>> captures = new HashMap<>();
        List<Ws60Driver.Checkpoint> checkpoints = new ArrayList<>();
        for (int i = 0; i < nameAndPredicate.length; i += 2) {
            String name = (String) nameAndPredicate[i];
            @SuppressWarnings("unchecked")
            Predicate<JsonObject> when = (Predicate<JsonObject>) nameAndPredicate[i + 1];
            checkpoints.add((frame, harness, seq) -> {
                if (captures.containsKey(name) || !when.test(frame)) {
                    return;
                }
                List<JsonObject> views = new ArrayList<>();
                for (int seat = 0; seat < 4; seat++) {
                    views.add(XmageFullGameStateRedactor.actorView(
                            harness.game, harness.players().get(seat)));
                }
                captures.put(name, views);
            });
        }
        return new Ws60Suite.CheckpointSet(checkpoints, captures);
    }

    static List<JsonObject> snapshotAll(Ws52Harness harness) {
        List<JsonObject> views = new ArrayList<>();
        for (int seat = 0; seat < 4; seat++) {
            views.add(XmageFullGameStateRedactor.actorView(
                    harness.game, harness.players().get(seat)));
        }
        return views;
    }

    static Predicate<JsonObject> frameIs(String clazz, String fragment) {
        return frame -> Ws60Pilot.frameClass(frame).equals(clazz)
                && (Ws60Pilot.prompt(frame).contains(fragment)
                        || Ws60Pilot.contextString(frame, "target_description").contains(fragment)
                        || Ws60Pilot.sourceName(frame).contains(fragment));
    }

    static Predicate<JsonObject> frameClassIs(String clazz) {
        return frame -> Ws60Pilot.frameClass(frame).equals(clazz);
    }

    /** Frame-class alternation (engines vary target vs choose_object by cost type). */
    static Predicate<JsonObject> frameIsAny(List<String> classes, String fragment) {
        return frame -> classes.contains(Ws60Pilot.frameClass(frame))
                && (Ws60Pilot.prompt(frame).contains(fragment)
                        || Ws60Pilot.contextString(frame, "target_description").contains(fragment)
                        || Ws60Pilot.sourceName(frame).contains(fragment));
    }

    static Predicate<JsonObject> frameOffers(String fragment) {
        return frame -> {
            if (!frame.has("legal_options") || !frame.get("legal_options").isJsonArray()) {
                return false;
            }
            for (JsonElement option : frame.getAsJsonArray("legal_options")) {
                if (option.getAsJsonObject().get("label").getAsString().contains(fragment)) {
                    return true;
                }
            }
            return false;
        };
    }

    static Predicate<JsonObject> frameOffersInClass(String clazz, String fragment) {
        return frame -> Ws60Pilot.frameClass(frame).equals(clazz) && frameOffers(fragment).test(frame);
    }

    static int tapeCount(JsonArray tape, String type) {
        int count = 0;
        for (JsonElement element : tape) {
            if (element.getAsJsonObject().get("type").getAsString().equals(type)) {
                count++;
            }
        }
        return count;
    }

    static List<Integer> dieResults(JsonArray tape) {
        List<Integer> out = new ArrayList<>();
        for (JsonElement element : tape) {
            JsonObject entry = element.getAsJsonObject();
            if (!entry.get("type").getAsString().equals("DIE_ROLLED")) {
                continue;
            }
            if (entry.has("amount")) {
                try {
                    // Tape amounts render as "amount=N" (see Ws60EventTape):
                    // strip the prefix before parsing the die result.
                    String first = entry.get("amount").getAsString().split(" ")[0];
                    if (first.startsWith("amount=")) {
                        first = first.substring("amount=".length());
                    }
                    out.add(Integer.parseInt(first));
                } catch (RuntimeException ignored) {
                    // Non-numeric amount text is ignored for band analysis.
                }
            }
        }
        return out;
    }

    static List<String> damagedPlayerAmounts(JsonArray tape, int rqSeat) {
        List<String> out = new ArrayList<>();
        String want = "WS52 Seat " + (rqSeat + 1);
        for (JsonElement element : tape) {
            JsonObject entry = element.getAsJsonObject();
            if (!entry.get("type").getAsString().equals("DAMAGED_PLAYER")) {
                continue;
            }
            String ref = entry.has("target_name") ? entry.get("target_name").getAsString() : "";
            if (ref.contains(want) && entry.has("amount")) {
                out.add(entry.get("amount").getAsString());
            }
        }
        return out;
    }

    static boolean logHasClassBetween(List<Ws60Driver.FrameRecord> log, String clazz,
            int fromSeq, int toSeq) {
        for (Ws60Driver.FrameRecord record : log) {
            int seq = record.projection().get("log_seq").getAsInt();
            if (seq >= fromSeq && seq <= toSeq
                    && record.projection().get("class").getAsString().equals(clazz)) {
                return true;
            }
        }
        return false;
    }

    // ------------------------------------------------------------------
    // A03 — Regeneration shield as automatic replacement.
    // ------------------------------------------------------------------

    static Ws60Suite.Spec a03() {
        List<Ws60Driver.SeatDeck> seats = List.of(
                seat2(Ws60Decks.THRASIOS, Ws60Decks.TYMNA,
                        "Drudge Skeletons", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Swamp", 56, "Plains", 20, "Forest", 15),
                seat2(Ws60Decks.THRASIOS, Ws60Decks.ROGRAKH,
                        "Lightning Bolt", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Mountain", 60, "Forest", 31),
                idlePlains(),
                idleSwamp());
        return new Ws60Suite.Spec("RQ-C3-A03",
                "Regeneration shield as automatic replacement (corrected: no may at destruction)",
                "RQ-C3-A03", 6103L, 3000, seats,
                () -> {
                    Ws60Pilot pilot = new Ws60Pilot("RQ-C3-A03");
                    commandersAll(pilot, seats);
                    pilot.seatLands(0, "Swamp", "Plains", "Forest")
                            .seatLands(1, "Mountain", "Plains", "Swamp", "Forest")
                            .landOrder(0, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Forest", "Plains", "Swamp")
                            .landOrder(1, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Forest", "Plains", "Swamp",
                                    "Mountain")
                            .secureWhen(0, "Drudge Skeletons")
                            .scryGas(0, 4)
                            .setupCast(0, "Drudge Skeletons")
                            .conserveMana(0, "Drudge Skeletons")
                            .allowCommanderCast(0).allowCommanderCast(1)
                            .assemblyFiltering(0).assemblyFiltering(1)
                            .setupActivate(0, "Regenerate")
                            .activateGate(0, "Regenerate", "Lightning Bolt")
                            .activateOnce("Regenerate")
                            .secureWhen(1, "Lightning Bolt")
                            .setupCast(1, "Lightning Bolt")
                            .castGate(1, "Lightning Bolt", "Drudge Skeletons")
                            .delayGate(1, "Lightning Bolt", "Drudge Skeletons", 1)
                            .target("", "Drudge Skeletons")
                            .bool("pay X life", true)
                            .seek(0, 6, "Drudge Skeletons", "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Gemstone Mine", "Tendo Ice Bridge")
                            .seek(1, 6, "Lightning Bolt", "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Gemstone Mine", "Tendo Ice Bridge")
                            .critical("Lightning Bolt")
                            .critical("Regenerate");
                    return pilot;
                },
                publicComplete(view -> Ws60Views.controls(view, 0, "Drudge Skeletons")
                        && Ws60Views.graveyardNames(view, 1).stream()
                                .anyMatch(card -> card.contains("Lightning Bolt"))
                        && Ws60Views.life(view, 0) == 40 && Ws60Views.life(view, 1) == 40
                        && Ws60Views.life(view, 2) == 40 && Ws60Views.life(view, 3) == 40),
                () -> captureSet(
                        "pre-resolution",
                        frameOffersInClass("priority", "Drudge Skeletons")),
                List.of(
                        new Ws60Suite.Assertion(
                                "Drudge Skeletons is on battlefield tapped with zero damage marked",
                                "battlefield",
                                (primary0, views, tape, log) -> {
                                    boolean tapped = false;
                                    for (Ws60Views.BattlefieldEntry entry :
                                            Ws60Views.battlefield(views.get(0), 0)) {
                                        if (entry.name().contains("Drudge Skeletons")) {
                                            assertTrue(entry.tapped(), "Skeletons must be tapped");
                                            assertEquals(0, entry.damage(), "no damage marked");
                                            tapped = true;
                                        }
                                    }
                                    assertTrue(tapped, "Skeletons on battlefield");
                                    return "tapped,damage=0";
                                }),
                        new Ws60Suite.Assertion("one P0 Swamp tapped for the {B} activation",
                                "battlefield",
                                (primary0, views, tape, log) -> {
                                    long tapped = Ws60Views.battlefield(views.get(0), 0).stream()
                                            .filter(entry -> entry.name().contains("Swamp")
                                                    && entry.tapped())
                                            .count();
                                    assertTrue(tapped >= 1,
                                            "at least one tapped Swamp, observed " + tapped);
                                    return "tapped-swamps=" + tapped;
                                }),
                        new Ws60Suite.Assertion("Lightning Bolt is in P1 graveyard",
                                "graveyards.P1",
                                (primary0, views, tape, log) ->
                                        Ws60Checks.graveHas(views, 1, "Lightning Bolt")),
                        new Ws60Suite.Assertion("all life totals unchanged", "life",
                                (primary0, views, tape, log) -> Ws60Checks.allLife(views, 40))),
                List.of(
                        new Ws60Suite.HiddenAudit("pre-activation", "ALL",
                                (captures, deckSeats) ->
                                        Ws60Checks.structuralPrivacy(captures, "pre-resolution"))));
    }

    // ------------------------------------------------------------------
    // A04 — Two counter replacements with divergent orders.
    // ------------------------------------------------------------------

    static Ws60Suite.Spec a04() {
        List<Ws60Driver.SeatDeck> seats = List.of(
                seat2(Ws60Decks.THRASIOS, Ws60Decks.TYMNA,
                        "Stonecoil Serpent", 1, "Hardened Scales", 1, "Doubling Season", 1,
                        "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Forest", 79, "Plains", 5, "Swamp", 5),
                idleMountain(), idlePlains(), idleSwamp());
        return new Ws60Suite.Spec("RQ-C3-A04",
                "Two counter replacements with divergent orders",
                "RQ-C3-A04", 6104L, 3000, seats,
                () -> {
                    Ws60Pilot pilot = new Ws60Pilot("RQ-C3-A04");
                    commandersAll(pilot, seats);
                    pilot.seatLands(0, "Forest", "Plains", "Swamp")
                            .landOrder(0, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Plains", "Swamp", "Forest")
                            .setupCast(0, "Hardened Scales", "Doubling Season",
                                    "Stonecoil Serpent")
                            .castGate(0, "Stonecoil Serpent", "Hardened Scales",
                                    "Doubling Season")
                            .ownCountGate(0, "Stonecoil Serpent", "Forest", 3)
                            .allowCommanderCast(0).assemblyFiltering(0)
                            .attackRoundRobin("Tymna the Weaver", List.of(2, 3))
                            .attackerFallback("Thrasios, Triton Hero", 3)
                            .bool("pay X life", true)
                            .scryGas(0, 4)
                            .secureWhen(0, "Hardened Scales", "Doubling Season",
                                    "Stonecoil Serpent")
                            .numeric("Stonecoil Serpent", 3)
                            .replacement("Hardened Scales", "Doubling Season")
                            .seek(0, 6, "Stonecoil Serpent", "Hardened Scales",
                                    "Doubling Season", "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Gemstone Mine", "Tendo Ice Bridge")
                            .critical("replacement_effect")
                            .critical("Stonecoil Serpent");
                    return pilot;
                },
                publicComplete(view -> {
                    for (Ws60Views.BattlefieldEntry entry :
                            Ws60Views.battlefield(view, 0)) {
                        if (entry.name().contains("Stonecoil Serpent")
                                && entry.power() == 8 && entry.toughness() == 8) {
                            return true;
                        }
                    }
                    return false;
                }),
                () -> captureSet(
                        "ordering",
                        frameIs("replacement_effect", "replacement")),
                List.of(
                        new Ws60Suite.Assertion(
                                "Stonecoil Serpent is 8/8 (0/0 base + eight +1/+1 counters)",
                                "battlefield",
                                (primary0, views, tape, log) -> {
                                    for (Ws60Views.BattlefieldEntry entry :
                                            Ws60Views.battlefield(views.get(0), 0)) {
                                        if (entry.name().contains("Stonecoil Serpent")) {
                                            assertEquals(8, entry.power(), "power");
                                            assertEquals(8, entry.toughness(), "toughness");
                                            return "8/8";
                                        }
                                    }
                                    fail("Serpent not on battlefield");
                                    throw new AssertionError("unreachable");
                                }),
                        new Ws60Suite.Assertion("exactly 8 +1/+1 counters on the Serpent",
                                "battlefield",
                                (primary0, views, tape, log) -> {
                                    for (Ws60Views.BattlefieldEntry entry :
                                            Ws60Views.battlefield(views.get(0), 0)) {
                                        if (entry.name().contains("Stonecoil Serpent")) {
                                            int total = entry.counters().values().stream()
                                                    .mapToInt(Integer::intValue).sum();
                                            assertEquals(8, total, "counters");
                                            return "counters=" + entry.counters();
                                        }
                                    }
                                    fail("Serpent not on battlefield");
                                    throw new AssertionError("unreachable");
                                }),
                        new Ws60Suite.Assertion("both enchantments remain on battlefield",
                                "battlefield",
                                (primary0, views, tape, log) -> Ws60Checks.controls(views, 0,
                                        "Hardened Scales") + "+"
                                        + Ws60Checks.controls(views, 0, "Doubling Season"))),
                List.of(
                        new Ws60Suite.HiddenAudit("ordering offer", "ALL",
                                (captures, deckSeats) ->
                                        Ws60Checks.structuralPrivacy(captures, "ordering"))));
    }
}
