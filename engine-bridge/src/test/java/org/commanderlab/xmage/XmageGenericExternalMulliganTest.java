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
    void selectedMulliganFailsClosedAtUnprojectedLondonBottoming() {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);
        List<String> handles = mountainDecks(importer, "generic-mulligan-bottom", 2);

        XmageGameManager.CreateResult created = manager.createCommanderGame(
                "generic-mulligan-bottom",
                handles,
                0,
                40,
                true
        );
        manager.startGame(created.gameHandle());

        XmageGameManager.LegalActionsSnapshot first =
                manager.legalActions(created.gameHandle());
        assertEquals("mulligan", first.decisionKind());
        XmageGenericExternalMulliganSupport.requireDomain(first);

        // The pilot explicitly chooses mulligan. This is not an inferred
        // preference and not the first action in an arbitrary order.
        manager.resolveMulligan(
                created.gameHandle(),
                first.decisionId(),
                first.actorId(),
                false,
                List.of()
        );

        XmageGameManager.GameException failure = null;
        for (int decision = 0; decision < 12 && failure == null; decision++) {
            XmageGameManager.LegalActionsSnapshot pending =
                    manager.legalActions(created.gameHandle());
            assertEquals("mulligan", pending.decisionKind());
            XmageGenericExternalMulliganSupport.requireDomain(pending);
            try {
                manager.resolveMulligan(
                        created.gameHandle(),
                        pending.decisionId(),
                        pending.actorId(),
                        true,
                        List.of()
                );
            } catch (XmageGameManager.GameException exc) {
                failure = exc;
            }
        }

        if (failure == null) {
            throw new AssertionError(
                    "selected 2P London mulligan reached no explicit bottom-card fail-closed boundary"
            );
        }
        assertTrue(
                failure.getMessage().contains("London bottom-card selection"),
                failure.getMessage()
        );
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
