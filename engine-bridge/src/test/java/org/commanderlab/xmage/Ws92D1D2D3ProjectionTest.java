package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.MageInt;
import mage.abilities.Abilities;
import mage.cards.Card;
import mage.counters.Counter;
import mage.counters.Counters;
import mage.game.CommanderFreeForAll;
import mage.game.permanent.Permanent;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * WS92 fresh runtime qualification for D1 (grant-scoped hidden-library
 * decision identity), D2 (Rules-entitled library look-window projection) and
 * D3 (principal-scoped knowledge/public-state projection) on current cfc36f.
 *
 * <p>No historical WS60 behavior credit is consumed: every assertion executes
 * against current-main bridge code with real RogShai decks. The Rules Core
 * remains the sole legality authority; these tests prove only adapter
 * projection scoping and hidden-information confinement.</p>
 */
class Ws92D1D2D3ProjectionTest {

    @Test
    void grantedLibraryEmptyOutsideWindowAndCommanderStatusPublic()
            throws Exception {
        Fixture fixture = startSession();
        // Pre-start: decks loaded, no window open, no hidden leak.
        JsonObject preStart = XmageFullGameStateRedactor.actorView(
                fixture.game(), fixture.players().get(0)
        );
        for (JsonElement element : preStart.getAsJsonArray("players")) {
            JsonObject player = element.getAsJsonObject();
            // D1/D2: no hidden library identity outside an entitled window.
            assertEquals(
                    0,
                    player.getAsJsonArray("granted_library").size(),
                    "granted_library must be empty outside a look window"
            );
            assertTrue(player.get("library_count").getAsInt() > 0);
        }

        // Start the engine so commanders reach the command zone; the first
        // pending external decision (mulligan) parks the engine thread while
        // the projection is inspected. No pilot answer is submitted here.
        fixture.session().start();
        JsonObject view = XmageFullGameStateRedactor.actorView(
                fixture.game(), fixture.players().get(0)
        );

        JsonArray players = view.getAsJsonArray("players");
        assertEquals(4, players.size());
        for (JsonElement element : players) {
            assertEquals(
                    0,
                    element.getAsJsonObject().getAsJsonArray("granted_library").size(),
                    "granted_library must be empty outside a look window"
            );
            // Command-zone commanders are public once the game starts.
            assertTrue(
                    element.getAsJsonObject().getAsJsonArray("command").size() > 0
            );
        }

        // Actor sees own hand; opponents expose no hand array.
        assertTrue(players.get(0).getAsJsonObject().has("hand"));
        for (int seat = 1; seat < 4; seat++) {
            assertFalse(players.get(seat).getAsJsonObject().has("hand"));
        }

        // D3: public commander facts for all four command pairings.
        JsonArray status = view.getAsJsonArray("commander_status");
        assertEquals(8, status.size());
        for (JsonElement element : status) {
            JsonObject entry = element.getAsJsonObject();
            assertFalse(entry.get("owner_id").getAsString().isBlank());
            assertFalse(entry.get("name").getAsString().isBlank());
            assertTrue(entry.has("commander_damage_to_player"));
            assertTrue(entry.has("casts_from_command"));
        }
    }

    @Test
    void lookWindowGrantsViewerScopedLibraryOnly()
            throws Exception {
        Fixture fixture = startSession();
        var game = fixture.game();
        var actor = fixture.players().get(0);
        var opponent = fixture.players().get(1);

        XmageFullGameStateRedactor.beginZoneFullLook(actor, actor, game);
        try {
            JsonObject view = XmageFullGameStateRedactor.actorView(game, actor);
            JsonArray players = view.getAsJsonArray("players");
            JsonObject actorEntry = players.get(0).getAsJsonObject();
            int libraryCount = actorEntry.get("library_count").getAsInt();
            // D1: entitled full-look projection matches the owned library.
            assertEquals(
                    libraryCount,
                    actorEntry.getAsJsonArray("granted_library").size()
            );
            // Per-owner scoping: the unentitled opponent library stays shut
            // inside the same viewer projection.
            for (int seat = 1; seat < 4; seat++) {
                assertEquals(
                        0,
                        players.get(seat).getAsJsonObject()
                                .getAsJsonArray("granted_library").size()
                );
            }
            // Opponent principals never observe the actor grant.
            JsonObject opponentView = XmageFullGameStateRedactor.actorView(
                    game, opponent
            );
            for (JsonElement element : opponentView.getAsJsonArray("players")) {
                assertEquals(
                        0,
                        element.getAsJsonObject()
                                .getAsJsonArray("granted_library").size()
                );
            }
        } finally {
            XmageFullGameStateRedactor.endZoneFullLook(actor, actor);
        }

        // D2: the window closes; the grant does not linger.
        JsonObject closed = XmageFullGameStateRedactor.actorView(game, actor);
        for (JsonElement element : closed.getAsJsonArray("players")) {
            assertEquals(
                    0,
                    element.getAsJsonObject()
                            .getAsJsonArray("granted_library").size()
            );
        }
    }

    @Test
    void publicPermanentProjectsBoardPublicCharacteristics()
            throws Exception {
        UUID controllerId = UUID.randomUUID();
        Permanent faceUp = stubPermanent(controllerId, false);
        Method publicPermanent = XmageFullGameStateRedactor.class.getDeclaredMethod(
                "publicPermanent", Permanent.class, mage.game.Game.class
        );
        publicPermanent.setAccessible(true);

        JsonObject item = (JsonObject) publicPermanent.invoke(null, faceUp, null);
        assertEquals(2, item.get("power").getAsInt());
        assertEquals(2, item.get("toughness").getAsInt());
        assertEquals(0, item.get("damage").getAsInt());
        JsonArray counters = item.getAsJsonArray("counters");
        assertEquals(1, counters.size());
        assertEquals("+1/+1", counters.get(0).getAsJsonObject().get("type").getAsString());
        assertEquals(1, counters.get(0).getAsJsonObject().get("count").getAsInt());
        JsonArray abilities = item.getAsJsonArray("abilities");
        assertEquals(1, abilities.size());
        assertEquals("Flying", abilities.get(0).getAsString());
        assertEquals(1, item.get("ability_count").getAsInt());

        // Face-down identities stay shut while board-public numbers project.
        Permanent faceDown = stubPermanent(controllerId, true);
        JsonObject hidden = (JsonObject) publicPermanent.invoke(null, faceDown, null);
        assertEquals(2, hidden.get("power").getAsInt());
        assertEquals(0, hidden.getAsJsonArray("abilities").size());
        assertEquals(0, hidden.get("ability_count").getAsInt());
    }

    /** Minimal interface stub: only the projection-touched methods answer. */
    private static Permanent stubPermanent(UUID controllerId, boolean faceDown) {
        UUID id = UUID.randomUUID();
        Map<String, Object> answers = new HashMap<>();
        answers.put("getId", id);
        answers.put("getName", faceDown ? "Face-down creature" : "Grizzly Bears");
        answers.put("getControllerId", controllerId);
        answers.put("isTapped", false);
        answers.put("getPower", new MageInt(2));
        answers.put("getToughness", new MageInt(2));
        answers.put("getDamage", 0);
        Counters counters = new Counters(new Counter("+1/+1", 1));
        answers.put("getCounters", counters);
        return (Permanent) Proxy.newProxyInstance(
                Ws92D1D2D3ProjectionTest.class.getClassLoader(),
                new Class<?>[]{Permanent.class},
                (proxy, method, args) -> {
                    if ("isFaceDown".equals(method.getName())) {
                        return faceDown;
                    }
                    if ("getAbilities".equals(method.getName())) {
                        return stubAbilities(faceDown);
                    }
                    if (answers.containsKey(method.getName())) {
                        return answers.get(method.getName());
                    }
                    Class<?> type = method.getReturnType();
                    if (type == boolean.class) {
                        return false;
                    }
                    if (type == int.class) {
                        return 0;
                    }
                    return null;
                }
        );
    }

    private static Abilities<?> stubAbilities(boolean faceDown) {
        List<String> rules = faceDown ? List.of() : List.of("Flying");
        return (Abilities<?>) Proxy.newProxyInstance(
                Ws92D1D2D3ProjectionTest.class.getClassLoader(),
                new Class<?>[]{Abilities.class},
                (proxy, method, args) -> {
                    if ("iterator".equals(method.getName())) {
                        List<mage.abilities.Ability> abilities = new ArrayList<>();
                        for (String rule : rules) {
                            abilities.add(stubAbility(rule));
                        }
                        return abilities.iterator();
                    }
                    if ("size".equals(method.getName())) {
                        return rules.size();
                    }
                    if ("isEmpty".equals(method.getName())) {
                        return rules.isEmpty();
                    }
                    return null;
                }
        );
    }

    private static mage.abilities.Ability stubAbility(String rule) {
        return (mage.abilities.Ability) Proxy.newProxyInstance(
                Ws92D1D2D3ProjectionTest.class.getClassLoader(),
                new Class<?>[]{mage.abilities.Ability.class},
                (proxy, method, args) -> {
                    if ("getRule".equals(method.getName())) {
                        return rule;
                    }
                    return null;
                }
        );
    }

    private static Fixture startSession()
            throws Exception {
        RuntimeDeck deck = loadRogShaiRuntimeDeck();
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = importCopies(importer, deck, 4);
        XmageFullGameSession session = new XmageFullGameSession(
                "ws92-d1d2d3-projection",
                handles,
                0,
                40,
                7017L,
                importer
        );
        CommanderFreeForAll game = field(session, "game", CommanderFreeForAll.class);
        @SuppressWarnings("unchecked")
        List<XmageFullGamePlayer> players = (List<XmageFullGamePlayer>) field(
                session, "players", List.class
        );
        return new Fixture(session, game, players);
    }

    private record Fixture(
            XmageFullGameSession session,
            CommanderFreeForAll game,
            List<XmageFullGamePlayer> players
    ) {
    }

    @SuppressWarnings("unchecked")
    private static <T> T field(Object target, String name, Class<T> type)
            throws ReflectiveOperationException {
        Field field = target.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return (T) field.get(target);
    }

    private static List<String> importCopies(
            XmageDeckImporter importer,
            RuntimeDeck deck,
            int count
    ) {
        List<String> handles = new ArrayList<>(count);
        for (int copy = 0; copy < count; copy++) {
            XmageDeckImporter.ImportResult imported = importer.importCommanderDeck(
                    deck.deckId(),
                    deck.deckHash(),
                    deck.mainboard(),
                    deck.commanders()
            );
            handles.add(imported.deckHandle());
        }
        return List.copyOf(handles);
    }

    private static RuntimeDeck loadRogShaiRuntimeDeck()
            throws IOException {
        String repoRoot = System.getProperty("commanderlab.repoRoot");
        if (repoRoot == null || repoRoot.isBlank()) {
            throw new IllegalStateException("commanderlab.repoRoot is missing");
        }
        Path path = Path.of(repoRoot, "data", "decks", "rogshai_current.json").normalize();
        JsonObject root = JsonParser.parseString(
                Files.readString(path, StandardCharsets.UTF_8)
        ).getAsJsonObject();

        List<String> mainboard = new ArrayList<>();
        List<String> commanders = new ArrayList<>();
        root.getAsJsonArray("cards").forEach(element -> {
            JsonObject card = element.getAsJsonObject();
            String name = card.get("oracle_name").getAsString();
            int quantity = card.get("quantity").getAsInt();
            String zone = card.get("zone").getAsString();
            List<String> target;
            if ("main".equals(zone)) {
                target = mainboard;
            } else if ("commander".equals(zone)) {
                target = commanders;
            } else {
                throw new IllegalStateException("Unexpected zone: " + zone);
            }
            for (int copy = 0; copy < quantity; copy++) {
                target.add(name);
            }
        });

        return new RuntimeDeck(
                root.get("deck_id").getAsString(),
                root.get("deck_hash").getAsString(),
                List.copyOf(mainboard),
                List.copyOf(commanders)
        );
    }

    private record RuntimeDeck(
            String deckId,
            String deckHash,
            List<String> mainboard,
            List<String> commanders
    ) {
    }
}
