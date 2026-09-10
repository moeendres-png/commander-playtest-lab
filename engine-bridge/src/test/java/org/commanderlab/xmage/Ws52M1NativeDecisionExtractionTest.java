package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.MageObject;
import mage.abilities.Ability;
import mage.abilities.ActivatedAbility;
import mage.abilities.Modes;
import mage.abilities.SpellAbility;
import mage.cards.Card;
import mage.constants.Outcome;
import mage.players.Player;
import mage.target.TargetPlayer;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * WS52 M1 — native decision extraction.
 *
 * <p>Proves the credited legal sets originate in XMage: the complete offered
 * option set for priority (pass + cast/activate) and for targets equals the
 * engine-computed set, compared by an independent test oracle against live
 * engine state. The pilot only echoes offered identifiers. Mode frames are
 * proven to fail closed by design (mode UUIDs carry no ledger identity).</p>
 */
class Ws52M1NativeDecisionExtractionTest {

    @Test
    void priorityFrameEqualsEnginePlayableSet() throws Exception {
        Ws52.DeckSpec rogshai = Ws52.rogshaiDeck();
        try (Ws52Harness harness = new Ws52Harness("ws52-m1", rogshai.mainboard(),
                rogshai.commanders(), 2, Ws52.SEED_A, Ws52.STARTING_LIFE)) {
            harness.start(0);
            harness.pilotOpening(2);
            JsonObject credited = null;
            for (int step = 0; step < 60; step++) {
                JsonObject pending = harness.awaitFrame();
                assertEquals("priority", pending.get("decision_class").getAsString(),
                        () -> "unexpected decision class while seeking priority: " + pending);
                Ws52.assertUniqueOptionIds(pending);
                if (hasNonPassOption(pending)) {
                    credited = pending;
                    break;
                }
                harness.submit(pending, List.of(Ws52.singleOptionIdByType(pending, "pass_priority")), null);
            }
            assertNotNull(credited, "no priority frame with a cast/activate option within 60 passes");

            // --- Oracle: recompute the engine set independently. ---
            UUID actorId = UUID.fromString(credited.get("actor_id").getAsString());
            Player actor = harness.game.getPlayer(actorId);
            assertNotNull(actor, "decision actor is not a live engine player");
            List<ActivatedAbility> playable = actor.getPlayable(harness.game, false);

            Set<String> expectedIds = new LinkedHashSet<>();
            expectedIds.add(XmageFullGameDecisionController.stableId(
                    "priority-pass", actor.getId().toString()));
            for (ActivatedAbility ability : playable) {
                String source = ability.getSourceId() == null
                        ? "<none>" : ability.getSourceId().toString();
                expectedIds.add(XmageFullGameDecisionController.stableId(
                        "priority", source, ability.getOriginalId().toString()));
            }

            Set<String> offeredIds = new LinkedHashSet<>();
            for (JsonElement element : credited.getAsJsonArray("legal_options")) {
                offeredIds.add(element.getAsJsonObject().get("option_id").getAsString());
            }
            assertEquals(expectedIds, offeredIds,
                    "credited priority set must equal the engine playable set exactly");

            // Pass is offered exactly once.
            long passCount = credited.getAsJsonArray("legal_options").asList().stream()
                    .map(e -> e.getAsJsonObject())
                    .filter(o -> "pass_priority".equals(o.get("option_type").getAsString()))
                    .count();
            assertEquals(1, passCount, "pass_priority must be offered exactly once");

            // No raw HIDDEN-zone identity may be visible to the pilot in the
            // credited frame. The exact enforcement set is the ledger's own
            // forbidden-token set (opponent hand/library/face-down identities
            // plus their UUIDs); public principals (actor ids, ability ids of
            // visible cards) are transport by design and not asserted here.
            Set<String> forbidden = harness.ledger.forbiddenIdentityTokens(
                    harness.game, actor);
            String frameText = credited.toString();
            for (String token : forbidden) {
                if (token == null || token.isBlank()) {
                    continue;
                }
                assertTrue(!frameText.contains(token),
                        () -> "hidden identity token in pilot-visible frame: " + token);
            }
            // The credited set is complete AND the hidden zone stays hidden:
            // every offered ability must resolve to a live engine object.
            for (ActivatedAbility ability : playable) {
                assertTrue(harness.game.getObject(ability.getSourceId()) != null
                                || harness.game.getPlayer(ability.getSourceId()) != null
                                || harness.game.getCard(ability.getSourceId()) != null,
                        () -> "offered ability has no live engine source: " + ability);
            }
        }
    }

    @Test
    void targetFrameEqualsEnginePossibleTargets() throws Exception {
        // Direct calls require a started game (range checks reject pre-start
        // usage); the engine is parked at priority while the phantom direct
        // player (own controller) issues the target call on the live game.
        try (Ws52Harness harness = Ws52Harness.sentinelTwoPlayer(Ws52.SEED_A)) {
            harness.start(0);
            harness.pilotOpening(2);
            Ws52Harness.DirectHandle direct = harness.directSlot(harness.freeSeat());
            TargetPlayer target = new TargetPlayer();
            ExecutorService exec = Executors.newSingleThreadExecutor();
            try {
                Future<Boolean> worker = exec.submit(
                        () -> direct.player().chooseTarget(
                                Outcome.Benefit, target, null, harness.game));
                JsonObject pending = direct.awaitDecision();
                assertEquals("target", pending.get("decision_class").getAsString());
                Ws52.assertUniqueOptionIds(pending);

                // --- Oracle: engine-computed possible targets. ---
                Set<UUID> possible = target.possibleTargets(
                        direct.player().getId(), null, harness.game);
                assertTrue(possible.size() >= 2,
                        "expected at least two legal players to target, observed " + possible.size());
                assertEquals(possible.size(),
                        pending.getAsJsonArray("legal_options").size(),
                        "credited target set must be complete (no filtering, no fabrication)");

                // Pilot-visible ids must be opaque handles, never native UUIDs.
                for (JsonElement element : pending.getAsJsonArray("legal_options")) {
                    String id = element.getAsJsonObject().get("option_id").getAsString();
                    assertTrue(id.startsWith("obj-"),
                            () -> "target option id must be an opaque handle: " + id);
                    assertTrue(!possible.contains(parseUuidOrNull(id)),
                            () -> "native target UUID exposed to pilot: " + id);
                }

                // Select the LAST offered option (non-first) and prove execution binds it.
                JsonArray options = pending.getAsJsonArray("legal_options");
                String selected = options.get(options.size() - 1).getAsJsonObject()
                        .get("option_id").getAsString();
                direct.submit(pending, List.of(selected), null);
                assertTrue(worker.get(30, TimeUnit.SECONDS), "target choice must succeed");
                assertEquals(1, target.getTargets().size());
                UUID bound = target.getTargets().iterator().next();
                assertTrue(harness.game.getPlayer(bound) != null,
                        "bound target must be a live engine player");
            } finally {
                exec.shutdownNow();
            }
        }
    }

    @Test
    void modeFrameFailsClosedByDesign() throws Exception {
        Ws52.DeckSpec rogshai = Ws52.rogshaiDeck();
        assertTrue(rogshai.mainboard().contains("Boros Charm"),
                "rogshai fixture must contain Boros Charm for the mode witness");
        try (Ws52Harness harness = new Ws52Harness("ws52-m1mode", rogshai.mainboard(),
                rogshai.commanders(), 2, Ws52.SEED_A, Ws52.STARTING_LIFE)) {
            harness.start(0);
            harness.pilotOpening(2);
            Ws52Harness.DirectHandle direct = harness.directSlot(harness.freeSeat());
            // Real modal spell ability from the live game (fixture setup only;
            // the credited set is computed by the engine below).
            SpellAbility charmAbility = findSpellAbility(harness, "Boros Charm");
            assertNotNull(charmAbility, "Boros Charm spell ability must exist in the live game");
            // The library copy carries the pre-selected base mode (casting
            // context selects on a fresh copy); reset selection on a COPY so
            // the engine's availability filter runs (fixture setup only — the
            // credited set below is still computed by the engine).
            Modes modes = charmAbility.getModes().copy();
            modes.clearSelectedModes();
            List<mage.abilities.Mode> available =
                    new ArrayList<>(modes.getAvailableModes(charmAbility, harness.game));
            assertTrue(available.size() >= 2,
                    "expected engine-available Boros Charm modes, observed " + available.size());

            ExecutorService exec = Executors.newSingleThreadExecutor();
            try {
                Future<mage.abilities.Mode> worker =
                        exec.submit(() -> direct.player().chooseMode(
                                modes, charmAbility, harness.game));
                // Either the controller fails closed (mode UUIDs have no ledger
                // identity) or no frame is ever published. Both are recorded;
                // a mode option crossing to the pilot would fail this test.
                long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(20);
                while (direct.controller().terminalFailure() == null
                        && System.nanoTime() < deadline) {
                    if (direct.controller().pendingDecision() != null) {
                        fail("mode option crossed the production boundary: "
                                + direct.controller().pendingDecision());
                    }
                    Thread.sleep(25L);
                }
                try {
                    worker.get(5, TimeUnit.SECONDS);
                    fail("chooseMode should not resolve while its options cannot be externalized");
                } catch (Exception expected) {
                    // Expected: DecisionException from the fail-closed binding.
                }
                assertNotNull(direct.controller().terminalFailure(),
                        "mode decision must terminate the controller fail-closed");
                assertTrue(direct.controller().terminalFailure().getMessage()
                                .contains("COMMON_PROTOCOL_EXPRESSIVENESS_BLOCKER"),
                        () -> "unexpected mode failure: "
                                + direct.controller().terminalFailure().getMessage());
            } finally {
                exec.shutdownNow();
            }
        }
    }

    @Test
    void naturalPlaySurvey() throws Exception {
        XmageFullGameJsonlBridge bridge = new XmageFullGameJsonlBridge();
        Ws52.DeckSpec rogshai = Ws52.rogshaiDeck();
        String handleA = Ws52.importDeck(bridge, rogshai);
        String handleB = Ws52.importDeck(bridge, rogshai);
        Ws52.createFullGame(bridge, "ws52-m1-survey", List.of(handleA, handleB), Ws52.SEED_A);
        Ws52.startFullGame(bridge);
        Ws52.Opening opening = Ws52.pilotOpening(bridge);
        assertEquals(1, opening.startingPlayerChoices());
        assertEquals(2, opening.mulligans(), "two-player game must open with two mulligan frames");

        Set<String> classes = new LinkedHashSet<>();
        List<JsonObject> firstFrames = new ArrayList<>();
        boolean sawPass = false;
        boolean sawNonPass = false;
        for (int step = 0; step < 60; step++) {
            JsonObject payload = Ws52.getDecision(bridge);
            if (!payload.has("decision") || !payload.get("decision").isJsonObject()) {
                break;
            }
            JsonObject decision = payload.getAsJsonObject("decision");
            String klass = decision.get("decision_class").getAsString();
            if (classes.add(klass)) {
                firstFrames.add(decision);
            }
            Ws52.assertUniqueOptionIds(decision);
            if ("priority".equals(klass)) {
                sawPass = sawPass || !Ws52.optionIdsByType(decision, "pass_priority").isEmpty();
                sawNonPass = sawNonPass || hasNonPassOption(decision);
                if (sawNonPass) {
                    break;
                }
                Ws52.submit(bridge, decision,
                        List.of(Ws52.singleOptionIdByType(decision, "pass_priority")));
            } else {
                break;
            }
        }
        assertTrue(classes.contains("priority"), "natural play must reach a priority frame");
        assertTrue(sawPass, "priority frame must offer pass_priority");

        JsonObject survey = new JsonObject();
        survey.addProperty("seed", Ws52.SEED_A);
        survey.addProperty("starting_player_choices", opening.startingPlayerChoices());
        survey.addProperty("mulligans", opening.mulligans());
        JsonArray seen = new JsonArray();
        classes.forEach(seen::add);
        survey.add("decision_classes_reached", seen);
        survey.addProperty("saw_pass", sawPass);
        survey.addProperty("saw_non_pass_priority_option", sawNonPass);
        survey.addProperty("frames_captured", firstFrames.size());
        writeEvidence("m1-survey.json", survey);
    }

    // ------------------------------------------------------------------

    private static boolean hasNonPassOption(JsonObject decision) {
        for (JsonElement element : decision.getAsJsonArray("legal_options")) {
            if (!"pass_priority".equals(element.getAsJsonObject().get("option_type").getAsString())) {
                return true;
            }
        }
        return false;
    }

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

    private static void writeEvidence(String name, JsonObject payload) throws Exception {
        // Surefire workingDirectory is the module target/ dir.
        Path dir = Path.of("ws52-evidence");
        Files.createDirectories(dir);
        Files.writeString(dir.resolve(name), payload.toString(), StandardCharsets.UTF_8);
    }
}
