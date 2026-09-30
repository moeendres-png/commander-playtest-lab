package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.constants.Zone;
import mage.players.Player;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Shared set-up for N-player actual-card scenarios on the XMage full-game
 * lane: a native restoration at P{active}'s precombat main with the requested
 * objects, Rograkh commanders and Mountain libraries.
 */
final class XmageMultiplayerScenario {

    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";

    final XmageFullGameSession session;
    final Map<String, Player> seats;

    private XmageMultiplayerScenario(XmageFullGameSession session, Map<String, Player> seats) {
        this.session = session;
        this.seats = seats;
    }

    static XmageNativeStateRestoration.RequestedObject obj(
            String pid, String name, int index, Zone zone) {
        String slug = name.replaceAll("[^A-Za-z0-9]+", "");
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zone.name().toLowerCase() + "-" + pid + "-" + index + "-" + slug,
                name, pid, pid, zone, false);
    }

    static XmageMultiplayerScenario start(String tag, int count, String active,
            List<XmageNativeStateRestoration.RequestedObject> objects) {
        return start(tag, count, active, objects, Map.of());
    }

    /**
     * As {@link #start(String, int, String, List)}, with named cards in a
     * seat's library: {@code libraryCards} replaces that many of the seat's
     * 99 Mountains (the library itself stays engine-shuffled).
     */
    static XmageMultiplayerScenario start(String tag, int count, String active,
            List<XmageNativeStateRestoration.RequestedObject> objects,
            Map<String, List<String>> libraryCards) {
        List<XmageNativeStateRestoration.RequestedPlayer> players = new ArrayList<>();
        List<XmageNativeStateRestoration.RequestedCommander> commanders = new ArrayList<>();
        for (int seat = 1; seat <= count; seat++) {
            String pid = "P" + seat;
            players.add(new XmageNativeStateRestoration.RequestedPlayer(pid, seat, 40));
            commanders.add(new XmageNativeStateRestoration.RequestedCommander(
                    "cmd:" + pid + "-A", ROGRAKH, pid, 0));
        }
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                tag, count, 424242L, List.copyOf(players), List.copyOf(commanders),
                List.copyOf(objects), 1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                mage.constants.PhaseStep.PRECOMBAT_MAIN, active, active);
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles = new ArrayList<>();
        for (XmageNativeStateRestoration.RequestedPlayer player : players) {
            List<String> mainboard = new ArrayList<>(
                    libraryCards.getOrDefault(player.playerId(), List.of()));
            while (mainboard.size() < 99) {
                mainboard.add("Mountain");
            }
            handles.add(importer.importCommanderDeck(tag + "-" + player.playerId(),
                    tag + "-hash", mainboard, List.of(ROGRAKH)).deckHandle());
        }
        // The starting seat must match the restored active player.
        int activeSeat = Integer.parseInt(active.substring(1));
        XmageFullGameSession session = new XmageFullGameSession(
                tag, handles, activeSeat - 1, 40, plan.seed(), importer, restoration);
        session.start();
        Map<String, Player> seats = session.restorationSeats();
        XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);
        return new XmageMultiplayerScenario(session, seats);
    }

    String decisionClass() {
        JsonObject legal = session.legalActionsPayload();
        return legal.get("decision_class") == null || legal.get("decision_class").isJsonNull()
                ? null : legal.get("decision_class").getAsString();
    }

    String actor() {
        return XmageNativeStateRestorationTest.pidOf(seats,
                session.legalActionsPayload().get("actor_id").getAsString());
    }

    String pidOf(String uuid) {
        return XmageNativeStateRestorationTest.pidOf(seats, uuid);
    }

    JsonObject action(String actionType, String labelPart) {
        for (JsonElement e : session.legalActionsPayload().getAsJsonArray("actions")) {
            JsonObject a = e.getAsJsonObject();
            if (actionType.equals(a.get("action_type").getAsString())
                    && a.getAsJsonObject("metadata").get("label").getAsString()
                            .contains(labelPart)) {
                return a;
            }
        }
        return null;
    }

    List<String> labels() {
        List<String> out = new ArrayList<>();
        for (JsonElement e : session.legalActionsPayload().getAsJsonArray("actions")) {
            out.add(e.getAsJsonObject().getAsJsonObject("metadata").get("label").getAsString());
        }
        return out;
    }

    String prompt() {
        JsonObject decision = session.pendingDecisionPayload().getAsJsonObject("decision");
        return decision == null || !decision.has("prompt") ? "" : decision.get("prompt").getAsString();
    }

    private int step;

    void submit(JsonObject action) {
        XmageFullGameTaxExecutionTest.submit(session, "mp-" + (step++), action);
    }

    /** Pays the pending mana cost from lands named {@code land}, pool mana first. */
    void payWith(String land) {
        for (int i = 0; i < 20 && "mana_payment".equals(decisionClass()); i++) {
            JsonObject pool = action("pay_cost", "Spend ");
            submit(pool != null ? pool : action("pay_cost", land));
        }
    }
}
