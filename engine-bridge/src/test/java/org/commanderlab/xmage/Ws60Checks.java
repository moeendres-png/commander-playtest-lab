package org.commanderlab.xmage;

import com.google.gson.JsonObject;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * WS60 shared assertion and hidden-info audit helpers.
 */
final class Ws60Checks {

    private Ws60Checks() {
    }

    static String lifeIs(List<JsonObject> views, int rqSeat, int expected) {
        int actual = Ws60Views.life(views.get(0), rqSeat);
        assertEquals(expected, actual,
                () -> "life P" + rqSeat + " expected " + expected + " observed " + actual);
        return "P" + rqSeat + "=" + actual;
    }

    static String allLife(List<JsonObject> views, int expected) {
        for (int seat = 0; seat < 4; seat++) {
            lifeIs(views, seat, expected);
        }
        return "all=" + expected;
    }

    static String graveHas(List<JsonObject> views, int rqSeat, String name) {
        List<String> grave = Ws60Views.graveyardNames(views.get(0), rqSeat);
        assertTrue(grave.stream().anyMatch(card -> card.contains(name)),
                () -> "P" + rqSeat + " graveyard lacks " + name + ": " + grave);
        return "grave" + rqSeat + "=" + grave;
    }

    static String graveLacks(List<JsonObject> views, int rqSeat, String name) {
        List<String> grave = Ws60Views.graveyardNames(views.get(0), rqSeat);
        assertTrue(grave.stream().noneMatch(card -> card.contains(name)),
                () -> "P" + rqSeat + " graveyard unexpectedly holds " + name + ": " + grave);
        return "grave" + rqSeat + "-no-" + name;
    }

    static String controls(List<JsonObject> views, int rqSeat, String name) {
        assertTrue(Ws60Views.controls(views.get(0), rqSeat, name),
                () -> "P" + rqSeat + " does not control " + name + ": "
                        + Ws60Views.battlefieldNames(views.get(0), rqSeat));
        return "P" + rqSeat + "-controls-" + name;
    }

    static String controlsTapped(List<JsonObject> views, int rqSeat, String name) {
        for (Ws60Views.BattlefieldEntry entry : Ws60Views.battlefield(views.get(0), rqSeat)) {
            if (entry.name().contains(name) && entry.tapped()) {
                return "P" + rqSeat + "-" + name + "-tapped";
            }
        }
        fail("P" + rqSeat + " controls no tapped " + name);
        throw new AssertionError("unreachable");
    }

    static String stackEmpty(List<JsonObject> views) {
        int size = Ws60Views.stackSize(views.get(0));
        assertEquals(0, size, () -> "stack not empty: " + Ws60Views.stackNames(views.get(0)));
        return "stack-empty";
    }

    static String libraryLessThan(List<JsonObject> views, int rqSeat, int bound) {
        int count = Ws60Views.libraryCount(views.get(0), rqSeat);
        assertTrue(count < bound,
                () -> "P" + rqSeat + " library " + count + " not below " + bound);
        return "lib" + rqSeat + "=" + count;
    }

    static String lost(List<JsonObject> views, int rqSeat, boolean expected) {
        boolean actual = Ws60Views.hasLost(views.get(0), rqSeat);
        assertEquals(expected, actual, () -> "P" + rqSeat + " has_lost=" + actual);
        return "P" + rqSeat + "-lost=" + actual;
    }

    static String left(List<JsonObject> views, int rqSeat, boolean expected) {
        boolean actual = Ws60Views.hasLeft(views.get(0), rqSeat);
        assertEquals(expected, actual, () -> "P" + rqSeat + " has_left=" + actual);
        return "P" + rqSeat + "-left=" + actual;
    }

    // ------------------------------------------------------------------
    // Hidden-info audits over checkpoint captures (principal-scoped views).
    // ------------------------------------------------------------------

    /** Structural privacy: hand arrays owner-only; no granted library looks. */
    static String structuralPrivacy(Map<String, List<JsonObject>> captures, String capture) {
        List<JsonObject> views = requireCapture(captures, capture);
        assertEquals(4, views.size(), "four principal views required");
        for (int viewer = 0; viewer < 4; viewer++) {
            JsonObject view = views.get(viewer);
            for (JsonElementPlayer player : players(view)) {
                int seat = player.seat();
                boolean hasHand = player.object().has("hand");
                if (seat == viewer) {
                    assertTrue(hasHand, "viewer P" + viewer + " must see own hand");
                } else {
                    assertTrue(!hasHand,
                            "viewer P" + viewer + " must not see P" + seat + " hand");
                }
                JsonObject row = player.object();
                if (row.has("granted_library") && row.get("granted_library").isJsonArray()) {
                    assertEquals(0, row.getAsJsonArray("granted_library").size(),
                            "viewer P" + viewer + " unexpected granted look at P" + seat);
                }
            }
        }
        return "hand-discipline-ok;granted-empty";
    }

    /** In-window legitimacy: only the owner holds a granted look, at own library. */
    static String grantedOwnLibraryOnly(Map<String, List<JsonObject>> captures, String capture,
            int ownerSeat) {
        List<JsonObject> views = requireCapture(captures, capture);
        for (int viewer = 0; viewer < 4; viewer++) {
            for (JsonElementPlayer player : players(views.get(viewer))) {
                JsonObject row = player.object();
                int size = row.has("granted_library") && row.get("granted_library").isJsonArray()
                        ? row.getAsJsonArray("granted_library").size() : 0;
                if (viewer == ownerSeat && player.seat() == ownerSeat) {
                    assertTrue(size > 0, "owner P" + ownerSeat + " must hold the entitled look");
                } else {
                    assertEquals(0, size, "viewer P" + viewer + " unexpected granted look at P"
                            + player.seat());
                }
            }
        }
        return "entitled-look-owner-only";
    }

    /** Retained composition memory belongs to the searcher alone. */
    static String rememberedOnlyOwner(Map<String, List<JsonObject>> captures, String capture,
            int ownerSeat) {
        List<JsonObject> views = requireCapture(captures, capture);
        for (int viewer = 0; viewer < 4; viewer++) {
            for (JsonElementPlayer player : players(views.get(viewer))) {
                JsonObject row = player.object();
                int size = row.has("remembered_library_composition")
                        && row.get("remembered_library_composition").isJsonArray()
                        ? row.getAsJsonArray("remembered_library_composition").size() : 0;
                if (viewer == ownerSeat && player.seat() == ownerSeat) {
                    assertTrue(size > 0, "searcher retains composition memory");
                } else {
                    assertEquals(0, size, "viewer P" + viewer + " unexpected memory of P"
                            + player.seat());
                }
            }
        }
        return "composition-memory-owner-only";
    }

    /** Opponent library positions unknown: known_library empty for all pairs. */
    static String noKnownLibrary(Map<String, List<JsonObject>> captures, String capture) {
        List<JsonObject> views = requireCapture(captures, capture);
        for (int viewer = 0; viewer < 4; viewer++) {
            for (JsonElementPlayer player : players(views.get(viewer))) {
                JsonObject row = player.object();
                if (row.has("known_library") && row.get("known_library").isJsonArray()) {
                    assertEquals(0, row.getAsJsonArray("known_library").size(),
                            "viewer P" + viewer + " knows P" + player.seat() + " library positions");
                }
            }
        }
        return "known-library-empty";
    }

    /** A private card name appears in no other principal's captured view. */
    static String nameAbsentFor(Map<String, List<JsonObject>> captures, String capture,
            int ownerSeat, String name) {
        List<JsonObject> views = requireCapture(captures, capture);
        for (int viewer = 0; viewer < 4; viewer++) {
            if (viewer == ownerSeat) {
                continue;
            }
            String serialized = Ws60Suite.GSON.toJson(views.get(viewer));
            assertTrue(!serialized.contains(name),
                    "viewer P" + viewer + " sees '" + name + "' owned by P" + ownerSeat);
        }
        return "'" + name + "'-absent-for-others";
    }

    /** The owner's captured view does contain the private card (sanity). */
    static String namePresentFor(Map<String, List<JsonObject>> captures, String capture,
            int ownerSeat, String name) {
        List<JsonObject> views = requireCapture(captures, capture);
        String serialized = Ws60Suite.GSON.toJson(views.get(ownerSeat));
        assertTrue(serialized.contains(name),
                "owner P" + ownerSeat + " view lacks '" + name + "'");
        return "'" + name + "'-present-for-owner";
    }

    static List<JsonObject> requireCapture(Map<String, List<JsonObject>> captures, String name) {
        List<JsonObject> views = captures.get(name);
        assertTrue(views != null && views.size() == 4, "missing capture " + name);
        return views;
    }

    record JsonElementPlayer(JsonObject object, int seat) {
    }

    static List<JsonElementPlayer> players(JsonObject view) {
        List<JsonElementPlayer> out = new ArrayList<>();
        for (com.google.gson.JsonElement element : view.getAsJsonArray("players")) {
            JsonObject row = element.getAsJsonObject();
            out.add(new JsonElementPlayer(row, row.get("seat").getAsInt()));
        }
        return out;
    }
}
