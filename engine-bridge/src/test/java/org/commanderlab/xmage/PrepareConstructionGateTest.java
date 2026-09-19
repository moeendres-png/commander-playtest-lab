package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.cards.repository.CardInfo;
import mage.cards.repository.CardRepository;
import mage.game.Game;
import mage.players.Player;
import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Owned construction gate (workstream prepare-behavior-qualification-20260919).
 *
 * <p>Classifies all 11 SOS prepare-relevant fixture identities against the
 * pinned xmage-1.4.61 card repository:</p>
 *
 * <ul>
 *   <li>9 Prepare-creature DFCs: genuinely absent from the pinned artifact
 *   (both {@code //} and front-face forms resolve NULL; DFC-lookup control
 *   proves the lookup shape itself is sound). Unknown names fail closed at
 *   import with {@code UNKNOWN_CARD_NAME}; no game is created.</li>
 *   <li>2 enablers (Biblioplex Tomekeeper, Skycoach Waypoint): resolve with
 *   exact identity, import into legal Commander shells, and start real
 *   four-player Commander games.</li>
 *   <li>Adversarial: standalone {@code Seething Song} resolves to the
 *   unrelated SLD reprint ({@code mage.cards.s.SeethingSong}), never to the
 *   unresolvable Prepare back face. Name similarity must never confer
 *   behavior credit.</li>
 * </ul>
 *
 * <p>Root cause for the 9 absences: ENGINE_PIN_GAP — the pinned 1.4.61
 * artifact predates SOS Prepare-DFC implementation present in mage source
 * (e.g. {@code [SOS] Implement Blazing Firesinger}). No Forge/mage source is
 * edited here; creature behavior paths stay NOT_RUN (blocked) with cause.</p>
 *
 * <p>Sequencing note: this class never calls {@code CardScanner.scan()}
 * directly. The importer owns verified repository initialization
 * (fail-closed against externally preinitialized scanners), so the warmup
 * test runs first ({@code @Order(1)}) and every direct repository read runs
 * after the verified READY state is established.</p>
 */
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class PrepareConstructionGateTest {

    static final List<String> PREPARE_CREATURE_DFC_FULL_NAMES = List.of(
            "Blazing Firesinger // Seething Song",
            "Cheerful Osteomancer // Raise Dead",
            "Dirgur Focusmage // Braingeyser",
            "Goblin Glasswright // Craft with Pride",
            "Inspired Skypainter // Maestro's Gift",
            "Sanar, Unfinished Genius // Wild Idea",
            "Spellbook Seeker // Careful Study",
            "Studious First-Year // Rampant Growth",
            "Tam, Observant Sequencer // Deep Sight"
    );

    static final List<String> PREPARE_CREATURE_FRONT_NAMES = List.of(
            "Blazing Firesinger",
            "Cheerful Osteomancer",
            "Dirgur Focusmage",
            "Goblin Glasswright",
            "Inspired Skypainter",
            "Sanar, Unfinished Genius",
            "Spellbook Seeker",
            "Studious First-Year",
            "Tam, Observant Sequencer"
    );

    @Test
    @Order(1)
    void repositoryWarmupViaVerifiedImporterInit() throws Exception {
        RuntimeDeck base = loadRogShaiRuntimeDeck();

        XmageDeckImporter importer = new XmageDeckImporter();
        XmageDeckImporter.ImportResult imported = importer.importCommanderDeck(
                "prepare-probe/warmup",
                "probe-hash-warmup",
                base.mainboard(),
                base.commanders());

        assertEquals(98, imported.mainboardCount());
        assertEquals(2, imported.commanderCount());
        assertNotNull(CardRepository.instance);
    }

    @Test
    @Order(2)
    void dfcLookupControlResolvesOnPinnedEngine() {
        CardInfo slashForm = CardRepository.instance.findCard(
                "Delver of Secrets // Insectile Aberration", true);
        assertNotNull(
                slashForm,
                "DFC //-form lookup itself must work on the pinned engine");
        assertEquals("Delver of Secrets", slashForm.getName());

        CardInfo frontForm =
                CardRepository.instance.findCard("Delver of Secrets", true);
        assertNotNull(
                frontForm,
                "DFC front-face lookup itself must work on the pinned engine");
        assertEquals("Delver of Secrets", frontForm.getName());
    }

    @Test
    @Order(3)
    void prepareCreatureDfcIdentitiesAreUnknownOnPinnedEngine() {
        List<String> resolved = new ArrayList<>();
        for (String name : PREPARE_CREATURE_DFC_FULL_NAMES) {
            CardInfo info = CardRepository.instance.findCard(name, true);
            if (info != null) {
                resolved.add(name + " -> " + info.getName());
            }
            assertNull(
                    info,
                    "Prepare DFC must be absent from pinned xmage-1.4.61: "
                            + name);
        }
        for (String name : PREPARE_CREATURE_FRONT_NAMES) {
            CardInfo info = CardRepository.instance.findCard(name, true);
            if (info != null) {
                resolved.add(name + " -> " + info.getName());
            }
            assertNull(
                    info,
                    "Prepare front face must be absent from pinned xmage-1.4.61: "
                            + name);
        }
        assertTrue(resolved.isEmpty(), "no Prepare creature may resolve");
    }

    @Test
    @Order(4)
    void prepareEnablersResolveWithExactIdentity() {
        CardInfo tomekeeper =
                CardRepository.instance.findCard("Biblioplex Tomekeeper", true);
        assertNotNull(tomekeeper, "Biblioplex Tomekeeper must resolve");
        assertEquals("Biblioplex Tomekeeper", tomekeeper.getName());
        assertEquals(
                "mage.cards.b.BiblioplexTomekeeper", tomekeeper.getClassName());

        CardInfo waypoint =
                CardRepository.instance.findCard("Skycoach Waypoint", true);
        assertNotNull(waypoint, "Skycoach Waypoint must resolve");
        assertEquals("Skycoach Waypoint", waypoint.getName());
        assertEquals(
                "mage.cards.s.SkycoachWaypoint", waypoint.getClassName());
    }

    @Test
    @Order(5)
    void seethingSongStandaloneIsNotThePrepareBackFace() {
        CardInfo info =
                CardRepository.instance.findCard("Seething Song", true);
        assertNotNull(info, "standalone Seething Song must resolve");
        assertEquals("Seething Song", info.getName());
        assertEquals(
                "mage.cards.s.SeethingSong",
                info.getClassName(),
                "resolved Seething Song must be the standalone reprint, "
                        + "never the unresolvable Prepare back face");
    }

    @Test
    @Order(6)
    void unknownPrepareNameFailsClosedAtImport() throws Exception {
        RuntimeDeck base = loadRogShaiRuntimeDeck();

        List<String> mainboard = new ArrayList<>(base.mainboard());
        mainboard.set(0, "Blazing Firesinger");

        XmageDeckImporter importer = new XmageDeckImporter();

        XmageDeckImporter.ImportException error = assertThrows(
                XmageDeckImporter.ImportException.class,
                () -> importer.importCommanderDeck(
                        "prepare-probe/unknown-creature",
                        "probe-hash-unknown",
                        mainboard,
                        base.commanders()));

        assertTrue(
                error.getMessage().contains("UNKNOWN_CARD_NAME"),
                "unknown Prepare creature must fail closed at resolve, got: "
                        + error.getMessage());
        assertEquals(0, importer.storedDeckCount());
    }

    @Test
    @Order(7)
    void tomekeeperDeckImportsAndStartsRealFourPlayerGame() throws Exception {
        RuntimeDeck base = loadRogShaiRuntimeDeck();

        List<String> mainboard = new ArrayList<>(base.mainboard());
        mainboard.set(0, "Biblioplex Tomekeeper");

        XmageDeckImporter importer = new XmageDeckImporter();
        XmageDeckImporter.ImportResult imported = importer.importCommanderDeck(
                "prepare-probe/tomekeeper",
                "probe-hash-tomekeeper",
                mainboard,
                base.commanders());

        assertEquals(98, imported.mainboardCount());
        assertEquals(2, imported.commanderCount());

        List<String> handles = new ArrayList<>();
        for (int copy = 0; copy < 4; copy++) {
            handles.add(importer.importCommanderDeck(
                    "prepare-probe/tomekeeper-copy-" + copy,
                    "probe-hash-tomekeeper-" + copy,
                    mainboard,
                    base.commanders()).deckHandle());
        }

        XmageGameManager manager = new XmageGameManager(importer);
        XmageGameManager.CreateResult created = manager.createCommanderGame(
                "prepare-probe/tomekeeper-4p", handles, 0, 40);
        assertEquals(4, created.playerCount());

        XmageGameManager.StartResult started =
                manager.startGame(created.gameHandle());
        assertEquals(4, started.playerCount());
        assertTrue(started.paused());

        Game game = manager.requireGame(created.gameHandle());
        assertEquals(4, game.getPlayers().size());
        for (Player player : game.getPlayers().values()) {
            assertEquals(40, player.getLife());
            assertEquals(7, player.getHand().size());
        }
    }

    @Test
    @Order(8)
    void waypointDeckImportsCommanderLegal() throws Exception {
        RuntimeDeck base = loadRogShaiRuntimeDeck();

        List<String> mainboard = new ArrayList<>(base.mainboard());
        mainboard.set(0, "Skycoach Waypoint");

        XmageDeckImporter importer = new XmageDeckImporter();
        XmageDeckImporter.ImportResult imported = importer.importCommanderDeck(
                "prepare-probe/waypoint",
                "probe-hash-waypoint",
                mainboard,
                base.commanders());

        assertEquals(98, imported.mainboardCount());
        assertEquals(2, imported.commanderCount());
        assertNotNull(importer.requireDeck(imported.deckHandle()));
    }

    private static RuntimeDeck loadRogShaiRuntimeDeck() throws Exception {
        String repoRoot = System.getProperty("commanderlab.repoRoot");
        assertNotNull(repoRoot, "commanderlab.repoRoot must be supplied");

        Path path = Path.of(repoRoot, "data", "decks", "rogshai_current.json");
        JsonObject root = JsonParser.parseString(
                Files.readString(path, StandardCharsets.UTF_8))
                .getAsJsonObject();

        JsonArray cards = root.getAsJsonArray("cards");
        List<String> mainboard = new ArrayList<>();
        List<String> commanders = new ArrayList<>();
        for (int i = 0; i < cards.size(); i++) {
            JsonObject card = cards.get(i).getAsJsonObject();
            String name = card.get("oracle_name").getAsString();
            int quantity = card.get("quantity").getAsInt();
            String zone = card.get("zone").getAsString();
            List<String> target = "commander".equals(zone)
                    ? commanders : mainboard;
            for (int copy = 0; copy < quantity; copy++) {
                target.add(name);
            }
        }

        assertEquals(98, mainboard.size());
        assertEquals(2, commanders.size());

        return new RuntimeDeck(
                root.get("deck_id").getAsString(),
                root.get("deck_hash").getAsString(),
                List.copyOf(mainboard),
                List.copyOf(commanders));
    }

    private record RuntimeDeck(
            String deckId,
            String deckHash,
            List<String> mainboard,
            List<String> commanders) {
    }
}
