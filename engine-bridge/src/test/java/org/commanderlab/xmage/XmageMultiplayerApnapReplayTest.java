package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.players.Player;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Semantic replay through the APNAP choice paths changed by the multiplayer
 * candidate (F-21 consumers: Grave Pact and SacrificeAllEffect), at 4P and 5P.
 *
 * <p>P1 controls Grave Pact and a Grizzly Bears. Every opponent controls a
 * Walking Corpse, a Craw Wurm and a Hill Giant. P1 casts Pyroclasm: every 2/2
 * dies, including P1's Bears, so Grave Pact makes each other player sacrifice
 * a creature in APNAP order (each sacrifices its Hill Giant). P1 then casts
 * Innocent Blood: each player sacrifices a creature (each opponent its Craw
 * Wurm; P1 has none).</p>
 *
 * <p>The scripted pilot chooses by card identity only. Two runs with the same
 * explicit Rules seed must produce the identical decision transcript (actor,
 * decision class, offered option labels) and identical final zones. Engine
 * UUIDs are random per game and are excluded from the comparison.</p>
 */
class XmageMultiplayerApnapReplayTest {

    private static final String MOUNTAIN_LABEL = "Mountain — {T}: Add {R}.";
    private static final String SWAMP_LABEL = "Swamp — {T}: Add {B}.";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {4, 5})
    void twinRunsProduceTheSameTranscriptAndZones(int playerCount) {
        Run first = run(playerCount, "a");
        Run second = run(playerCount, "b");
        assertEquals(first.transcript, second.transcript, "same seed: identical decision transcript");
        assertEquals(first.zones, second.zones, "same seed: identical final zones");

        // Non-vacuity: every opponent made both sacrifice choices, in APNAP order.
        List<String> sacrificers = new ArrayList<>();
        for (String line : first.transcript) {
            if (line.contains("|sacrifice|")) {
                sacrificers.add(line.substring(0, line.indexOf('|')));
            }
        }
        List<String> apnap = new ArrayList<>();
        for (int seat = 2; seat <= playerCount; seat++) {
            apnap.add("P" + seat);
        }
        List<String> expected = new ArrayList<>(apnap);
        expected.addAll(apnap);
        assertEquals(expected, sacrificers,
                "Grave Pact then Innocent Blood: each opponent chooses, in APNAP order (P1 active)");
        for (int seat = 2; seat <= playerCount; seat++) {
            assertEquals("[]", first.zones.get("P" + seat + ":battlefield-creatures"),
                    "P" + seat + " lost all three creatures");
        }
    }

    private record Run(List<String> transcript, Map<String, String> zones) {
    }

    private static Run run(int playerCount, String run) {
        String tag = "apnap-replay-" + playerCount + "p-" + run;
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("bf", "P1", "Grave Pact", 0));
        objects.add(obj("bf", "P1", "Grizzly Bears", 0));
        objects.add(obj("hand", "P1", "Pyroclasm", 0));
        objects.add(obj("hand", "P1", "Innocent Blood", 0));
        for (int index = 0; index < 2; index++) {
            objects.add(obj("bf", "P1", "Mountain", index));
        }
        objects.add(obj("bf", "P1", "Swamp", 0));
        for (int seat = 2; seat <= playerCount; seat++) {
            String pid = "P" + seat;
            objects.add(obj("bf", pid, "Walking Corpse", 0));
            objects.add(obj("bf", pid, "Craw Wurm", 0));
            objects.add(obj("bf", pid, "Hill Giant", 0));
        }
        XmageActualCardCorpusTest.Started started = XmageActualCardCorpusTest.start(
                tag, playerCount, objects, Map.of(), 0, 777L);
        Game game = started.session().restorationGame();
        List<String> transcript = new ArrayList<>();

        XmageActualCardCorpusTest.cast(started, tag + "-pyroclasm", "Pyroclasm");
        XmageActualCardCorpusTest.resolveAll(started, tag + "-pyroclasm", MOUNTAIN_LABEL,
                (cls, step) -> answer(started, tag, cls, step, transcript, "Hill Giant"));
        XmageActualCardCorpusTest.cast(started, tag + "-blood", "Innocent Blood");
        XmageActualCardCorpusTest.resolveAll(started, tag + "-blood", SWAMP_LABEL,
                (cls, step) -> answer(started, tag, cls, step, transcript, "Craw Wurm"));

        Map<String, String> zones = new TreeMap<>();
        for (Map.Entry<String, Player> seat : started.seats().entrySet()) {
            List<String> creatures = new ArrayList<>();
            for (Permanent permanent : game.getBattlefield().getAllActivePermanents(seat.getValue().getId())) {
                if (permanent.isCreature(game)) {
                    creatures.add(permanent.getName());
                }
            }
            creatures.sort(String::compareTo);
            List<String> graveyard = new ArrayList<>();
            for (Card card : seat.getValue().getGraveyard().getCards(game)) {
                graveyard.add(card.getName());
            }
            graveyard.sort(String::compareTo);
            zones.put(seat.getKey() + ":battlefield-creatures", creatures.toString());
            zones.put(seat.getKey() + ":graveyard", graveyard.toString());
            zones.put(seat.getKey() + ":life", String.valueOf(seat.getValue().getLife()));
            zones.put(seat.getKey() + ":hand", String.valueOf(seat.getValue().getHand().size()));
        }
        return new Run(transcript, zones);
    }

    /** Scripted by card identity: sacrifice {@code victim}; record the frame without engine ids. */
    private static boolean answer(XmageActualCardCorpusTest.Started started, String tag, String cls,
            int step, List<String> transcript, String victim) {
        if (!"choose_object".equals(cls) && !"target".equals(cls)) {
            return false;
        }
        String actor = XmageActualCardCorpusTest.actorPid(started);
        JsonObject pending = started.session().pendingDecisionPayload().getAsJsonObject("decision");
        String prompt = pending.get("prompt").getAsString().toLowerCase(Locale.ROOT);
        List<String> labels = new ArrayList<>();
        for (JsonElement element : started.session().legalActionsPayload().getAsJsonArray("actions")) {
            labels.add(element.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString());
        }
        labels.sort(String::compareTo);
        // Keep the authoritative decision class; "sacrifice" is an additional semantic tag, so
        // two runs that differ in decision class (e.g. choose_object vs target) never compare equal.
        String kind = prompt.contains("sacrifice") ? "sacrifice" : "other";
        transcript.add(actor + "|" + kind + "|" + cls + "|" + labels);
        if (!labels.stream().anyMatch(label -> label.startsWith(victim))) {
            fail("[" + tag + "] " + actor + " was not offered " + victim + ": " + labels);
        }
        XmageActualCardCorpusTest.chooseByExactName(started, tag + "-sac-" + actor + "-" + step, victim, 1);
        return true;
    }

    private static XmageNativeStateRestoration.RequestedObject obj(
            String zoneTag, String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zoneTag + "-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, "hand".equals(zoneTag) ? mage.constants.Zone.HAND
                        : mage.constants.Zone.BATTLEFIELD, false);
    }

}
