package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class XmageGenericExternalMulliganTest {

    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";

    @Test
    void startPublishesEngineMulliganDomainInsteadOfAutoKeep() {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);
        List<String> handles = mountainDecks(importer, "generic-mulligan-domain", 4);

        XmageGameManager.CreateResult created = manager.createCommanderGame(
                "generic-mulligan-domain",
                handles,
                0,
                40,
                true
        );
        XmageGameManager.StartResult started = manager.startGame(created.gameHandle());

        assertTrue(started.externalControl());
        XmageGameManager.LegalActionsSnapshot decision =
                manager.legalActions(created.gameHandle());
        assertEquals("mulligan", decision.decisionKind());
        XmageGenericExternalMulliganSupport.requireDomain(decision);

        // No hidden keep occurred: the first engine decision still awaits an
        // external response and the game has not reached priority.
        assertTrue(decision.decisionOffset() > 0L);
        assertEquals(2, decision.actions().size());
    }

    @Test
    void explicitKeepsReachPriorityWithoutAnyDefaultChoice() {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);
        List<String> handles = mountainDecks(importer, "generic-mulligan-keep", 4);

        XmageGameManager.CreateResult created = manager.createCommanderGame(
                "generic-mulligan-keep",
                handles,
                0,
                40,
                true
        );
        manager.startGame(created.gameHandle());

        XmageGenericExternalMulliganSupport.keepAllToPriority(
                manager, created.gameHandle(), 4);

        XmageGameManager.LegalActionsSnapshot priority =
                manager.legalActions(created.gameHandle());
        assertEquals("priority", priority.decisionKind());
        assertTrue(manager.requireGame(created.gameHandle()).isPaused());
    }

    @Test
    void selectedMulliganNeverContinuesViaADefaultBottoming() {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);
        List<String> handles = mountainDecks(importer, "generic-mulligan-bottom", 2);

        XmageGameManager.CreateResult created = manager.createCommanderGame(
                "generic-mulligan-bottom", handles, 0, 40, true);
        manager.startGame(created.gameHandle());

        XmageGameManager.LegalActionsSnapshot first = manager.legalActions(created.gameHandle());
        assertEquals("mulligan", first.decisionKind());
        XmageGenericExternalMulliganSupport.requireDomain(first);
        manager.resolveMulligan(
                created.gameHandle(), first.decisionId(), first.actorId(), false, List.of());

        XmageGameManager.LegalActionsSnapshot second = manager.legalActions(created.gameHandle());
        assertEquals("mulligan", second.decisionKind());
        XmageGenericExternalMulliganSupport.requireDomain(second);
        manager.resolveMulligan(
                created.gameHandle(), second.decisionId(), second.actorId(), true, List.of());

        // The engine now demands an explicit bottoming rather than defaulting.
        XmageGameManager.LegalActionsSnapshot bottom = manager.legalActions(created.gameHandle());
        assertEquals("mulligan_bottom", bottom.decisionKind());

        XmageGameManager.GameException failure = null;
        try {
            manager.resolveMulliganBottom(
                    created.gameHandle(), bottom.decisionId(), bottom.actorId(), List.of());
        } catch (XmageGameManager.GameException exc) {
            failure = exc;
        }
        assertTrue(failure != null,
                "the engine must never apply a default card choice for a required bottoming");
        assertTrue(failure.getMessage().contains("MULLIGAN_BOTTOM_SELECTION_INVALID"),
                "the refusal must be attributed to the selection: " + failure.getMessage());

        // Only an explicit valid selection completes the decision.
        releaseBottomDecision(manager, created.gameHandle(), bottom);
    }


    @Test
    void bottomCardIdsCannotBeInjectedIntoKeepMulliganDecision() {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);
        List<String> handles = mountainDecks(importer, "generic-mulligan-no-injection", 2);

        XmageGameManager.CreateResult created = manager.createCommanderGame(
                "generic-mulligan-no-injection",
                handles,
                0,
                40,
                true
        );
        manager.startGame(created.gameHandle());
        XmageGameManager.LegalActionsSnapshot pending =
                manager.legalActions(created.gameHandle());

        XmageGameManager.GameException failure = assertThrows(
                XmageGameManager.GameException.class,
                () -> manager.resolveMulligan(
                        created.gameHandle(),
                        pending.decisionId(),
                        pending.actorId(),
                        true,
                        List.of("fabricated-card-id")
                )
        );
        assertTrue(
                failure.getMessage().contains("bottom-card selection"),
                failure.getMessage()
        );
        // Rejection must leave the authoritative decision pending and usable.
        assertEquals(
                pending.decisionId(),
                manager.legalActions(created.gameHandle()).decisionId()
        );
    }

    @Test
    void selectedMulliganCompletesWithEngineDeclaredBottoming() {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);
        List<String> handles = mountainDecks(importer, "generic-bottom-two", 2);

        XmageGameManager.CreateResult created = manager.createCommanderGame(
                "generic-bottom-two", handles, 0, 40, true);
        manager.startGame(created.gameHandle());

        XmageGameManager.LegalActionsSnapshot first = manager.legalActions(created.gameHandle());
        assertEquals("mulligan", first.decisionKind());
        XmageGenericExternalMulliganSupport.requireDomain(first);
        manager.resolveMulligan(
                created.gameHandle(), first.decisionId(), first.actorId(), false, List.of());

        XmageGameManager.LegalActionsSnapshot second = manager.legalActions(created.gameHandle());
        assertEquals("mulligan", second.decisionKind());
        XmageGenericExternalMulliganSupport.requireDomain(second);
        manager.resolveMulligan(
                created.gameHandle(), second.decisionId(), second.actorId(), true, List.of());

        XmageGameManager.LegalActionsSnapshot bottom = manager.legalActions(created.gameHandle());
        assertEquals("mulligan_bottom", bottom.decisionKind());
        JsonObject context = bottom.context();
        assertEquals(1, context.get("min_selection").getAsInt(),
                "2P one mulligan requires exactly one card on the bottom: " + context);
        assertEquals(1, context.get("max_selection").getAsInt(),
                "engine cardinality must be exactly one here: " + context);

        List<JsonObject> offered = bottom.actions().stream()
                .filter(action -> "mulligan_bottom".equals(action.get("action_type").getAsString()))
                .toList();
        assertEquals(7, offered.size(),
                "the engine offers the acting player's whole hand as the domain: " + offered);
        String onlyCard = offered.get(0).getAsJsonObject("metadata").get("card_id").getAsString();

        manager.resolveMulliganBottom(
                created.gameHandle(), bottom.decisionId(), bottom.actorId(), List.of(onlyCard));

        XmageGameManager.LegalActionsSnapshot next = manager.legalActions(created.gameHandle());
        assertEquals("mulligan", next.decisionKind(),
                "after a resolved bottoming the engine proceeds to the next seat: " + next);
    }

    @Test
    void fourPlayerFirstMulliganIsFreeSoNoBottomingIsDemanded() {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);
        List<String> handles = mountainDecks(importer, "generic-bottom-four", 4);

        XmageGameManager.CreateResult created = manager.createCommanderGame(
                "generic-bottom-four", handles, 0, 40, true);
        manager.startGame(created.gameHandle());

        XmageGameManager.LegalActionsSnapshot first = manager.legalActions(created.gameHandle());
        assertEquals("mulligan", first.decisionKind());
        XmageGenericExternalMulliganSupport.requireDomain(first);
        manager.resolveMulligan(
                created.gameHandle(), first.decisionId(), first.actorId(), false, List.of());

        XmageGameManager.LegalActionsSnapshot second = manager.legalActions(created.gameHandle());
        assertEquals("mulligan", second.decisionKind());
        XmageGenericExternalMulliganSupport.requireDomain(second);
        manager.resolveMulligan(
                created.gameHandle(), second.decisionId(), second.actorId(), true, List.of());

        XmageGameManager.LegalActionsSnapshot next = manager.legalActions(created.gameHandle());
        assertEquals("mulligan", next.decisionKind(),
                "4P free first mulligan must not demand a bottoming: " + next);
        assertTrue(next.actions().stream().noneMatch(action ->
                        "mulligan_bottom".equals(action.get("action_type").getAsString())),
                "no bottoming action may appear for the free mulligan");
    }

    @Test
    void wrongCardinalityIsRejectedAndNoDefaultIsApplied() {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);
        List<String> handles = mountainDecks(importer, "generic-bottom-bad-count", 2);

        XmageGameManager.CreateResult created = manager.createCommanderGame(
                "generic-bottom-bad-count", handles, 0, 40, true);
        manager.startGame(created.gameHandle());

        reachBottomDecision(manager, created.gameHandle());
        XmageGameManager.LegalActionsSnapshot bottom = manager.legalActions(created.gameHandle());

        XmageGameManager.GameException failure = null;
        try {
            manager.resolveMulliganBottom(
                    created.gameHandle(), bottom.decisionId(), bottom.actorId(), List.of());
        } catch (XmageGameManager.GameException exc) {
            failure = exc;
        }
        assertTrue(failure != null, "an empty selection must not be accepted for a required bottoming");
        assertTrue(failure.getMessage().contains("MULLIGAN_BOTTOM_SELECTION_INVALID"),
                "failure must name the selection defect: " + failure.getMessage());

        releaseBottomDecision(manager, created.gameHandle(), bottom);
    }

    @Test
    void identityOutsideTheOfferedDomainIsRejected() {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);
        List<String> handles = mountainDecks(importer, "generic-bottom-foreign", 2);

        XmageGameManager.CreateResult created = manager.createCommanderGame(
                "generic-bottom-foreign", handles, 0, 40, true);
        manager.startGame(created.gameHandle());

        reachBottomDecision(manager, created.gameHandle());
        XmageGameManager.LegalActionsSnapshot bottom = manager.legalActions(created.gameHandle());

        XmageGameManager.GameException failure = null;
        try {
            manager.resolveMulliganBottom(
                    created.gameHandle(), bottom.decisionId(), bottom.actorId(),
                    List.of(java.util.UUID.randomUUID().toString()));
        } catch (XmageGameManager.GameException exc) {
            failure = exc;
        }
        assertTrue(failure != null, "an identity outside the offered domain must be rejected");
        assertTrue(failure.getMessage().contains("MULLIGAN_BOTTOM_SELECTION_INVALID"),
                "failure must name the selection defect: " + failure.getMessage());

        releaseBottomDecision(manager, created.gameHandle(), bottom);
    }

    private static void reachBottomDecision(XmageGameManager manager, String gameHandle) {
        XmageGameManager.LegalActionsSnapshot first = manager.legalActions(gameHandle);
        assertEquals("mulligan", first.decisionKind());
        XmageGenericExternalMulliganSupport.requireDomain(first);
        manager.resolveMulligan(gameHandle, first.decisionId(), first.actorId(), false, List.of());

        XmageGameManager.LegalActionsSnapshot second = manager.legalActions(gameHandle);
        assertEquals("mulligan", second.decisionKind());
        XmageGenericExternalMulliganSupport.requireDomain(second);
        manager.resolveMulligan(gameHandle, second.decisionId(), second.actorId(), true, List.of());

        XmageGameManager.LegalActionsSnapshot bottom = manager.legalActions(gameHandle);
        assertEquals("mulligan_bottom", bottom.decisionKind());
    }

    private static void releaseBottomDecision(
            XmageGameManager manager,
            String gameHandle,
            XmageGameManager.LegalActionsSnapshot bottom
    ) {
        int required = bottom.context().get("min_selection").getAsInt();
        List<String> offered = bottom.actions().stream()
                .filter(action -> "mulligan_bottom".equals(action.get("action_type").getAsString()))
                .map(action -> action.getAsJsonObject("metadata").get("card_id").getAsString())
                .toList();
        manager.resolveMulliganBottom(
                gameHandle, bottom.decisionId(), bottom.actorId(), offered.subList(0, required));
    }

    private static List<String> mountainDecks(
            XmageDeckImporter importer,
            String tag,
            int players
    ) {
        List<String> handles = new ArrayList<>();
        for (int seat = 1; seat <= players; seat++) {
            List<String> mainboard = new ArrayList<>();
            for (int index = 0; index < 99; index++) {
                mainboard.add("Mountain");
            }
            handles.add(
                    importer.importCommanderDeck(
                            tag + "-P" + seat,
                            tag + "-hash-" + seat,
                            mainboard,
                            List.of(ROGRAKH)
                    ).deckHandle()
            );
        }
        return handles;
    }
}
