package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.constants.CommanderCardType;
import mage.game.CommanderFreeForAll;
import mage.game.permanent.Permanent;
import mage.players.Player;
import mage.watchers.common.CommanderInfoWatcher;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * RG-02B: Commander Lab binds semantic Commander damage to XMage's native
 * CARD-scope CommanderInfoWatcher. No Lab damage ledger exists.
 *
 * <p>Deep post-restore Commander identity semantics (real later combat,
 * controller change, blink/re-entry, MDFC and mutate) are already runtime
 * qualified in the exact pinned Mage RG-02 suite. These tests qualify the new
 * Lab binding/restoration boundary and native SBA consumption of its result.
 * Any semantic Commander that cannot bind 1:1 to the genuine engine Commander
 * identity fails closed before watcher mutation.</p>
 */
class XmageCommanderDamageRestorationTest {

    private static XmageNativeStateRestoration.RequestedPlayer player(String pid, int seat) {
        return new XmageNativeStateRestoration.RequestedPlayer(pid, seat, 40);
    }

    private static XmageNativeStateRestoration.RequestedCommander commander(
            String id, String name, String owner) {
        return new XmageNativeStateRestoration.RequestedCommander(id, name, owner, 0);
    }

    private static XmageNativeStateRestoration.RequestedCommanderDamage damage(
            String commanderId, String playerId, int amount) {
        return new XmageNativeStateRestoration.RequestedCommanderDamage(
                commanderId, playerId, amount);
    }

    private static XmageNativeStateRestoration.Plan plan(
            String id,
            int playerCount,
            List<XmageNativeStateRestoration.RequestedCommander> commanders,
            List<XmageNativeStateRestoration.RequestedCommanderDamage> damage,
            List<XmageNativeStateRestoration.RequestedObject> objects) {
        List<XmageNativeStateRestoration.RequestedPlayer> players = new ArrayList<>();
        for (int seat = 1; seat <= playerCount; seat++) {
            players.add(player("P" + seat, seat));
        }
        return new XmageNativeStateRestoration.Plan(
                id, playerCount, 424242L, players, commanders, damage, objects,
                1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                mage.constants.PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
    }

    private static List<XmageNativeStateRestoration.RequestedCommander> commanders(
            int players, String p1Name) {
        List<XmageNativeStateRestoration.RequestedCommander> result = new ArrayList<>();
        result.add(commander("cmd:P1-A", p1Name, "P1"));
        for (int seat = 2; seat <= players; seat++) {
            result.add(commander(
                    "cmd:P" + seat + "-A", "Rograkh, Son of Rohgahh", "P" + seat));
        }
        return result;
    }

    private static Arrived arrive(XmageNativeStateRestoration.Plan plan, String tag) {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles =
                XmageNativeStateRestorationTest.importScaffolding(importer, plan, tag);
        XmageFullGameSession session = new XmageFullGameSession(
                tag, handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        return new Arrived(session, restoration, seats);
    }

    private static UUID commanderId(
            CommanderFreeForAll game, Player owner, String name) {
        List<UUID> matches = new ArrayList<>();
        for (UUID id : game.getCommandersIds(owner, CommanderCardType.ANY, false)) {
            Card card = game.getCard(id);
            if (card != null && name.equals(card.getName())) {
                matches.add(id);
            }
        }
        assertEquals(1, matches.size(), "exact genuine Commander binding for " + name);
        return matches.get(0);
    }

    private static CommanderInfoWatcher watcher(
            Arrived arrived, String ownerPid, String commanderName) {
        Player owner = arrived.seats().get(ownerPid);
        UUID id = commanderId(arrived.game(), owner, commanderName);
        CommanderInfoWatcher watcher =
                arrived.game().getState().getWatcher(CommanderInfoWatcher.class, id);
        assertNotNull(watcher, "native CommanderInfoWatcher must exist");
        return watcher;
    }

    @Test
    void frozenDamageMatrixParsesAndBindsToGenuineCommanderNotSetupCopy() {
        XmageNativeStateRestoration.Plan parsed =
                XmageNativeStateRestoration.planFromFrozenRecord(
                        XmageNativeStateRestorationTest.frozenRecord("WS05-CMD-DMG-SAME-21"),
                        "rg02b-frozen", 424242L);
        assertEquals(1, parsed.commanderDamage().size());
        assertEquals(19, parsed.commanderDamage().get(0).combatDamage());

        Arrived arrived = arrive(parsed, "rg02b-frozen");
        CommanderInfoWatcher real = watcher(arrived, "P1", "Isamaru, Hound of Konda");
        assertEquals(19, real.getDamageToPlayer().get(arrived.seats().get("P2").getId()));

        UUID realCommanderId = commanderId(
                arrived.game(), arrived.seats().get("P1"), "Isamaru, Hound of Konda");
        Permanent setupCopy = arrived.game().getBattlefield().getAllPermanents().stream()
                .filter(p -> "Isamaru, Hound of Konda".equals(p.getName()))
                .filter(p -> arrived.seats().get("P1").getId().equals(p.getOwnerId()))
                .filter(p -> !p.getId().equals(realCommanderId))
                .findFirst()
                .orElseThrow(() -> new AssertionError("fixture setup Isamaru copy missing"));
        assertNull(arrived.game().getState().getWatcher(
                        CommanderInfoWatcher.class, setupCopy.getId()),
                "setup-placed non-Commander copy must never receive Commander identity");
    }

    @Test
    void restore20DoesNotLoseButRestore21UsesNativeStateBasedLoss() {
        XmageNativeStateRestoration.Plan twenty = plan(
                "rg02b-20", 3, commanders(3, "Isamaru, Hound of Konda"),
                List.of(damage("cmd:P1-A", "P2", 20)), List.of());
        Arrived at20 = arrive(twenty, "rg02b-20");
        assertFalse(at20.seats().get("P2").hasLost());
        assertEquals(20, watcher(at20, "P1", "Isamaru, Hound of Konda")
                .getDamageToPlayer().get(at20.seats().get("P2").getId()));

        XmageNativeStateRestoration.Plan twentyOne = plan(
                "rg02b-21", 3, commanders(3, "Isamaru, Hound of Konda"),
                List.of(damage("cmd:P1-A", "P2", 21)), List.of());
        Arrived at21 = arrive(twentyOne, "rg02b-21");
        assertTrue(at21.seats().get("P2").hasLost(),
                "21 restored Commander combat damage must be consumed by native SBA");
        // Repeated later state checks must be stable and non-recursive.
        XmageNativeStateRestoration.revalidate(at21.game());
        assertTrue(at21.seats().get("P2").hasLost());
    }

    @Test
    void splitCommanderDamageDoesNotAggregateAndPartnersStayIndependent() {
        List<XmageNativeStateRestoration.RequestedCommander> split = List.of(
                commander("cmd:P1-A", "Rograkh, Son of Rohgahh", "P1"),
                commander("cmd:P1-B", "Kediss, Emberclaw Familiar", "P1"),
                commander("cmd:P2-A", "Rograkh, Son of Rohgahh", "P2"),
                commander("cmd:P3-A", "Rograkh, Son of Rohgahh", "P3"));
        XmageNativeStateRestoration.Plan p = plan(
                "rg02b-partners", 3, split,
                List.of(
                        damage("cmd:P1-A", "P2", 11),
                        damage("cmd:P1-B", "P2", 10)),
                List.of());
        Arrived arrived = arrive(p, "rg02b-partners");
        assertFalse(arrived.seats().get("P2").hasLost());
        assertEquals(11, watcher(arrived, "P1", "Rograkh, Son of Rohgahh")
                .getDamageToPlayer().get(arrived.seats().get("P2").getId()));
        assertEquals(10, watcher(arrived, "P1", "Kediss, Emberclaw Familiar")
                .getDamageToPlayer().get(arrived.seats().get("P2").getId()));
    }

    @Test
    void modalDoubleFacedCommanderBindsThroughNativeCommanderIdentity() {
        XmageNativeStateRestoration.Plan p = plan(
                "rg02b-mdfc", 3, commanders(3, "Esika, God of the Tree"),
                List.of(damage("cmd:P1-A", "P2", 20)), List.of());
        Arrived arrived = arrive(p, "rg02b-mdfc");
        assertEquals(20, watcher(arrived, "P1", "Esika, God of the Tree")
                .getDamageToPlayer().get(arrived.seats().get("P2").getId()));
        assertFalse(arrived.seats().get("P2").hasLost());
    }

    @Test
    void restorationWorksAtThreeFourAndFivePlayers() {
        for (int count : List.of(3, 4, 5)) {
            XmageNativeStateRestoration.Plan p = plan(
                    "rg02b-" + count + "p", count,
                    commanders(count, "Isamaru, Hound of Konda"),
                    List.of(damage("cmd:P1-A", "P2", 7)), List.of());
            Arrived arrived = arrive(p, "rg02b-" + count + "p");
            assertEquals(7, watcher(arrived, "P1", "Isamaru, Hound of Konda")
                    .getDamageToPlayer().get(arrived.seats().get("P2").getId()));
            assertFalse(arrived.seats().get("P2").hasLost());
        }
    }

    @Test
    void invalidSemanticDamageReferencesFailBeforeAnyGameMutation() {
        List<XmageNativeStateRestoration.RequestedCommander> cs =
                commanders(3, "Isamaru, Hound of Konda");

        XmageNativeStateRestoration.RestorationException unknownCommander =
                assertThrows(XmageNativeStateRestoration.RestorationException.class,
                        () -> XmageNativeStateRestorationTest.restorationFor(plan(
                                "bad-commander", 3, cs,
                                List.of(damage("cmd:missing", "P2", 1)), List.of())));
        assertTrue(unknownCommander.getMessage().startsWith("UNKNOWN_COMMANDER_ID"));

        XmageNativeStateRestoration.RestorationException unknownPlayer =
                assertThrows(XmageNativeStateRestoration.RestorationException.class,
                        () -> XmageNativeStateRestorationTest.restorationFor(plan(
                                "bad-player", 3, cs,
                                List.of(damage("cmd:P1-A", "P9", 1)), List.of())));
        assertTrue(unknownPlayer.getMessage().startsWith("UNKNOWN_ACTOR"));

        XmageNativeStateRestoration.RestorationException negative =
                assertThrows(XmageNativeStateRestoration.RestorationException.class,
                        () -> XmageNativeStateRestorationTest.restorationFor(plan(
                                "bad-negative", 3, cs,
                                List.of(damage("cmd:P1-A", "P2", -1)), List.of())));
        assertTrue(negative.getMessage().startsWith("INVALID_COMMANDER_DAMAGE"));
    }

    @Test
    void freshSessionReplayReproducesCommanderDamageTerminalState() {
        XmageNativeStateRestoration.Plan p = plan(
                "rg02b-replay", 3, commanders(3, "Isamaru, Hound of Konda"),
                List.of(damage("cmd:P1-A", "P2", 21)), List.of());
        Arrived first = arrive(p, "rg02b-replay-a");
        Arrived second = arrive(p, "rg02b-replay-b");
        assertTrue(first.seats().get("P2").hasLost());
        assertTrue(second.seats().get("P2").hasLost());
        assertEquals(
                watcher(first, "P1", "Isamaru, Hound of Konda")
                        .getDamageToPlayer().get(first.seats().get("P2").getId()),
                watcher(second, "P1", "Isamaru, Hound of Konda")
                        .getDamageToPlayer().get(second.seats().get("P2").getId()));
    }

    @Test
    void frozenSplitAndControlFixturesNowParseWithoutFabricatingCommanderIdentity() {
        for (String fixture : List.of(
                "WS05-CMD-DMG-SPLIT",
                "WS05-CMD-DMG-CONTROL",
                "WS05-CMD-PARTNER-DMG",
                "WS05-CMD-ELIM-4")) {
            XmageNativeStateRestoration.Plan p =
                    XmageNativeStateRestoration.planFromFrozenRecord(
                            XmageNativeStateRestorationTest.frozenRecord(fixture),
                            "rg02b-" + fixture, 424242L);
            assertFalse(p.commanderDamage().isEmpty(), fixture);
        }
    }

    private record Arrived(
            XmageFullGameSession session,
            XmageNativeStateRestoration restoration,
            Map<String, Player> seats
    ) {
        CommanderFreeForAll game() {
            return session.restorationGame();
        }
    }
}
