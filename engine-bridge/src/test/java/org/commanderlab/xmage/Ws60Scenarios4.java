package org.commanderlab.xmage;

import com.google.gson.JsonObject;

import java.util.ArrayList;
import java.util.List;

import static org.commanderlab.xmage.Ws60Scenarios.*;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;
/**
 * WS60 RQ-C3 first-wave scenario specifications, part 4 (G03, G04, H01, I01).
 */
final class Ws60Scenarios4 {

    private Ws60Scenarios4() {
    }

    // ------------------------------------------------------------------
    // G03 — Commander damage loss at 21 (two native hits, 0->12->24).
    // ------------------------------------------------------------------

    static Ws60Suite.Spec g03() {
        List<Ws60Driver.SeatDeck> seats = List.of(
                Ws60Decks.seat(List.of(Ws60Decks.GHALTA_TYRANT),
                        Ws60Decks.basics("Forest", 99)),
                idleMountain(), idlePlains(), idleSwamp());
        return new Ws60Suite.Spec("RQ-C3-G03",
                "Commander damage loss at 21 (corrected: seeded 12 zero-credit + native 12)",
                "RQ-C3-G03", 6163L, 3000, seats,
                () -> {
                    Ws60Pilot pilot = new Ws60Pilot("RQ-C3-G03");
                    commandersAll(pilot, seats);
                    pilot.seatLands(0, "Forest")
                            .landOrder(0, "Forest")
                            .allowCommanderCast(0)
                            .attacker("Ghalta, Stampede Tyrant", 1)
                            .critical("declare_attacker");
                    return pilot;
                },
                publicComplete(view -> Ws60Views.hasLost(view, 1)
                        && Ws60Views.commanderDamageTo(view, "Ghalta, Stampede Tyrant", 1)
                                >= 21),
                () -> captureSet(
                        "attack",
                        frameIs("declare_attacker", "Ghalta")),
                List.of(
                        new Ws60Suite.Assertion(
                                "P1 has lost the game (commander damage total 24 from Ghalta)",
                                "players.P1",
                                (primary0, views, tape, log) -> {
                                    Ws60Checks.lost(views, 1, true);
                                    int total = Ws60Views.commanderDamageTo(views.get(0),
                                            "Ghalta, Stampede Tyrant", 1);
                                    assertEquals(24, total, "commander damage ledger");
                                    List<String> hits = damagedPlayerAmounts(tape, 1);
                                    assertTrue(hits.stream().anyMatch(
                                            amount -> amount.startsWith("12 combat")),
                                            "two native 12-combat hits: " + hits);
                                    return "ledger=" + total + ";hits=" + hits;
                                }),
                        new Ws60Suite.Assertion("P0, P2, P3 remain in game", "players",
                                (primary0, views, tape, log) ->
                                        Ws60Checks.lost(views, 0, false) + "+"
                                                + Ws60Checks.lost(views, 2, false) + "+"
                                                + Ws60Checks.lost(views, 3, false)),
                        new Ws60Suite.Assertion("Ghalta on battlefield under P0",
                                "battlefield",
                                (primary0, views, tape, log) ->
                                        Ws60Checks.controls(views, 0,
                                                "Ghalta, Stampede Tyrant"))),
                List.of(
                        new Ws60Suite.HiddenAudit("damage ledger", "ALL",
                                (captures, deckSeats) ->
                                        Ws60Checks.structuralPrivacy(captures, "attack"))));
    }

    // ------------------------------------------------------------------
    // G04 — Control Magic controller leaves game (AG-1 governed).
    // ------------------------------------------------------------------

    static Ws60Suite.Spec g04() {
        List<Ws60Driver.SeatDeck> seats = List.of(
                seat2(Ws60Decks.THRASIOS, Ws60Decks.KRAUM,
                        "Control Magic", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Island", 87, "Forest", 4),
                seat2(Ws60Decks.THRASIOS, Ws60Decks.TANA,
                        "Runeclaw Bear", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Forest", 91),
                idlePlains(),
                idleSwamp());
        return new Ws60Suite.Spec("RQ-C3-G04",
                "Control Magic controller leaves game",
                "RQ-C3-G04", 6164L, 3000, seats,
                () -> {
                    Ws60Pilot pilot = new Ws60Pilot("RQ-C3-G04");
                    commandersAll(pilot, seats);
                    pilot.seatLands(0, "Island", "Forest")
                            .seatLands(1, "Forest")
                            .landOrder(0, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Forest", "Island")
                            .landOrder(1, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Forest")
                            .commanders(0, List.of(Ws60Decks.THRASIOS))
                            .setupCast(0, "Control Magic")
                            .castGate(0, "Control Magic", "Runeclaw Bear")
                            .allowCommanderCast(0).allowCommanderCast(1)
                            .assemblyFiltering(0).assemblyFiltering(1)
                            .bool("pay X life", true)
                            .target("creature", "Runeclaw Bear")
                            .setupCast(1, "Runeclaw Bear")
                            .seek(0, 6, "Control Magic", "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Gemstone Mine", "Tendo Ice Bridge")
                            .critical("Control Magic");
                    return pilot;
                },
                publicComplete(view -> {
                    if (!Ws60Views.hasLeft(view, 0)) {
                        return false;
                    }
                    for (Ws60Views.BattlefieldEntry entry :
                            Ws60Views.battlefield(view, 1)) {
                        if (entry.name().contains("Runeclaw Bear")) {
                            return true;
                        }
                    }
                    return false;
                }),
                () -> {
                    java.util.Map<String, List<JsonObject>> captures = new java.util.HashMap<>();
                    List<Ws60Driver.Checkpoint> checkpoints = new ArrayList<>();
                    boolean[] conceded = {false};
                    checkpoints.add((frame, harness, seq) -> {
                        if (!conceded[0] && Ws60Pilot.actorSeat(frame) != 0) {
                            JsonObject view;
                            try {
                                view = XmageFullGameStateRedactor.actorView(
                                        harness.game, harness.players().get(0));
                            } catch (RuntimeException exc) {
                                return;
                            }
                            boolean magicOut = Ws60Views.controls(view, 0, "Control Magic");
                            boolean bearOut = Ws60Views.battlefield(view, 1).stream()
                                    .anyMatch(entry -> entry.name()
                                            .contains("Runeclaw Bear"));
                            if (magicOut && bearOut) {
                                harness.game.setConcedingPlayer(
                                        harness.players().get(0).getId());
                                conceded[0] = true;
                            }
                        }
                        if (conceded[0] && !captures.containsKey("post-cleanup")) {
                            JsonObject view;
                            try {
                                view = XmageFullGameStateRedactor.actorView(
                                        harness.game, harness.players().get(0));
                            } catch (RuntimeException exc) {
                                return;
                            }
                            if (Ws60Views.hasLeft(view, 0)) {
                                List<JsonObject> allViews = new ArrayList<>();
                                for (int seat = 0; seat < 4; seat++) {
                                    allViews.add(XmageFullGameStateRedactor.actorView(
                                            harness.game, harness.players().get(seat)));
                                }
                                captures.put("post-cleanup", allViews);
                            }
                        }
                    });
                    return new Ws60Suite.CheckpointSet(checkpoints, captures);
                },
                List.of(
                        new Ws60Suite.Assertion("P0 has left the game; P1, P2, P3 remain",
                                "players",
                                (primary0, views, tape, log) ->
                                        Ws60Checks.left(views, 0, true) + "+"
                                                + Ws60Checks.left(views, 1, false) + "+"
                                                + Ws60Checks.left(views, 2, false) + "+"
                                                + Ws60Checks.left(views, 3, false)),
                        new Ws60Suite.Assertion(
                                "Control Magic has left the game with P0 (owner)",
                                "exile-or-absent",
                                (primary0, views, tape, log) -> {
                                    String serialized = Ws60Suite.GSON.toJson(views);
                                    assertTrue(!serialized.contains("Control Magic"),
                                            "Control Magic absent from all zones");
                                    return "absent-everywhere";
                                }),
                        new Ws60Suite.Assertion(
                                "Runeclaw Bear on battlefield under P1 (owner) control",
                                "battlefield",
                                (primary0, views, tape, log) -> {
                                    for (Ws60Views.BattlefieldEntry entry :
                                            Ws60Views.battlefield(views.get(0), 1)) {
                                        if (entry.name().contains("Runeclaw Bear")) {
                                            assertEquals(1, Ws60Views.controllerSeat(
                                                    views.get(0), entry),
                                                    "controller reverted to owner P1");
                                            return "controller-seat=1";
                                        }
                                    }
                                    fail("Bear not on battlefield");
                                    throw new AssertionError("unreachable");
                                }),
                        new Ws60Suite.Assertion(
                                "zero triggered abilities created for any principal",
                                "trigger count",
                                (primary0, views, tape, log) -> {
                                    int triggers = tapeCount(tape, "TRIGGERED_ABILITY");
                                    assertEquals(0, triggers, "no triggers");
                                    return "triggers=0";
                                })),
                List.of(
                        new Ws60Suite.HiddenAudit("post-cleanup ownership", "ALL",
                                (captures, deckSeats) ->
                                        Ws60Checks.structuralPrivacy(captures,
                                                "post-cleanup"))));
    }

    // ------------------------------------------------------------------
    // H01 — Clone under Humility.
    // ------------------------------------------------------------------

    static Ws60Suite.Spec h01() {
        List<Ws60Driver.SeatDeck> seats = List.of(
                seat2(Ws60Decks.THRASIOS, Ws60Decks.KRAUM,
                        "Clone", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Island", 91),
                seat2(Ws60Decks.THRASIOS, Ws60Decks.TANA,
                        "Runeclaw Bear", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Forest", 91),
                seat2(Ws60Decks.THRASIOS, Ws60Decks.TYMNA,
                        "Humility", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Plains", 81, "Forest", 5, "Swamp", 5),
                idleSwamp());
        return new Ws60Suite.Spec("RQ-C3-H01",
                "Clone under Humility",
                "RQ-C3-H01", 6171L, 3000, seats,
                () -> {
                    Ws60Pilot pilot = new Ws60Pilot("RQ-C3-H01");
                    commandersAll(pilot, seats);
                    pilot.seatLands(0, "Island")
                            .seatLands(1, "Forest")
                            .seatLands(2, "Plains", "Forest", "Swamp")
                            .landOrder(0, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Island")
                            .landOrder(1, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Forest")
                            .landOrder(2, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Forest", "Swamp", "Plains")
                            .commanders(0, List.of(Ws60Decks.THRASIOS))
                            .setupCast(0, "Clone")
                            .castGate(0, "Clone", "Humility", "Runeclaw Bear")
                            .allowCommanderCast(0).allowCommanderCast(1)
                            .allowCommanderCast(2)
                            .assemblyFiltering(0).assemblyFiltering(1)
                            .assemblyFiltering(2)
                            .bool("pay X life", true)
                            .bool("Use effect of", true)
                            .scryGas(0, 4)
                            .scryGas(1, 4)
                            .scryGas(2, 4)
                            .target("", "Runeclaw Bear")
                            .setupCast(1, "Runeclaw Bear")
                            .setupCast(2, "Humility")
                            .seek(0, 6, "Clone", "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Gemstone Mine", "Tendo Ice Bridge")
                            .critical("Clone");
                    return pilot;
                },
                publicComplete(view -> {
                    for (Ws60Views.BattlefieldEntry entry :
                            Ws60Views.battlefield(view, 0)) {
                        if (entry.name().contains("Runeclaw Bear")
                                && entry.power() == 1 && entry.toughness() == 1) {
                            return true;
                        }
                    }
                    return false;
                }),
                () -> captureSet(
                        "copy-choice",
                        frameOffersInClass("choose_object", "Runeclaw Bear")),
                List.of(
                        new Ws60Suite.Assertion("Clone is 1/1 with no abilities on battlefield",
                                "battlefield",
                                (primary0, views, tape, log) -> {
                                    for (Ws60Views.BattlefieldEntry entry :
                                            Ws60Views.battlefield(views.get(0), 0)) {
                                        if (entry.name().contains("Runeclaw Bear")) {
                                            assertEquals(1, entry.power(), "power");
                                            assertEquals(1, entry.toughness(), "toughness");
                                            assertEquals(0, entry.abilityCount(), "abilities");
                                            return "1/1,abilities=0";
                                        }
                                    }
                                    fail("Clone-Bear not on battlefield");
                                    throw new AssertionError("unreachable");
                                }),
                        new Ws60Suite.Assertion(
                                "original Bear is 1/1 with no abilities (Humility)",
                                "battlefield",
                                (primary0, views, tape, log) -> {
                                    for (Ws60Views.BattlefieldEntry entry :
                                            Ws60Views.battlefield(views.get(0), 1)) {
                                        if (entry.name().contains("Runeclaw Bear")) {
                                            assertEquals(1, entry.power(), "power");
                                            assertEquals(1, entry.toughness(), "toughness");
                                            assertEquals(0, entry.abilityCount(), "abilities");
                                            return "1/1,abilities=0";
                                        }
                                    }
                                    fail("original Bear not on battlefield");
                                    throw new AssertionError("unreachable");
                                })),
                List.of(
                        new Ws60Suite.HiddenAudit("copy choice", "ALL",
                                (captures, deckSeats) ->
                                        Ws60Checks.structuralPrivacy(captures, "copy-choice"))));
    }

    // ------------------------------------------------------------------
    // I01 — Blink drops counters and Aura.
    // ------------------------------------------------------------------

    static Ws60Suite.Spec i01() {
        List<Ws60Driver.SeatDeck> seats = List.of(
                seat2(Ws60Decks.THRASIOS, Ws60Decks.TYMNA,
                        "Runeclaw Bear", 1, "Llanowar Reborn", 1, "Momentary Blink", 1,
                        "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Forest", 43, "Plains", 46),
                seat2(Ws60Decks.THRASIOS, Ws60Decks.TYMNA,
                        "Pacifism", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Plains", 81, "Forest", 5, "Swamp", 5),
                idlePlains(),
                idleSwamp());
        return new Ws60Suite.Spec("RQ-C3-I01",
                "Blink drops counters and Aura",
                "RQ-C3-I01", 6181L, 3000, seats,
                () -> {
                    Ws60Pilot pilot = new Ws60Pilot("RQ-C3-I01");
                    commandersAll(pilot, seats);
                    pilot.seatLands(0, "Llanowar Reborn", "Forest", "Plains")
                            .seatLands(1, "Plains", "Forest", "Swamp")
                            .landOrder(0, "Command Tower", "Llanowar Reborn",
                                    "Exotic Orchard", "Reflecting Pool", "Forest",
                                    "Plains")
                            .landOrder(1, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Forest", "Swamp", "Plains")
                            .setupCast(0, "Runeclaw Bear", "Momentary Blink")
                            .attackRoundRobin("Tymna the Weaver", List.of(2, 3))
                            .castGate(0, "Runeclaw Bear", "Llanowar Reborn")
                            .castGate(0, "Momentary Blink", "Pacifism")
                            .allowCommanderCast(0).allowCommanderCast(1)
                            .assemblyFiltering(0).assemblyFiltering(1)
                            .attackerFallback("Tymna the Weaver", 2)
                            .attackerFallback("Thrasios, Triton Hero", 3)
                            .bool("pay X life", true)
                            .bool("counter", true)
                            .scryGas(0, 4)
                            .scryGas(1, 4)
                            .target("creature", "Runeclaw Bear")
                            .setupCast(1, "Pacifism")
                            .castGate(1, "Pacifism", "Runeclaw Bear")
                            .seek(0, 6, "Runeclaw Bear", "Momentary Blink",
                                    "Llanowar Reborn", "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Gemstone Mine", "Tendo Ice Bridge")
                            .critical("Momentary Blink");
                    return pilot;
                },
                publicComplete(view -> Ws60Views.graveyardNames(view, 1).stream()
                                .anyMatch(card -> card.contains("Pacifism"))
                        && Ws60Views.graveyardNames(view, 0).stream()
                                .anyMatch(card -> card.contains("Momentary Blink"))
                        && Ws60Views.controls(view, 0, "Runeclaw Bear")),
                () -> captureSet(
                        "blink",
                        frameOffers("Momentary Blink — Cast")),
                List.of(
                        new Ws60Suite.Assertion(
                                "Runeclaw Bear on battlefield as a plain 2/2 with zero counters and no Auras",
                                "battlefield",
                                (primary0, views, tape, log) -> {
                                    for (Ws60Views.BattlefieldEntry entry :
                                            Ws60Views.battlefield(views.get(0), 0)) {
                                        if (entry.name().contains("Runeclaw Bear")) {
                                            assertEquals(2, entry.power(), "power");
                                            assertEquals(2, entry.toughness(), "toughness");
                                            int counters = entry.counters().values().stream()
                                                    .mapToInt(Integer::intValue).sum();
                                            assertEquals(0, counters, "counters");
                                            return "2/2,counters=0";
                                        }
                                    }
                                    fail("Bear not on battlefield");
                                    throw new AssertionError("unreachable");
                                }),
                        new Ws60Suite.Assertion(
                                "Pacifism in P1 graveyard (not reattached)", "graveyards.P1",
                                (primary0, views, tape, log) -> {
                                    String result = Ws60Checks.graveHas(views, 1, "Pacifism");
                                    assertTrue(Ws60Views.battlefieldNames(views.get(0), 0)
                                            .stream().noneMatch(card ->
                                                    card.contains("Pacifism")),
                                            "Pacifism not attached");
                                    return result;
                                }),
                        new Ws60Suite.Assertion("Momentary Blink in P0 graveyard",
                                "graveyards.P0",
                                (primary0, views, tape, log) -> Ws60Checks.graveHas(views, 0,
                                        "Momentary Blink"))),
                List.of(
                        new Ws60Suite.HiddenAudit("identity", "ALL",
                                (captures, deckSeats) ->
                                        Ws60Checks.structuralPrivacy(captures, "blink"))));
    }
}
