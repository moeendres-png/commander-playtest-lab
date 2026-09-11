package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * WS60 read helpers over principal-scoped ledger snapshots.
 *
 * <p>Test-side only. Completion checks and terminal assertions read entitled
 * views; hidden-info audits compare per-principal views against omniscient
 * ground truth (deck lists) to prove redaction.</p>
 */
final class Ws60Views {

    private Ws60Views() {
    }

    static JsonObject playerView(JsonObject snapshot, int rqSeat) {
        for (JsonElement element : snapshot.getAsJsonArray("players")) {
            JsonObject player = element.getAsJsonObject();
            if (player.get("seat").getAsInt() == rqSeat) {
                return player;
            }
        }
        throw new IllegalArgumentException("no player view for seat " + rqSeat);
    }

    static int life(JsonObject snapshot, int rqSeat) {
        return playerView(snapshot, rqSeat).get("life").getAsInt();
    }

    static boolean hasLost(JsonObject snapshot, int rqSeat) {
        return playerView(snapshot, rqSeat).get("has_lost").getAsBoolean();
    }

    static boolean hasLeft(JsonObject snapshot, int rqSeat) {
        return playerView(snapshot, rqSeat).get("has_left").getAsBoolean();
    }

    static int handCount(JsonObject snapshot, int rqSeat) {
        return playerView(snapshot, rqSeat).get("hand_count").getAsInt();
    }

    static int libraryCount(JsonObject snapshot, int rqSeat) {
        return playerView(snapshot, rqSeat).get("library_count").getAsInt();
    }

    /** Owner-entitled hand names; empty when the viewer is not entitled. */
    static List<String> handNames(JsonObject snapshot, int rqSeat) {
        JsonObject player = playerView(snapshot, rqSeat);
        List<String> out = new ArrayList<>();
        if (!player.has("hand") || !player.get("hand").isJsonArray()) {
            return out;
        }
        for (JsonElement element : player.getAsJsonArray("hand")) {
            out.add(element.getAsJsonObject().get("name").getAsString());
        }
        return out;
    }

    record BattlefieldEntry(String name, String controller, String owner,
            boolean tapped, int damage, int power, int toughness,
            Map<String, Integer> counters, int abilityCount, List<String> abilities) {
    }

    static List<BattlefieldEntry> battlefield(JsonObject snapshot, int rqSeat) {
        JsonObject player = playerView(snapshot, rqSeat);
        List<BattlefieldEntry> out = new ArrayList<>();
        for (JsonElement element : player.getAsJsonArray("battlefield")) {
            JsonObject item = element.getAsJsonObject();
            Map<String, Integer> counters = new LinkedHashMap<>();
            if (item.has("counters") && item.get("counters").isJsonArray()) {
                for (JsonElement counter : item.getAsJsonArray("counters")) {
                    JsonObject row = counter.getAsJsonObject();
                    counters.put(row.get("type").getAsString(), row.get("count").getAsInt());
                }
            }
            List<String> abilities = new ArrayList<>();
            if (item.has("abilities") && item.get("abilities").isJsonArray()) {
                for (JsonElement ability : item.getAsJsonArray("abilities")) {
                    abilities.add(ability.getAsString());
                }
            }
            out.add(new BattlefieldEntry(
                    item.get("name").getAsString(),
                    item.has("controller_id") ? item.get("controller_id").getAsString() : "?",
                    item.has("owner_id") ? item.get("owner_id").getAsString() : "?",
                    item.get("tapped").getAsBoolean(),
                    item.has("damage") ? item.get("damage").getAsInt() : 0,
                    item.has("power") ? item.get("power").getAsInt() : 0,
                    item.has("toughness") ? item.get("toughness").getAsInt() : 0,
                    counters,
                    item.has("ability_count") ? item.get("ability_count").getAsInt() : -1,
                    abilities));
        }
        return out;
    }

    static List<String> battlefieldNames(JsonObject snapshot, int rqSeat) {
        List<String> out = new ArrayList<>();
        for (BattlefieldEntry entry : battlefield(snapshot, rqSeat)) {
            out.add(entry.name());
        }
        return out;
    }

    static boolean controls(JsonObject snapshot, int rqSeat, String nameFragment) {
        return battlefieldNames(snapshot, rqSeat).stream().anyMatch(name -> name.contains(nameFragment));
    }

    static List<String> graveyardNames(JsonObject snapshot, int rqSeat) {
        List<String> out = new ArrayList<>();
        for (JsonElement element : playerView(snapshot, rqSeat).getAsJsonArray("graveyard")) {
            out.add(element.getAsJsonObject().get("name").getAsString());
        }
        return out;
    }

    static List<String> exileNames(JsonObject snapshot, int rqSeat) {
        List<String> out = new ArrayList<>();
        for (JsonElement element : playerView(snapshot, rqSeat).getAsJsonArray("exile")) {
            out.add(element.getAsJsonObject().get("name").getAsString());
        }
        return out;
    }

    static List<String> commandNames(JsonObject snapshot, int rqSeat) {
        List<String> out = new ArrayList<>();
        for (JsonElement element : playerView(snapshot, rqSeat).getAsJsonArray("command")) {
            out.add(element.getAsJsonObject().get("name").getAsString());
        }
        return out;
    }

    static List<String> stackNames(JsonObject snapshot) {
        List<String> out = new ArrayList<>();
        if (!snapshot.has("stack") || !snapshot.get("stack").isJsonArray()) {
            return out;
        }
        for (JsonElement element : snapshot.getAsJsonArray("stack")) {
            out.add(element.getAsJsonObject().get("name").getAsString());
        }
        return out;
    }

    static int stackSize(JsonObject snapshot) {
        return stackNames(snapshot).size();
    }

    static int turnNumber(JsonObject snapshot) {
        return snapshot.get("turn_number").getAsInt();
    }

    static String phase(JsonObject snapshot) {
        return snapshot.has("phase") && !snapshot.get("phase").isJsonNull()
                ? snapshot.get("phase").getAsString() : "";
    }

    static JsonArray commanderStatus(JsonObject snapshot) {
        return snapshot.has("commander_status") && snapshot.get("commander_status").isJsonArray()
                ? snapshot.getAsJsonArray("commander_status") : new JsonArray();
    }

    static int commanderDamageTo(JsonObject snapshot, String commanderFragment, int rqSeat) {
        Map<String, Integer> seatByRef = seatByRef(snapshot);
        for (JsonElement element : commanderStatus(snapshot)) {
            JsonObject row = element.getAsJsonObject();
            if (!row.get("name").getAsString().contains(commanderFragment)) {
                continue;
            }
            for (JsonElement damage : row.getAsJsonArray("commander_damage_to_player")) {
                JsonObject hit = damage.getAsJsonObject();
                Integer seat = seatByRef.get(hit.get("player_id").getAsString());
                if (seat != null && seat == rqSeat) {
                    return hit.get("total").getAsInt();
                }
            }
        }
        return 0;
    }

    /** Maps opaque actor-projected identity refs to 0-based seats. */
    static Map<String, Integer> seatByRef(JsonObject snapshot) {
        Map<String, Integer> out = new LinkedHashMap<>();
        if (!snapshot.has("players") || !snapshot.get("players").isJsonArray()) {
            return out;
        }
        for (JsonElement element : snapshot.getAsJsonArray("players")) {
            JsonObject player = element.getAsJsonObject();
            if (player.has("player_id") && player.has("seat")) {
                out.put(player.get("player_id").getAsString(),
                        player.get("seat").getAsInt());
            }
        }
        return out;
    }

    /** Resolves a battlefield entry's controller/owner ref to an RQ seat. */
    static int controllerSeat(JsonObject snapshot, BattlefieldEntry entry) {
        Integer seat = seatByRef(snapshot).get(entry.controller());
        return seat == null ? -1 : seat;
    }

    static int ownerSeat(JsonObject snapshot, BattlefieldEntry entry) {
        Integer seat = seatByRef(snapshot).get(entry.owner());
        return seat == null ? -1 : seat;
    }

    static int castsFromCommand(JsonObject snapshot, String commanderFragment) {
        for (JsonElement element : commanderStatus(snapshot)) {
            JsonObject row = element.getAsJsonObject();
            if (row.get("name").getAsString().contains(commanderFragment)
                    && row.has("casts_from_command") && !row.get("casts_from_command").isJsonNull()) {
                return row.get("casts_from_command").getAsInt();
            }
        }
        return -1;
    }

    /** Counts permanents by name across all seats (multiset, controller-agnostic). */
    static Map<String, Integer> battlefieldCensus(JsonObject snapshot) {
        Map<String, Integer> out = new LinkedHashMap<>();
        for (JsonElement player : snapshot.getAsJsonArray("players")) {
            for (JsonElement element : player.getAsJsonObject().getAsJsonArray("battlefield")) {
                String name = element.getAsJsonObject().get("name").getAsString();
                out.merge(name, 1, Integer::sum);
            }
        }
        return out;
    }
}
