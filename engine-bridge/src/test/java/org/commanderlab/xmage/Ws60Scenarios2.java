package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import java.util.ArrayList;
import java.util.List;

import static org.commanderlab.xmage.Ws60Scenarios.*;
import static org.junit.jupiter.api.Assertions.assertTrue;
/**
 * WS60 RQ-C3 first-wave scenario specifications, part 2 (C01, C03, D06).
 */
final class Ws60Scenarios2 {

    private Ws60Scenarios2() {
    }

    // ------------------------------------------------------------------
    // C01 — Force of Will pitch versus hard-cast.
    // ------------------------------------------------------------------

    static Ws60Suite.Spec c01() {
        List<Ws60Driver.SeatDeck> seats = List.of(
                seat2(Ws60Decks.THRASIOS, Ws60Decks.KRAUM,
                        "Force of Will", 1, "Turn to Frog", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Island", 75, "Forest", 15),
                seat2(Ws60Decks.THRASIOS, Ws60Decks.TYMNA,
                        "Llanowar Elves", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Forest", 71, "Plains", 10, "Swamp", 10),
                idlePlains(),
                idleSwamp());
        return new Ws60Suite.Spec("RQ-C3-C01",
                "Force of Will pitch versus hard-cast (corrected: blue nonland pitch + 5-Island mana)",
                "RQ-C3-C01", 6121L, 6000, seats,
                () -> {
                    Ws60Pilot pilot = new Ws60Pilot("RQ-C3-C01");
                    commandersAll(pilot, seats);
                    pilot.seatLands(0, "Island", "Forest")
                            .seatLands(1, "Forest", "Plains", "Swamp")
                            .landOrder(0, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Forest", "Island")
                            .landOrder(1, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Plains", "Swamp", "Forest")
                            .commanders(0, List.of(Ws60Decks.THRASIOS))
                            // P0 filters tap-safely (Islands pristine for the
                            // answer) and holds once both pieces are secured.
                            .setupCast(0, "Force of Will")
                            .stackGate(0, "Force of Will", "Llanowar Elves")
                            .holdForAnswer(0, "Force of Will", "Turn to Frog")
                            .reserveTaps(0, "Island")
                            .filterMaxPerTurn(0, 4)
                            .filterMinUntapped(0, 3)
                            // P1 must find its own 1-of Elves by turn 65: same
                            // filter cap plus scry-digging (Thrasios reveals are
                            // 96% lands-to-battlefield, so the scry bottoms do
                            // the finding). Tymna draws auto-decline once P1
                            // secures Elves (secured mill guard).
                            .filterMaxPerTurn(1, 3)
                            .scryGas(1, 4)
                            .choice("alternative cost", "exile")
                            .allowCommanderCast(0).allowCommanderCast(1)
                            .assemblyFiltering(0).assemblyFiltering(1)
                            .attackerFallback("Thrasios, Triton Hero", 2)
                            .fallbackExcludeSeats(0)
                            .attackRoundRobin("Tymna the Weaver", List.of(2, 3))
                            .bool("pay X life", true)
                            .scryGas(0, 4)
                            .handPick("blue card from your hand", "Turn to Frog")
                            .target("", "Llanowar Elves")
                            .secureWhen(1, "Llanowar Elves")
                            .setupCast(1, "Llanowar Elves")
                            .turnGate(1, "Llanowar Elves", 65)
                            // Hard-seek both 1-of assembly pieces (opener piece
                            // plus scry-dug draws); fixing-seek keeps would stop
                            // mulligans before the pieces are found, and the old
                            // diluted seeks decked all four seats by turn ~124
                            // without ever meeting.
                            .seek(0, 6, "Force of Will", "Turn to Frog")
                            .seek(1, 6, "Llanowar Elves")
                            .critical("Force of Will")
                            .critical("blue card from your hand");
                    return pilot;
                },
                publicComplete(view -> Ws60Views.graveyardNames(view, 1).stream()
                                .anyMatch(card -> card.contains("Llanowar Elves"))
                        && Ws60Views.graveyardNames(view, 0).stream()
                                .anyMatch(card -> card.contains("Force of Will"))
                        && Ws60Views.life(view, 0) == 39),
                () -> captureSet(
                        "pitch-selection",
                        // Pitch exile arrives as choose_object (cost payment),
                        // not target: accept either engine rendering.
                        frameIsAny(List.of("target", "choose_object"),
                                "blue card from your hand"),
                        "cost-choice",
                        frameIs("choice", "Force of Will")),
                List.of(
                        new Ws60Suite.Assertion("P0 life is 39", "life",
                                (primary0, views, tape, log) -> Ws60Checks.lifeIs(views, 0, 39)),
                        new Ws60Suite.Assertion(
                                "Turn to Frog (blue nonland) from P0 hand is in exile; Force of Will in P0 graveyard",
                                "exile",
                                (primary0, views, tape, log) -> {
                                    List<String> exile = Ws60Views.exileNames(views.get(0), 0);
                                    assertTrue(exile.stream()
                                            .anyMatch(card -> card.contains("Turn to Frog")),
                                            "Frog exiled: " + exile);
                                    return Ws60Checks.graveHas(views, 0, "Force of Will")
                                            + ";exile0=" + exile;
                                }),
                        new Ws60Suite.Assertion(
                                "Llanowar Elves spell countered to P1 graveyard (never entered)",
                                "graveyards.P1",
                                (primary0, views, tape, log) -> {
                                    String result = Ws60Checks.graveHas(views, 1,
                                            "Llanowar Elves");
                                    assertTrue(Ws60Views.battlefieldNames(views.get(0), 1)
                                            .stream().noneMatch(card ->
                                                    card.contains("Llanowar Elves")),
                                            "Elves must never have entered");
                                    return result + ";never-entered";
                                })),
                List.of(
                        new Ws60Suite.HiddenAudit("pitch selection (hidden-zone decision)",
                                "P0",
                                (captures, deckSeats) -> Ws60Checks.nameAbsentFor(captures,
                                        "pitch-selection", 0, "Turn to Frog")),
                        new Ws60Suite.HiddenAudit("pitch selection owner visibility", "P0",
                                (captures, deckSeats) -> Ws60Checks.namePresentFor(captures,
                                        "pitch-selection", 0, "Turn to Frog")),
                        new Ws60Suite.HiddenAudit("stack knowledge", "ALL",
                                (captures, deckSeats) -> Ws60Checks.structuralPrivacy(captures,
                                        "cost-choice"))));
    }

    // ------------------------------------------------------------------
    // C03 — Fireball X with per-target increase.
    // ------------------------------------------------------------------

    static Ws60Suite.Spec c03() {
        List<Ws60Driver.SeatDeck> seats = List.of(
                seat2(Ws60Decks.THRASIOS, Ws60Decks.ROGRAKH,
                        "Fireball", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Mountain", 86, "Forest", 5),
                idleMountain(), idlePlains(), idleSwamp());
        return new Ws60Suite.Spec("RQ-C3-C03",
                "Fireball X with per-target increase",
                "RQ-C3-C03", 6123L, 3000, seats,
                () -> {
                    Ws60Pilot pilot = new Ws60Pilot("RQ-C3-C03");
                    commandersAll(pilot, seats);
                    pilot.seatLands(0, "Mountain", "Forest")
                            .landOrder(0, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Forest", "Mountain")
                            .setupCast(0, "Fireball")
                            .ownCountGate(0, "Fireball", "Mountain", 7)
                            .allowCommanderCast(0).assemblyFiltering(0)
                            .attackerFallback("Thrasios, Triton Hero", 3)
                            .bool("pay X life", true)
                            .numeric("Fireball", 5)
                            .sequentialTargets("", List.of("WS52 Seat 2", "WS52 Seat 3"))
                            .seek(0, 6, "Fireball", "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Gemstone Mine", "Tendo Ice Bridge")
                            .critical("Fireball");
                    return pilot;
                },
                publicComplete(view -> Ws60Views.life(view, 1) == 38
                        && Ws60Views.life(view, 2) == 38
                        && Ws60Views.graveyardNames(view, 0).stream()
                                .anyMatch(card -> card.contains("Fireball"))),
                () -> captureSet(
                        "cast",
                        frameOffers("Fireball — Cast Fireball")),
                List.of(
                        new Ws60Suite.Assertion(
                                "P1 and P2 life are 38 each (remainder discarded, not assigned)",
                                "life",
                                (primary0, views, tape, log) ->
                                        Ws60Checks.lifeIs(views, 1, 38) + "+"
                                                + Ws60Checks.lifeIs(views, 2, 38)),
                        new Ws60Suite.Assertion("Fireball in P0 graveyard", "graveyards.P0",
                                (primary0, views, tape, log) ->
                                        Ws60Checks.graveHas(views, 0, "Fireball"))),
                List.of(
                        new Ws60Suite.HiddenAudit("division", "ALL",
                                (captures, deckSeats) ->
                                        Ws60Checks.structuralPrivacy(captures, "cast"))));
    }

    // ------------------------------------------------------------------
    // D06 — Casualties of War choose one or more (AG-2 governed).
    // ------------------------------------------------------------------

    static Ws60Suite.Spec d06() {
        List<Ws60Driver.SeatDeck> seats = List.of(
                seat2(Ws60Decks.THRASIOS, Ws60Decks.TYMNA,
                        "Casualties of War", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "City of Brass", 1, "Mana Confluence", 1,
                        "Swamp", 54, "Plains", 25, "Island", 10),
                seat2(Ws60Decks.THRASIOS, Ws60Decks.TYMNA,
                        "Ornithopter", 1, "Runeclaw Bear", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Forest", 70, "Plains", 10, "Swamp", 10),
                idlePlains(),
                idleSwamp());
        return new Ws60Suite.Spec("RQ-C3-D06",
                "Casualties of War choose one or more",
                "RQ-C3-D06", 6136L, 4000, seats,
                () -> {
                    Ws60Pilot pilot = new Ws60Pilot("RQ-C3-D06");
                    commandersAll(pilot, seats);
                    pilot.seatLands(0, "Swamp", "Plains", "City of Brass",
                                    "Mana Confluence", "Island")
                            .seatLands(1, "Forest")
                            .landOrder(0, "Command Tower", "Island", "Exotic Orchard",
                                    "Reflecting Pool", "City of Brass", "Mana Confluence",
                                    "Plains", "Swamp")
                            .seatLands(1, "Forest")
                            .landOrder(0, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "City of Brass", "Mana Confluence",
                                    "Plains", "Swamp")
                            .landOrder(1, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Forest")
                            .secureWhen(0, "Casualties of War")
                            .setupCast(0, "Casualties of War")
                            .castGate(0, "Casualties of War", "Ornithopter", "Runeclaw Bear")
                            .allowCommanderCast(0).allowCommanderCast(1)
                            .assemblyFiltering(0).assemblyFiltering(1)
                            .filterMaxPerTurn(1, 1)
                            .attackRoundRobin("Tymna the Weaver", List.of(2, 3))
                            .attackRoundRobin("Thrasios, Triton Hero", List.of(2, 3))
                            .bool("pay X life", true)
                            .scryGas(0, 4)
                            .scryGas(1, 4)
                            .modes("artifact", "creature", "land")
                            .target("artifact", "Ornithopter")
                            .target("creature", "Runeclaw Bear")
                            .target("land", "Forest")
                            .secureWhen(1, "Ornithopter", "Runeclaw Bear")
                            .setupCast(1, "Ornithopter", "Runeclaw Bear")
                            .seek(0, 6, "Casualties of War",
                                    "Command Tower", "Exotic Orchard", "Reflecting Pool",
                                    "Gemstone Mine", "Tendo Ice Bridge", "Island")
                            .critical("mode")
                            .critical("Casualties of War");
                    return pilot;
                },
                publicComplete(view -> Ws60Views.graveyardNames(view, 1).stream()
                                .anyMatch(card -> card.contains("Ornithopter"))
                        && Ws60Views.graveyardNames(view, 1).stream()
                                .anyMatch(card -> card.contains("Runeclaw Bear"))
                        && Ws60Views.graveyardNames(view, 0).stream()
                                .anyMatch(card -> card.contains("Casualties of War"))),
                () -> captureSet(
                        "modes",
                        frameIs("mode", "Casualties of War")),
                List.of(
                        new Ws60Suite.Assertion(
                                "Ornithopter, Runeclaw Bear in graveyards; one P1 Forest in graveyard",
                                "graveyards",
                                (primary0, views, tape, log) -> {
                                    String result = Ws60Checks.graveHas(views, 1, "Ornithopter")
                                            + "+" + Ws60Checks.graveHas(views, 1,
                                                    "Runeclaw Bear");
                                    List<String> grave = Ws60Views.graveyardNames(
                                            views.get(0), 1);
                                    long forests = grave.stream()
                                            .filter(card -> card.contains("Forest")).count();
                                    assertTrue(forests >= 1,
                                            "P1 Forest destroyed: " + grave);
                                    return result + "+forests=" + forests;
                                }),
                        new Ws60Suite.Assertion("Casualties of War in P0 graveyard",
                                "graveyards.P0",
                                (primary0, views, tape, log) -> Ws60Checks.graveHas(views, 0,
                                        "Casualties of War"))),
                List.of(
                        new Ws60Suite.HiddenAudit("mode legality", "ALL",
                                (captures, deckSeats) ->
                                        Ws60Checks.structuralPrivacy(captures, "modes"))));
    }
}
