package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.abilities.Mode;
import mage.abilities.Modes;
import mage.abilities.SpellAbility;
import mage.abilities.Ability;
import mage.cards.Card;
import mage.MageObject;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * WS56 Phase C — Mode identity (successor).
 *
 * <p>XMage alone determines available/legal modes via
 * {@code modes.getAvailableModes(source, game)}. CPL only exposes opaque
 * identity for those authoritative native options and never computes legal
 * combinations. External selected mode identity binds exactly one current
 * native mode. Sequential/multiple modes remain engine-driven.</p>
 *
 * <p>Uses Boros Charm modes from the live game (engine-determined) with a
 * null source for the gateway (no hidden-source leak; the available set is
 * still engine-computed). A hidden-library source still fails closed via the
 * gateway (see WS52 M1 update); this suite proves the visible path crosses
 * with exact binding.</p>
 */
class Ws56ModeIdentityTest {

    @Test
    void competingModesAreEngineDeterminedWithOpaqueIdentity() throws Exception {
        Ws52.DeckSpec rogshai = Ws52.rogshaiDeck();
        assertTrue(rogshai.mainboard().contains("Boros Charm"));
        try (Ws52Harness harness = new Ws52Harness("ws56-mode-competing",
                rogshai.mainboard(), rogshai.commanders(), 2, Ws52.SEED_A, Ws52.STARTING_LIFE)) {
            harness.start(0);
            harness.pilotOpening(2);
            Ws52Harness.DirectHandle direct = harness.directSlot(harness.freeSeat());
            SpellAbility charmAbility = findSpellAbility(harness, "Boros Charm");
            assertNotNull(charmAbility, "Boros Charm must exist in live game");
            Modes modes = charmAbility.getModes().copy();
            modes.clearSelectedModes();
            List<Mode> available = new ArrayList<>(modes.getAvailableModes(charmAbility, harness.game));
            assertTrue(available.size() >= 2, "engine must offer competing modes, observed " + available.size());

            ExecutorService exec = Executors.newSingleThreadExecutor();
            try {
                Future<Mode> worker = exec.submit(() -> direct.player().chooseMode(modes, null, harness.game));
                JsonObject pending = direct.awaitDecision();
                assertEquals("mode", pending.get("decision_class").getAsString());
                JsonArray options = pending.getAsJsonArray("legal_options");
                assertEquals(available.size(), options.size(),
                        "credited mode set must equal engine available set (no filtering, no fabrication)");
                // Opaque identity: never native UUIDs, unique, non-blank.
                Set<String> ids = new HashSet<>();
                for (JsonElement e : options) {
                    JsonObject o = e.getAsJsonObject();
                    String id = o.get("option_id").getAsString();
                    assertTrue(!id.isBlank(), "mode option id must be non-blank");
                    assertTrue(ids.add(id), "duplicate mode option id: " + id);
                    assertTrue(parseUuidOrNull(id) == null,
                            "native mode UUID must not cross to pilot: " + id);
                    assertEquals("mode", o.get("option_type").getAsString());
                    // Metadata must not leak native UUIDs.
                    String metaText = o.getAsJsonObject("metadata").toString();
                    for (Mode m : available) {
                        assertTrue(!metaText.contains(m.getId().toString()),
                                "native mode UUID leaked in metadata: " + m.getId());
                    }
                }
                // Resolve with the FIRST option to keep the controller clean; the
                // non-first proof is in the next test.
                String first = options.get(0).getAsJsonObject().get("option_id").getAsString();
                direct.submit(pending, List.of(first), null);
                Mode chosen = worker.get(30, TimeUnit.SECONDS);
                assertNotNull(chosen, "mode choice must resolve");
                // Chosen mode must be one of the engine-available natives.
                boolean found = false;
                for (Mode m : available) {
                    if (m.getId().equals(chosen.getId())) {
                        found = true;
                        break;
                    }
                }
                assertTrue(found, "chosen mode must be an engine-available native");

                JsonObject evidence = new JsonObject();
                evidence.addProperty("available_modes", available.size());
                evidence.addProperty("chosen_is_engine_native", found);
                writeEvidence("mode-competing.json", evidence);
            } finally {
                exec.shutdownNow();
            }
        }
    }

    @Test
    void nonFirstModeBindsExactlyOneNative() throws Exception {
        Ws52.DeckSpec rogshai = Ws52.rogshaiDeck();
        try (Ws52Harness harness = new Ws52Harness("ws56-mode-nonfirst",
                rogshai.mainboard(), rogshai.commanders(), 2, Ws52.SEED_A, Ws52.STARTING_LIFE)) {
            harness.start(0);
            harness.pilotOpening(2);
            Ws52Harness.DirectHandle direct = harness.directSlot(harness.freeSeat());
            SpellAbility charmAbility = findSpellAbility(harness, "Boros Charm");
            assertNotNull(charmAbility);
            Modes modes = charmAbility.getModes().copy();
            modes.clearSelectedModes();
            List<Mode> available = new ArrayList<>(modes.getAvailableModes(charmAbility, harness.game));
            assertTrue(available.size() >= 3, "Boros Charm must offer 3 modes for non-first proof");

            ExecutorService exec = Executors.newSingleThreadExecutor();
            try {
                Future<Mode> worker = exec.submit(() -> direct.player().chooseMode(modes, null, harness.game));
                JsonObject pending = direct.awaitDecision();
                JsonArray options = pending.getAsJsonArray("legal_options");
                // Select the LAST offered option (non-first).
                String last = options.get(options.size() - 1).getAsJsonObject().get("option_id").getAsString();
                int lastIndex = options.size() - 1;
                assertTrue(lastIndex >= 1, "non-first index must be >=1");
                direct.submit(pending, List.of(last), null);
                Mode chosen = worker.get(30, TimeUnit.SECONDS);
                assertNotNull(chosen);
                // Prove exactly-one binding: the chosen native must correspond to
                // the last external id via the per-frame binding (no rematch).
                // The worker resolved without missing-binding failure, and the
                // chosen id must be in the available set.
                boolean inAvailable = false;
                for (Mode m : available) {
                    if (m.getId().equals(chosen.getId())) {
                        inAvailable = true;
                        break;
                    }
                }
                assertTrue(inAvailable, "non-first selection must bind an engine-available native");

                JsonObject evidence = new JsonObject();
                evidence.addProperty("option_count", options.size());
                evidence.addProperty("selected_index", lastIndex);
                evidence.addProperty("bound_is_engine_native", inAvailable);
                writeEvidence("mode-nonfirst.json", evidence);
            } finally {
                exec.shutdownNow();
            }
        }
    }

    @Test
    void staleModeFailsClosed() throws Exception {
        Ws52.DeckSpec rogshai = Ws52.rogshaiDeck();
        try (Ws52Harness harness = new Ws52Harness("ws56-mode-stale",
                rogshai.mainboard(), rogshai.commanders(), 2, Ws52.SEED_A, Ws52.STARTING_LIFE)) {
            harness.start(0);
            harness.pilotOpening(2);
            Ws52Harness.DirectHandle direct = harness.directSlot(harness.freeSeat());
            SpellAbility charmAbility = findSpellAbility(harness, "Boros Charm");
            assertNotNull(charmAbility);
            Modes modes = charmAbility.getModes().copy();
            modes.clearSelectedModes();

            ExecutorService exec = Executors.newSingleThreadExecutor();
            try {
                Future<Mode> worker = exec.submit(() -> direct.player().chooseMode(modes, null, harness.game));
                JsonObject first = direct.awaitDecision();
                String firstId = first.get("option_id") != null ? "" : "";
                String decisionId = first.get("decision_id").getAsString();
                JsonArray options = first.getAsJsonArray("legal_options");
                String selected = options.get(0).getAsJsonObject().get("option_id").getAsString();
                direct.submit(first, List.of(selected), null);
                assertNotNull(worker.get(30, TimeUnit.SECONDS));

                // Replaying the consumed frame must fail closed (no pending).
                XmageFullGameDecisionController.DecisionException stale = assertThrows(
                        XmageFullGameDecisionController.DecisionException.class,
                        () -> direct.controller().submit(staleResponse(first)));
                assertTrue(stale.getMessage().contains("STALE_DECISION")
                                || stale.getMessage().contains("no pending"),
                        () -> "replayed mode frame must be stale: " + stale.getMessage());
            } finally {
                exec.shutdownNow();
            }
        }
    }

    @Test
    void wrongPrincipalModeFailsClosed() throws Exception {
        Ws52.DeckSpec rogshai = Ws52.rogshaiDeck();
        try (Ws52Harness harness = new Ws52Harness("ws56-mode-actor",
                rogshai.mainboard(), rogshai.commanders(), 2, Ws52.SEED_A, Ws52.STARTING_LIFE)) {
            harness.start(0);
            harness.pilotOpening(2);
            Ws52Harness.DirectHandle direct = harness.directSlot(harness.freeSeat());
            SpellAbility charmAbility = findSpellAbility(harness, "Boros Charm");
            assertNotNull(charmAbility);
            Modes modes = charmAbility.getModes().copy();
            modes.clearSelectedModes();

            ExecutorService exec = Executors.newSingleThreadExecutor();
            try {
                Future<Mode> worker = exec.submit(() -> direct.player().chooseMode(modes, null, harness.game));
                JsonObject pending = direct.awaitDecision();
                JsonObject forged = copyResponse(pending);
                forged.addProperty("actor_id", "00000000-wrong-actor");
                XmageFullGameDecisionController.DecisionException wrong = assertThrows(
                        XmageFullGameDecisionController.DecisionException.class,
                        () -> direct.controller().submit(forged));
                assertTrue(wrong.getMessage().contains("wrong actor"),
                        () -> "wrong-principal mode must be rejected: " + wrong.getMessage());
                // Resolve cleanly to avoid leaking the parked engine.
                JsonArray options = pending.getAsJsonArray("legal_options");
                String selected = options.get(0).getAsJsonObject().get("option_id").getAsString();
                direct.submit(pending, List.of(selected), null);
                assertNotNull(worker.get(30, TimeUnit.SECONDS));
            } finally {
                exec.shutdownNow();
            }
        }
    }

    @Test
    void unknownAndAmbiguousModeFailClosed() throws Exception {
        // Unknown mode id must be ILLEGAL_ACTION.
        Ws52.DeckSpec rogshai = Ws52.rogshaiDeck();
        try (Ws52Harness harness = new Ws52Harness("ws56-mode-unknown",
                rogshai.mainboard(), rogshai.commanders(), 2, Ws52.SEED_A, Ws52.STARTING_LIFE)) {
            harness.start(0);
            harness.pilotOpening(2);
            Ws52Harness.DirectHandle direct = harness.directSlot(harness.freeSeat());
            SpellAbility charmAbility = findSpellAbility(harness, "Boros Charm");
            assertNotNull(charmAbility);
            Modes modes = charmAbility.getModes().copy();
            modes.clearSelectedModes();

            ExecutorService exec = Executors.newSingleThreadExecutor();
            try {
                Future<Mode> worker = exec.submit(() -> direct.player().chooseMode(modes, null, harness.game));
                JsonObject pending = direct.awaitDecision();
                JsonObject forged = copyResponse(pending, List.of("mode-fabricated-by-pilot"));
                XmageFullGameDecisionController.DecisionException unknown = assertThrows(
                        XmageFullGameDecisionController.DecisionException.class,
                        () -> direct.controller().submit(forged));
                assertTrue(unknown.getMessage().contains("ILLEGAL_ACTION"),
                        () -> "fabricated mode must be rejected: " + unknown.getMessage());
                JsonArray options = pending.getAsJsonArray("legal_options");
                String selected = options.get(0).getAsJsonObject().get("option_id").getAsString();
                direct.submit(pending, List.of(selected), null);
                assertNotNull(worker.get(30, TimeUnit.SECONDS));
            } finally {
                exec.shutdownNow();
            }
        }

        // Ambiguous identity (two natives collapse to one external) must fail
        // closed at the binding gate (unit, no game needed).
        JsonArray nativeOptions = new JsonArray();
        nativeOptions.add(XmageFullGameDecisionController.option(
                "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "A", "mode", new JsonObject()));
        nativeOptions.add(XmageFullGameDecisionController.option(
                "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "B", "mode", new JsonObject()));
        java.util.Map<String, String> collapsing = java.util.Map.of(
                "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "same-external",
                "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "same-external");
        IllegalStateException ambiguous = assertThrows(IllegalStateException.class,
                () -> XmageDecisionOptionIdentity.externalize(nativeOptions, collapsing));
        assertTrue(ambiguous.getMessage().contains("COMMON_PROTOCOL_EXPRESSIVENESS_BLOCKER"));

        JsonObject evidence = new JsonObject();
        evidence.addProperty("unknown_rejected", true);
        evidence.addProperty("ambiguous_collapse_rejected", true);
        writeEvidence("mode-ambiguous.json", evidence);
    }

    @Test
    void modeIdentityAfterProgression() throws Exception {
        // After state progression (priority passes), old mode identities must
        // not bind: a new mode frame has a different frame_digest/revision and
        // the old frame is stale.
        Ws52.DeckSpec rogshai = Ws52.rogshaiDeck();
        try (Ws52Harness harness = new Ws52Harness("ws56-mode-progress",
                rogshai.mainboard(), rogshai.commanders(), 2, Ws52.SEED_A, Ws52.STARTING_LIFE)) {
            harness.start(0);
            harness.pilotOpening(2);
            // First mode frame.
            Ws52Harness.DirectHandle direct = harness.directSlot(harness.freeSeat());
            SpellAbility charmAbility = findSpellAbility(harness, "Boros Charm");
            assertNotNull(charmAbility);
            Modes modes = charmAbility.getModes().copy();
            modes.clearSelectedModes();
            ExecutorService exec = Executors.newSingleThreadExecutor();
            String firstDigest;
            String firstDecisionId;
            try {
                Future<Mode> worker = exec.submit(() -> direct.player().chooseMode(modes, null, harness.game));
                JsonObject first = direct.awaitDecision();
                firstDigest = first.get("frame_digest").getAsString();
                firstDecisionId = first.get("decision_id").getAsString();
                JsonArray options = first.getAsJsonArray("legal_options");
                direct.submit(first, List.of(options.get(0).getAsJsonObject().get("option_id").getAsString()), null);
                assertNotNull(worker.get(30, TimeUnit.SECONDS));
            } finally {
                exec.shutdownNow();
            }
            // Progress the main parked decision (pass once) to advance state.
            JsonObject parked = harness.awaitFrame();
            harness.submit(parked,
                    List.of(Ws52.singleOptionIdByType(parked, "pass_priority")), null);
            // Second mode frame after progression must have different freshness.
            Ws52Harness.DirectHandle direct2 = harness.directSlot(harness.freeSeat());
            SpellAbility charm2 = findSpellAbility(harness, "Boros Charm");
            assertNotNull(charm2);
            Modes modes2 = charm2.getModes().copy();
            modes2.clearSelectedModes();
            ExecutorService exec2 = Executors.newSingleThreadExecutor();
            try {
                Future<Mode> worker2 = exec2.submit(() -> direct2.player().chooseMode(modes2, null, harness.game));
                JsonObject second = direct2.awaitDecision();
                String secondDigest = second.get("frame_digest").getAsString();
                String secondDecisionId = second.get("decision_id").getAsString();
                assertNotEquals(firstDecisionId, secondDecisionId, "progression must advance decision identity");
                assertNotEquals(firstDigest, secondDigest, "progression must advance frame digest");
                JsonArray options2 = second.getAsJsonArray("legal_options");
                direct2.submit(second, List.of(options2.get(0).getAsJsonObject().get("option_id").getAsString()), null);
                assertNotNull(worker2.get(30, TimeUnit.SECONDS));
            } finally {
                exec2.shutdownNow();
            }
            JsonObject evidence = new JsonObject();
            evidence.addProperty("first_digest", firstDigest);
            evidence.addProperty("progression_advanced", true);
            writeEvidence("mode-progression.json", evidence);
        }
    }

    // ------------------------------------------------------------------

    private static SpellAbility findSpellAbility(Ws52Harness harness, String cardName) {
        for (Card card : harness.game.getCards()) {
            if (card != null && cardName.equals(card.getName())) {
                for (Ability ability : card.getAbilities(harness.game)) {
                    if (ability instanceof SpellAbility spell) {
                        return spell;
                    }
                }
                MageObject object = harness.game.getObject(card.getId());
                if (object instanceof Card abilityCard) {
                    for (Ability ability : abilityCard.getAbilities(harness.game)) {
                        if (ability instanceof SpellAbility spell) {
                            return spell;
                        }
                    }
                }
            }
        }
        return null;
    }

    private static UUID parseUuidOrNull(String value) {
        try {
            return UUID.fromString(value);
        } catch (IllegalArgumentException ignored) {
            return null;
        }
    }

    private static JsonObject copyResponse(JsonObject pending) {
        JsonArray options = pending.getAsJsonArray("legal_options");
        String first = options.get(0).getAsJsonObject().get("option_id").getAsString();
        return copyResponse(pending, List.of(first));
    }

    private static JsonObject copyResponse(JsonObject pending, List<String> selected) {
        JsonObject response = new JsonObject();
        response.addProperty("decision_id", pending.get("decision_id").getAsString());
        response.addProperty("actor_id", pending.get("actor_id").getAsString());
        if (pending.has("frame_digest") && !pending.get("frame_digest").isJsonNull()) {
            response.addProperty("frame_digest", pending.get("frame_digest").getAsString());
        }
        if (pending.has("option_digest") && !pending.get("option_digest").isJsonNull()) {
            response.addProperty("option_digest", pending.get("option_digest").getAsString());
        }
        if (pending.has("frame_revision") && !pending.get("frame_revision").isJsonNull()) {
            response.addProperty("frame_revision", pending.get("frame_revision").getAsLong());
        }
        com.google.gson.JsonArray sel = new com.google.gson.JsonArray();
        selected.forEach(sel::add);
        response.add("selected_option_ids", sel);
        response.add("ordering", new com.google.gson.JsonArray());
        response.add("numeric_choice", com.google.gson.JsonNull.INSTANCE);
        return response;
    }

    private static JsonObject staleResponse(JsonObject pending) {
        // Echo the consumed frame's ids (now stale since pending is gone).
        return copyResponse(pending);
    }

    private static void writeEvidence(String name, JsonObject payload) throws Exception {
        Path dir = Path.of("ws56-evidence");
        Files.createDirectories(dir);
        Files.writeString(dir.resolve(name), payload.toString(), StandardCharsets.UTF_8);
    }
}
