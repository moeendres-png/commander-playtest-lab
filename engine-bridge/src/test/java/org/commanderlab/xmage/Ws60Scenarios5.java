package org.commanderlab.xmage;

import com.google.gson.JsonObject;

import java.util.List;

import static org.commanderlab.xmage.Ws60Scenarios.*;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;
/**
 * WS60 RQ-C3 first-wave scenario specifications, part 5 (B01 bounded attempt, J02).
 */
final class Ws60Scenarios5 {

    private Ws60Scenarios5() {
    }

    // ------------------------------------------------------------------
    // B01 — Five Wardens trigger across four players (bounded attempt).
    //
    // Structural note: P0 must control two Soul Wardens under Commander
    // singleton, so the second arrives as a Cackling Counterpart token; and
    // every native Warden entry fires entry triggers, so the fixture's
    // nominal-40 lives are unreachable natively. This spec attempts honest
    // native assembly within bounds and records the outcome; the verdict is
    // expected UNKNOWN with a precise blocker (see evidence rationale).
    // ------------------------------------------------------------------

    static Ws60Suite.Spec b01() {
        List<Ws60Driver.SeatDeck> seats = List.of(
                seat2(Ws60Decks.THRASIOS, Ws60Decks.TYMNA,
                        "Soul Warden", 1, "Cackling Counterpart", 1, "Llanowar Elves", 1,
                        "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Plains", 41, "Island", 22, "Forest", 21, "Swamp", 5),
                seat2(Ws60Decks.THRASIOS, Ws60Decks.TYMNA,
                        "Soul Warden", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Plains", 91),
                seat2(Ws60Decks.THRASIOS, Ws60Decks.TYMNA,
                        "Soul Warden", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Plains", 91),
                seat2(Ws60Decks.THRASIOS, Ws60Decks.TYMNA,
                        "Soul Warden", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Plains", 91));
        return new Ws60Suite.Spec("RQ-C3-B01",
                "Five Wardens trigger across four players",
                "RQ-C3-B01", 6110L, 3000, seats,                () -> {
                    Ws60Pilot pilot = new Ws60Pilot("RQ-C3-B01");
                    commandersAll(pilot, seats);
                    pilot.seatLands(0, "Plains", "Island", "Forest", "Swamp")
                            .seatLands(1, "Plains")
                            .seatLands(2, "Plains")
                            .seatLands(3, "Plains")
                            .landOrder(0, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Swamp", "Forest", "Island",
                                    "Plains")
                            .landOrder(1, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Plains")
                            .landOrder(2, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Plains")
                            .landOrder(3, "Command Tower", "Exotic Orchard",
                                    "Reflecting Pool", "Plains")
                            .setupCast(0, "Soul Warden", "Cackling Counterpart",
                                    "Llanowar Elves")
                            .castGate(0, "Cackling Counterpart", "Soul Warden")
                            .countGate(0, "Llanowar Elves", "Soul Warden", 5)
                            .allowCommanderCast(0).allowCommanderCast(1)
                            .allowCommanderCast(2).allowCommanderCast(3)
                            .assemblyFiltering(0).assemblyFiltering(1)
                            .assemblyFiltering(2).assemblyFiltering(3)
                            .bool("pay X life", true)
                            .target("creature", "Soul Warden")
                            .setupCast(1, "Soul Warden")
                            .setupCast(2, "Soul Warden")
                            .setupCast(3, "Soul Warden")
                            .seek(0, 6, "Soul Warden", "Cackling Counterpart",
                                    "Llanowar Elves")
                            .seek(1, 6, "Soul Warden")
                            .seek(2, 6, "Soul Warden")
                            .seek(3, 6, "Soul Warden")
                            .critical("Soul Warden");
                    return pilot;
                },
                publicComplete(view -> Ws60Views.life(view, 0) == 42
                        && Ws60Views.life(view, 1) == 41
                        && Ws60Views.life(view, 2) == 41
                        && Ws60Views.life(view, 3) == 41
                        && Ws60Views.controls(view, 0, "Llanowar Elves")),
                () -> captureSet(
                        "triggers",
                        frameIs("trigger_order", "trigger")),
                List.of(
                        new Ws60Suite.Assertion("P0 life 42, P1/P2/P3 life 41", "life",
                                (primary0, views, tape, log) ->
                                        Ws60Checks.lifeIs(views, 0, 42) + "+"
                                                + Ws60Checks.lifeIs(views, 1, 41) + "+"
                                                + Ws60Checks.lifeIs(views, 2, 41) + "+"
                                                + Ws60Checks.lifeIs(views, 3, 41)),
                        new Ws60Suite.Assertion("Llanowar Elves on battlefield under P0",
                                "battlefield",
                                (primary0, views, tape, log) ->
                                        Ws60Checks.controls(views, 0, "Llanowar Elves")),
                        new Ws60Suite.Assertion("stack empty, 5 triggers resolved in APNAP order",
                                "stack",
                                (primary0, views, tape, log) -> Ws60Checks.stackEmpty(views))),
                List.of(
                        new Ws60Suite.HiddenAudit("trigger creation", "ALL",
                                (captures, deckSeats) ->
                                        Ws60Checks.structuralPrivacy(captures, "triggers"))),
                Ws60Driver.RunResult::completed,
                () -> {
                },
                "STRUCTURAL: Commander-singleton assembly of 6 distributed Soul Warden 1-ofs + "
                        + "Cackling Counterpart + Llanowar Elves did not complete within bounds; "
                        + "additionally every native Warden entry fires entry triggers, so the "
                        + "fixture's nominal-40 lives are unreachable natively "
                        + "(predicted entry history P0+1/P1+4/P2+3/P3+2 for cast order "
                        + "P1,P2,P3,P0A,P0B-token). HARNESS_LIMITATION + FIXTURE_LIMITATION.");
    }

    // ------------------------------------------------------------------
    // J02 — Delina d20 with roll-again (seed-scanned 15-20 band).
    // ------------------------------------------------------------------

    static Ws60Suite.Spec j02() {
        List<Ws60Driver.SeatDeck> seats = List.of(
                seat2(Ws60Decks.TYMNA, Ws60Decks.TANA,
                        "Delina, Wild Mage", 1, "Runeclaw Bear", 1, "Sol Ring", 1,
                        "Command Tower", 1, "Exotic Orchard", 1, "Reflecting Pool", 1,
                        "Gemstone Mine", 1, "Tendo Ice Bridge", 1,
                        "Mountain", 40, "Forest", 40, "Plains", 5, "Swamp", 5),
                idleMountain(), idlePlains(), idleSwamp());
        TokenFlags flags = new TokenFlags();
        return new Ws60Suite.Spec("RQ-C3-J02",
                "Delina d20 with roll-again",
                "RQ-C3-J02", 6192L, 4200, seats,
                () -> {
                    Ws60Pilot pilot = new Ws60Pilot("RQ-C3-J02");
                    commandersAll(pilot, seats);
                    pilot.commanders(0, List.of(Ws60Decks.TYMNA, Ws60Decks.TANA));
                    pilot.seatLands(0, "Mountain", "Forest", "Plains", "Swamp")
                            .landOrder(0, "Command Tower", "Plains", "Swamp",
                                    "Exotic Orchard", "Reflecting Pool", "Forest",
                                    "Mountain")
                            .setupCast(0, "Delina, Wild Mage", "Runeclaw Bear")
                            .allowCommanderCast(0).assemblyFiltering(0)
                            .bool("pay X life", true)
                            .scryGas(0, 4)
                            .attackRoundRobin("Tymna the Weaver", List.of(2, 3, 1))
                            .attackRoundRobin("Tana, the Bloodsower", List.of(1, 2, 3))
                            .secureWhen(0, "Delina, Wild Mage", "Runeclaw Bear")
                            .attackCountGate("Delina, Wild Mage", "Runeclaw Bear", 1)
                            .attacker("Delina, Wild Mage", 1)
                            .target("creature you control", "Runeclaw Bear")
                            // Delina's token enters tapped-and-attacking, so the
                            // engine asks for ITS defender via a TargetDefender
                            // frame (no blockers exist anywhere and J02 asserts
                            // no life totals, so the token joins Delina on P1).
                            .targetPlayer(
                                    "player, planeswalker, or battle to attack", 1)
                            .bool("Roll again?", false)
                            // Hard-seek the two 1-of assembly pieces: an opener
                            // holding Delina or Bear plus the natural fixing
                            // density (50 lands/98) assembles natively, while
                            // fixing-seek keeps would stop mulligans before a
                            // piece is found. London bottoms still protect both
                            // pieces via the seek list.
                            .seek(0, 6, "Delina, Wild Mage", "Runeclaw Bear")
                            .critical("Roll again?")
                            .critical("Delina, Wild Mage");
                    return pilot;
                },
                harness -> {
                    JsonObject view;
                    try {
                        view = XmageFullGameStateRedactor.actorView(
                                harness.game, harness.players().get(0));
                    } catch (RuntimeException exc) {
                        return false;
                    }
                    long bears = Ws60Views.battlefield(view, 0).stream()
                            .filter(entry -> entry.name().contains("Runeclaw Bear")).count();
                    if (bears >= 2) {
                        flags.tokenSeen = true;
                    }
                    if (flags.tokenSeen && bears == 1) {
                        flags.tokenGone = true;
                    }
                    return flags.tokenSeen && flags.tokenGone
                            && Ws60Views.controls(view, 0, "Delina, Wild Mage")
                            && Ws60Views.stackSize(view) == 0;
                },
                () -> captureSet(
                        "roll-again",
                        frameIs("choose_use", "Roll again?")),
                List.of(
                        new Ws60Suite.Assertion(
                                "exactly one token was created and then exiled at end of combat (no token remains)",
                                "token existence",
                                (primary0, views, tape, log) -> {
                                    assertTrue(flags.tokenSeen, "token was created");
                                    assertTrue(flags.tokenGone, "token left at end of combat");
                                    long bears = Ws60Views.battlefield(views.get(0), 0)
                                            .stream()
                                            .filter(entry -> entry.name()
                                                    .contains("Runeclaw Bear"))
                                            .count();
                                    assertEquals(1, bears, "only the original Bear remains");
                                    return "token-created-and-exiled";
                                }),
                        new Ws60Suite.Assertion("Delina and Bear survive on battlefield",
                                "battlefield",
                                (primary0, views, tape, log) ->
                                        Ws60Checks.controls(views, 0, "Delina, Wild Mage")
                                                + "+" + Ws60Checks.controls(views, 0,
                                                        "Runeclaw Bear")),
                        new Ws60Suite.Assertion(
                                "RNG journal contains the d20 entry (domain 1-20, sampled 15-20 band, plus the decline of may-roll-again)",
                                "rng journal",
                                (primary0, views, tape, log) -> {
                                    List<Integer> rolls = dieResults(tape);
                                    assertTrue(!rolls.isEmpty(), "d20 journaled: " + rolls);
                                    int first = rolls.get(0);
                                    assertTrue(first >= 1 && first <= 20, "domain 1-20");
                                    assertTrue(first >= 15,
                                            "15-20 band required, observed " + rolls);
                                    boolean declined = log.stream().anyMatch(record -> {
                                        JsonObject projection = record.projection();
                                        return projection.get("class").getAsString()
                                                        .equals("choose_use")
                                                && projection.get("prompt").getAsString()
                                                        .contains("Roll again?")
                                                && projection.has("selected")
                                                && projection.getAsJsonArray("selected")
                                                        .toString().contains("No");
                                    });
                                    assertTrue(declined, "roll-again declined");
                                    return "d20=" + rolls + ";declined";
                                })),
                List.of(
                        new Ws60Suite.HiddenAudit("roll", "ALL",
                                (captures, deckSeats) ->
                                        Ws60Checks.structuralPrivacy(captures, "roll-again"))),
                run -> run.completed() && !dieResults(run.eventTape()).isEmpty()
                        && dieResults(run.eventTape()).get(0) >= 15,
                () -> {
                    flags.tokenSeen = false;
                    flags.tokenGone = false;
                },
                null);
    }

    static final class TokenFlags {
        volatile boolean tokenSeen;
        volatile boolean tokenGone;
    }
}
