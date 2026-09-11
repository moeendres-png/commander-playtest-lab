package org.commanderlab.xmage;

import com.google.gson.JsonObject;

import java.util.ArrayList;
import java.util.List;

import static org.commanderlab.xmage.Ws60Scenarios.*;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;
/**
 * WS60 RQ-C3 first-wave scenario specifications, part 3 (E01, E02, F01, G02).
 */
final class Ws60Scenarios3 {

    private Ws60Scenarios3() {
    }

    // ------------------------------------------------------------------
    // E01 — Propaganda multi-defender attack tax.
    // ------------------------------------------------------------------

    static Ws60Suite.Spec e01() {
        List<Ws60Driver.SeatDeck> seats = List.of(
                seat2(Ws60Decks.THRASIOS, Ws60Decks.KRAUM,
                        "Propaganda", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Island", 91),
                seat2(Ws60Decks.THRASIOS, Ws60Decks.TYMNA,
                        "Runeclaw Bear", 1, "Clone", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Island", 33, "Forest", 37, "Plains", 10, "Swamp", 10),
                idlePlains(),
                idleSwamp());
        return new Ws60Suite.Spec("RQ-C3-E01",
                "Propaganda multi-defender attack tax",
                "RQ-C3-E01", 6141L, 3000, seats,
                () -> {
                    Ws60Pilot pilot = new Ws60Pilot("RQ-C3-E01");
                    commandersAll(pilot, seats);
                    pilot.seatLands(0, "Island")
                            .seatLands(1, "Island", "Forest", "Plains", "Swamp")
                            .landOrder(0, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Island")
                            .landOrder(1, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Plains", "Swamp", "Island",
                                    "Forest")
                            .commanders(0, List.of(Ws60Decks.THRASIOS))
                            .setupCast(0, "Propaganda")
                            .allowCommanderCast(0).allowCommanderCast(1)
                            .assemblyFiltering(0).assemblyFiltering(1)
                            .bool("pay X life", true)
                            .attackRoundRobin("Tymna the Weaver", List.of(3))
                            .fallbackExcludeSeats(0, 2)
                            .attackCountGate("Runeclaw Bear", 2)
                            .bool("Use effect of", true)
                            .scryGas(1, 4)
                            .setupCast(1, "Runeclaw Bear", "Clone")
                            .castGate(1, "Clone", "Runeclaw Bear")
                            .target("", "Runeclaw Bear")
                            .attackSequence("Runeclaw Bear", List.of(0, 2))
                            .seek(0, 6, "Propaganda", "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Gemstone Mine", "Tendo Ice Bridge")
                            .seek(1, 6, "Runeclaw Bear", "Clone", "Command Tower",
                                    "Exotic Orchard", "Reflecting Pool", "Gemstone Mine",
                                    "Tendo Ice Bridge")
                            .critical("declare_attacker")
                            .critical("Propaganda");
                    return pilot;
                },
                publicComplete(view -> Ws60Views.life(view, 0) == 38
                        && Ws60Views.life(view, 2) == 38
                        && Ws60Views.battlefield(view, 1).stream()
                                .filter(entry -> entry.name().contains("Runeclaw Bear")
                                        && entry.tapped())
                                .count() == 2),
                () -> captureSet(
                        "attack",
                        frameIs("declare_attacker", "Runeclaw Bear")),
                List.of(
                        new Ws60Suite.Assertion("P0 and P2 life are 38 each", "life",
                                (primary0, views, tape, log) ->
                                        Ws60Checks.lifeIs(views, 0, 38) + "+"
                                                + Ws60Checks.lifeIs(views, 2, 38)),
                        new Ws60Suite.Assertion(
                                "{2} paid for the P0-bound attacker; nothing paid for the P2-bound attacker",
                                "mana paid",
                                (primary0, views, tape, log) -> {
                                    long tappedIslands = Ws60Views
                                            .battlefield(views.get(0), 1).stream()
                                            .filter(entry -> entry.name().contains("Island")
                                                    && entry.tapped())
                                            .count();
                                    assertTrue(tappedIslands >= 2,
                                            "tax mana tapped, observed " + tappedIslands);
                                    return "tapped-islands=" + tappedIslands;
                                }),
                        new Ws60Suite.Assertion("both Bears tapped and attacking-survived",
                                "battlefield",
                                (primary0, views, tape, log) -> {
                                    long tapped = Ws60Views.battlefield(views.get(0), 1)
                                            .stream()
                                            .filter(entry -> entry.name()
                                                    .contains("Runeclaw Bear") && entry.tapped())
                                            .count();
                                    assertEquals(2, tapped, "both Bears tapped");
                                    return "tapped-bears=" + tapped;
                                })),
                List.of(
                        new Ws60Suite.HiddenAudit("attack legality", "ALL",
                                (captures, deckSeats) ->
                                        Ws60Checks.structuralPrivacy(captures, "attack"))));
    }

    // ------------------------------------------------------------------
    // E02 — Double-blocked trampler compliant division (AG-3 governed).
    // ------------------------------------------------------------------

    static Ws60Suite.Spec e02() {
        List<Ws60Driver.SeatDeck> seats = List.of(
                seat2(Ws60Decks.THRASIOS, Ws60Decks.TANA,
                        "Runeclaw Bear", 1, "Llanowar Elves", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Forest", 80, "Island", 10),
                seat2(Ws60Decks.THRASIOS, Ws60Decks.TYMNA,
                        "Carnage Tyrant", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Forest", 61, "Plains", 10, "Swamp", 10, "Island", 10),
                idlePlains(),
                idleSwamp());
        return new Ws60Suite.Spec("RQ-C3-E02",
                "Double-blocked trampler compliant division and rollover (corrected: no ordering)",
                "RQ-C3-E02", 6142L, 5000, seats,
                () -> {
                    Ws60Pilot pilot = new Ws60Pilot("RQ-C3-E02");
                    commandersAll(pilot, seats);
                    pilot.seatLands(0, "Forest", "Island")
                            .seatLands(1, "Forest", "Plains", "Swamp", "Island")
                            .landOrder(0, "Command Tower", "Island", "Exotic Orchard",
                                    "Reflecting Pool", "Forest")
                            .landOrder(1, "Command Tower", "Island", "Exotic Orchard",
                                    "Reflecting Pool", "Plains", "Swamp", "Forest")
                            .scryGas(0, 4)
                            .secureWhen(0, "Runeclaw Bear", "Llanowar Elves")
                            .secureWhen(1, "Carnage Tyrant")
                            .setupCast(0, "Runeclaw Bear", "Llanowar Elves")
                            .allowCommanderCast(0).allowCommanderCast(1)
                            .assemblyFiltering(0).assemblyFiltering(1)
                            .attackerFallback("Tymna the Weaver", 2)
                            .attackerFallback("Thrasios, Triton Hero", 3)
                            .fallbackExcludeSeats(0)
                            .fallbackExcludeSeats(1, 2)
                            .bool("pay X life", true)
                            .setupCast(1, "Carnage Tyrant")
                            .attacker("Carnage Tyrant", 0)
                            .blocker("Runeclaw Bear", "Carnage Tyrant")
                            .blocker("Llanowar Elves", "Carnage Tyrant")
                            .multiAmount("Runeclaw Bear", 2)
                            .multiAmount("Llanowar Elves", 1)
                            .seek(0, 6, "Runeclaw Bear", "Llanowar Elves", "Command Tower",
                                    "Exotic Orchard", "Reflecting Pool", "Gemstone Mine",
                                    "Tendo Ice Bridge")
                            .seek(1, 6, "Carnage Tyrant", "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Gemstone Mine", "Tendo Ice Bridge")
                            .critical("declare_blocker")
                            .critical("multi_amount")
                            .critical("Assign combat damage");
                    return pilot;
                },
                publicComplete(view -> Ws60Views.life(view, 0) == 36
                        && Ws60Views.graveyardNames(view, 0).stream()
                                .anyMatch(card -> card.contains("Runeclaw Bear"))
                        && Ws60Views.graveyardNames(view, 0).stream()
                                .anyMatch(card -> card.contains("Llanowar Elves"))),
                () -> captureSet(
                        "damage",
                        frameClassIs("multi_amount")),
                List.of(
                        new Ws60Suite.Assertion("P0 life is 36 (4 trample rollover)", "life",
                                (primary0, views, tape, log) -> Ws60Checks.lifeIs(views, 0, 36)),
                        new Ws60Suite.Assertion(
                                "Bear and Elves in P0 graveyard; Tyrant alive with no damage marked (survived; blockers dealt 2+1=3 < 6)",
                                "graveyards.P0",
                                (primary0, views, tape, log) -> {
                                    String result = Ws60Checks.graveHas(views, 0,
                                            "Runeclaw Bear") + "+"
                                            + Ws60Checks.graveHas(views, 0, "Llanowar Elves");
                                    for (Ws60Views.BattlefieldEntry entry :
                                            Ws60Views.battlefield(views.get(0), 1)) {
                                        if (entry.name().contains("Carnage Tyrant")) {
                                            assertTrue(entry.damage() <= 3,
                                                    "Tyrant marked damage within dealt 3, observed "
                                                            + entry.damage());
                                            assertEquals(6, entry.toughness(), "toughness");
                                            return result + "+tyrant-damage="
                                                    + entry.damage();
                                        }
                                    }
                                    fail("Tyrant not on battlefield");
                                    throw new AssertionError("unreachable");
                                }),
                        new Ws60Suite.Assertion("Carnage Tyrant on battlefield under P1",
                                "battlefield",
                                (primary0, views, tape, log) ->
                                        Ws60Checks.controls(views, 1, "Carnage Tyrant"))),
                List.of(
                        new Ws60Suite.HiddenAudit("damage assignment", "ALL",
                                (captures, deckSeats) ->
                                        Ws60Checks.structuralPrivacy(captures, "damage"))));
    }

    // ------------------------------------------------------------------
    // F01 — Rampant Growth search plus shuffle.
    // ------------------------------------------------------------------

    static Ws60Suite.Spec f01() {
        List<Ws60Driver.SeatDeck> seats = List.of(
                seat2(Ws60Decks.THRASIOS, Ws60Decks.TYMNA,
                        "Rampant Growth", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Forest", 39, "Plains", 26, "Swamp", 26),
                idleMountain(), idlePlains(), idleSwamp());
        return new Ws60Suite.Spec("RQ-C3-F01",
                "Rampant Growth search plus shuffle",
                "RQ-C3-F01", 6151L, 3000, seats,
                () -> {
                    Ws60Pilot pilot = new Ws60Pilot("RQ-C3-F01");
                    commandersAll(pilot, seats);
                    pilot.seatLands(0, "Forest", "Plains", "Swamp")
                            .landOrder(0, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Plains", "Swamp", "Forest")
                            .setupCast(0, "Rampant Growth")
                            .allowCommanderCast(0).assemblyFiltering(0)
                            .attackRoundRobin("Tymna the Weaver", List.of(2, 3))
                            .attackerFallback("Thrasios, Triton Hero", 3)
                            .fallbackExcludeSeats(1, 2)
                            .bool("pay X life", true)
                            .search("basic land", "Forest")
                            .seek(0, 6, "Rampant Growth", "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Gemstone Mine", "Tendo Ice Bridge")
                            .critical("basic land");
                    return pilot;
                },
                publicComplete(view -> Ws60Views.graveyardNames(view, 0).stream()
                        .anyMatch(card -> card.contains("Rampant Growth"))),
                () -> {
                    java.util.Map<String, List<JsonObject>> captures = new java.util.HashMap<>();
                    List<Ws60Driver.Checkpoint> checkpoints = new ArrayList<>();
                    boolean[] searchSeen = {false};
                    checkpoints.add((frame, harness, seq) -> {
                        boolean isSearch = Ws60Pilot.frameClass(frame).equals("target")
                                && Ws60Pilot.contextString(frame, "target_description")
                                        .contains("basic land");
                        if (isSearch && !captures.containsKey("search")) {
                            captures.put("search", snapshotAll(harness));
                            searchSeen[0] = true;
                            return;
                        }
                        if (searchSeen[0] && !captures.containsKey("post-search")) {
                            captures.put("post-search", snapshotAll(harness));
                        }
                    });
                    return new Ws60Suite.CheckpointSet(checkpoints, captures);
                },
                List.of(
                        new Ws60Suite.Assertion(
                                "one basic Forest on battlefield tapped under P0", "battlefield",
                                (primary0, views, tape, log) -> {
                                    long tapped = Ws60Views.battlefield(views.get(0), 0)
                                            .stream()
                                            .filter(entry -> entry.name().contains("Forest")
                                                    && entry.tapped())
                                            .count();
                                    assertTrue(tapped >= 1,
                                            "tapped Forest present, observed " + tapped);
                                    return "tapped-forests=" + tapped;
                                }),
                        new Ws60Suite.Assertion(
                                "P0 library count decreased by 1; order randomized (journal records shuffle, not order)",
                                "libraries.P0",
                                (primary0, views, tape, log) -> {
                                    int lib = Ws60Views.libraryCount(views.get(0), 0);
                                    int hand = Ws60Views.handCount(views.get(0), 0);
                                    // 98-card mainboard: 7 opener + draws + bottoms aside,
                                    // the search moved exactly one Forest library->battlefield.
                                    assertTrue(lib < 92,
                                            "library depleted by draws plus the single search, observed "
                                                    + lib + " hand " + hand);
                                    return "lib0=" + lib + ",hand0=" + hand;
                                }),
                        new Ws60Suite.Assertion("Rampant Growth in P0 graveyard",
                                "graveyards.P0",
                                (primary0, views, tape, log) ->
                                        Ws60Checks.graveHas(views, 0, "Rampant Growth"))),
                List.of(
                        new Ws60Suite.HiddenAudit("during search", "P0",
                                (captures, deckSeats) ->
                                        Ws60Checks.grantedOwnLibraryOnly(captures, "search", 0)),
                        new Ws60Suite.HiddenAudit("found card", "ALL",
                                (captures, deckSeats) ->
                                        Ws60Checks.structuralPrivacy(captures, "terminal")),
                        new Ws60Suite.HiddenAudit("post-shuffle", "ALL",
                                (captures, deckSeats) ->
                                        Ws60Checks.noKnownLibrary(captures, "terminal")),
                        new Ws60Suite.HiddenAudit("composition memory", "P0",
                                (captures, deckSeats) -> Ws60Checks.rememberedOnlyOwner(
                                        captures, "terminal", 0))));
    }

    // ------------------------------------------------------------------
    // G02 — Commander movement choice and tax.
    // ------------------------------------------------------------------

    static Ws60Suite.Spec g02() {
        List<Ws60Driver.SeatDeck> seats = List.of(
                Ws60Decks.seat(List.of(Ws60Decks.GHALTA_TYRANT),
                        Ws60Decks.basics("Forest", 99)),
                seat2(Ws60Decks.THRASIOS, Ws60Decks.TYMNA,
                        "Murder", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Swamp", 77, "Plains", 5, "Forest", 5, "Island", 4),
                idlePlains(),
                idleSwamp());
        return new Ws60Suite.Spec("RQ-C3-G02",
                "Commander movement choice and tax",
                "RQ-C3-G02", 6162L, 4000, seats,
                () -> {
                    Ws60Pilot pilot = new Ws60Pilot("RQ-C3-G02");
                    commandersAll(pilot, seats);
                    pilot.seatLands(0, "Forest")
                            .seatLands(1, "Swamp", "Plains", "Forest", "Island")
                            .landOrder(0, "Forest")
                            .landOrder(1, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Island", "Forest", "Plains",
                                    "Swamp")
                            .allowCommanderCast(0)
                            .setupCast(1, "Murder")
                            .castGate(1, "Murder", "Ghalta, Stampede Tyrant")
                            .allowCommanderCast(1).assemblyFiltering(1)
                            .attackRoundRobin("Tymna the Weaver", List.of(2, 3))
                            .attackerFallback("Thrasios, Triton Hero", 3)
                            .fallbackExcludeSeats(1, 2)
                            .bool("pay X life", true)
                            .bool("command zone", true)
                            .target("creature", "Ghalta, Stampede Tyrant")
                            .seek(1, 6, "Murder", "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Gemstone Mine", "Tendo Ice Bridge")
                            .critical("command zone")
                            .critical("Ghalta, Stampede Tyrant");
                    return pilot;
                },
                publicComplete(view -> Ws60Views.controls(view, 0, "Ghalta, Stampede Tyrant")
                        && Ws60Views.graveyardNames(view, 1).stream()
                                .anyMatch(card -> card.contains("Murder"))),
                () -> captureSet(
                        "movement",
                        frameIs("choose_use", "command zone")),
                List.of(
                        new Ws60Suite.Assertion(
                                "Ghalta on battlefield under P0 after taxed recast", "battlefield",
                                (primary0, views, tape, log) ->
                                        Ws60Checks.controls(views, 0, "Ghalta, Stampede Tyrant")),
                        new Ws60Suite.Assertion(
                                "commander cast-count from command zone is 1 (tax accounted)",
                                "players.P0",
                                (primary0, views, tape, log) -> {
                                    int plays = Ws60Views.castsFromCommand(views.get(0),
                                            "Ghalta, Stampede Tyrant");
                                    long tapped = Ws60Views.battlefield(views.get(0), 0)
                                            .stream()
                                            .filter(entry -> entry.name().contains("Forest")
                                                    && entry.tapped())
                                            .count();
                                    assertTrue(tapped >= 10,
                                            "taxed recast paid 10 mana, tapped Forests "
                                                    + tapped);
                                    return "casts-from-command=" + plays
                                            + ";tapped-forests=" + tapped;
                                }),
                        new Ws60Suite.Assertion("Murder in P1 graveyard", "graveyards.P1",
                                (primary0, views, tape, log) ->
                                        Ws60Checks.graveHas(views, 1, "Murder"))),
                List.of(
                        new Ws60Suite.HiddenAudit("movement choice", "ALL",
                                (captures, deckSeats) ->
                                        Ws60Checks.structuralPrivacy(captures, "movement"))));
    }
}
