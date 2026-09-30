package org.commanderlab.xmage;

import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * PB-01 (provider-blocker register, final current boundary 2026-09-27):
 * the generic Protocol-2 lane exposes an external decision surface only for a
 * game created with {@code external_control=true}. A game created without it
 * must fail closed with {@code LEGAL_ACTIONS_UNAVAILABLE} instead of
 * publishing a decision a pilot could answer, so an adapter that omits the
 * parameter cannot be mistaken for one driving the game.
 */
class XmageExternalControlRequiredTest {

    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";

    @Test
    void legalActionsFailClosedWhenTheGameWasNotCreatedForExternalControl() {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);
        XmageGameManager.CreateResult created = manager.createCommanderGame(
                "pb01-no-external-control", decks(importer, "pb01-no-external-control"), 0, 40, false);

        XmageGameManager.GameException beforeStart = assertThrows(
                XmageGameManager.GameException.class, () -> manager.legalActions(created.gameHandle()));
        assertTrue(beforeStart.getMessage().startsWith("LEGAL_ACTIONS_UNAVAILABLE"), beforeStart.getMessage());

        XmageGameManager.StartResult started = manager.startGame(created.gameHandle());
        assertFalse(started.externalControl(), "the start result reports that nobody external drives this game");
        XmageGameManager.GameException failure = assertThrows(
                XmageGameManager.GameException.class, () -> manager.legalActions(created.gameHandle()));
        assertEquals(
                "LEGAL_ACTIONS_UNAVAILABLE: game was not created with external_control=true",
                failure.getMessage());
    }

    @Test
    void theSameGameCreatedForExternalControlPublishesAnEngineDecision() {
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageGameManager manager = new XmageGameManager(importer);
        XmageGameManager.CreateResult created = manager.createCommanderGame(
                "pb01-external-control", decks(importer, "pb01-external-control"), 0, 40, true);
        assertTrue(manager.startGame(created.gameHandle()).externalControl());
        assertEquals("mulligan", manager.legalActions(created.gameHandle()).decisionKind(),
                "control: with external_control=true the first engine decision is published");
    }

    private static List<String> decks(XmageDeckImporter importer, String tag) {
        List<String> handles = new ArrayList<>();
        for (int seat = 1; seat <= 4; seat++) {
            List<String> mainboard = new ArrayList<>();
            for (int index = 0; index < 99; index++) {
                mainboard.add("Mountain");
            }
            handles.add(importer.importCommanderDeck(
                    tag + "-P" + seat, tag + "-hash-" + seat, mainboard, List.of(ROGRAKH)).deckHandle());
        }
        return handles;
    }
}
