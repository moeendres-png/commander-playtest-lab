package org.mage.test.ws26;

import mage.constants.PhaseStep;
import mage.constants.Zone;
import org.junit.Test;
import org.mage.test.serverside.base.CardTestCommander4Players;

/**
 * Qualification-only representative WS-26 rules fixtures executed inside the
 * pinned XMage Mage.Tests harness. Commander Lab defines scenarios/assertions;
 * XMage owns legality, stack processing, targets, replacements, continuous
 * effects, combat, commander rules and state-based actions.
 */
public class Ws26RepresentativeRulesTest extends CardTestCommander4Players {

    @Test
    public void microStackTargetLifo() {
        addCard(Zone.HAND, playerA, "Lightning Bolt");
        addCard(Zone.BATTLEFIELD, playerA, "Mountain");
        addCard(Zone.HAND, playerB, "Giant Growth");
        addCard(Zone.BATTLEFIELD, playerB, "Forest");
        addCard(Zone.BATTLEFIELD, playerB, "Grizzly Bears");

        castSpell(1, PhaseStep.PRECOMBAT_MAIN, playerA, "Lightning Bolt", "Grizzly Bears");
        castSpell(1, PhaseStep.PRECOMBAT_MAIN, playerB, "Giant Growth", "Grizzly Bears", "Lightning Bolt");

        setStopAt(1, PhaseStep.BEGIN_COMBAT);
        execute();

        assertPermanentCount(playerB, "Grizzly Bears", 1);
        assertPowerToughness(playerB, "Grizzly Bears", 5, 5);
    }

    @Test
    public void microReplacementRestInPeace() {
        addCard(Zone.BATTLEFIELD, playerA, "Rest in Peace");
        addCard(Zone.HAND, playerA, "Lightning Bolt");
        addCard(Zone.BATTLEFIELD, playerA, "Mountain");
        addCard(Zone.BATTLEFIELD, playerB, "Grizzly Bears");

        castSpell(1, PhaseStep.PRECOMBAT_MAIN, playerA, "Lightning Bolt", "Grizzly Bears", true);

        setStopAt(1, PhaseStep.BEGIN_COMBAT);
        execute();

        assertPermanentCount(playerB, "Grizzly Bears", 0);
        assertGraveyardCount(playerB, "Grizzly Bears", 0);
        assertExileCount(playerB, "Grizzly Bears", 1);
        assertExileCount(playerA, "Lightning Bolt", 1);
    }

    @Test
    public void microContinuousGloriousAnthem() {
        addCard(Zone.BATTLEFIELD, playerA, "Glorious Anthem");
        addCard(Zone.BATTLEFIELD, playerA, "Grizzly Bears");

        setStopAt(1, PhaseStep.PRECOMBAT_MAIN);
        execute();

        assertPowerToughness(playerA, "Grizzly Bears", 3, 3);
    }

    @Test
    public void multiplayerMultipleDefenders4P() {
        addCard(Zone.BATTLEFIELD, playerA, "Grizzly Bears");
        addCard(Zone.BATTLEFIELD, playerA, "Runeclaw Bear");

        attack(1, playerA, "Grizzly Bears", playerB);
        attack(1, playerA, "Runeclaw Bear", playerC);

        setStopAt(1, PhaseStep.POSTCOMBAT_MAIN);
        execute();

        assertLife(playerA, 20);
        assertLife(playerB, 18);
        assertLife(playerC, 18);
        assertLife(playerD, 20);
    }

    @Test
    public void commanderTax4P() {
        addCard(Zone.COMMAND, playerA, "Rograkh, Son of Rohgahh");
        addCard(Zone.BATTLEFIELD, playerA, "Mountain", 2);
        addCard(Zone.HAND, playerB, "Murder");
        addCard(Zone.BATTLEFIELD, playerB, "Swamp", 3);

        castSpell(1, PhaseStep.PRECOMBAT_MAIN, playerA, "Rograkh, Son of Rohgahh", true);
        castSpell(1, PhaseStep.PRECOMBAT_MAIN, playerB, "Murder", "Rograkh, Son of Rohgahh", true);
        setChoice(playerA, true);
        castSpell(1, PhaseStep.PRECOMBAT_MAIN, playerA, "Rograkh, Son of Rohgahh", true);

        setStopAt(1, PhaseStep.BEGIN_COMBAT);
        execute();

        assertPermanentCount(playerA, "Rograkh, Son of Rohgahh", 1);
        assertCommandZoneCount(playerA, "Rograkh, Son of Rohgahh", 0);
        assertTappedCount("Mountain", true, 2);
    }

    @Test
    public void actualRograkhCommanderCast() {
        addCard(Zone.COMMAND, playerA, "Rograkh, Son of Rohgahh");

        castSpell(1, PhaseStep.PRECOMBAT_MAIN, playerA, "Rograkh, Son of Rohgahh", true);

        setStopAt(1, PhaseStep.BEGIN_COMBAT);
        execute();

        assertPermanentCount(playerA, "Rograkh, Son of Rohgahh", 1);
        assertPowerToughness(playerA, "Rograkh, Son of Rohgahh", 0, 1);
    }

    @Test
    public void actualSyphonMindFourPlayers() {
        removeAllCardsFromLibrary(playerA);
        addCard(Zone.LIBRARY, playerA, "Island", 3);
        addCard(Zone.HAND, playerA, "Syphon Mind");
        addCard(Zone.BATTLEFIELD, playerA, "Swamp", 4);
        addCard(Zone.HAND, playerB, "Plains");
        addCard(Zone.HAND, playerC, "Plains");
        addCard(Zone.HAND, playerD, "Plains");

        castSpell(1, PhaseStep.PRECOMBAT_MAIN, playerA, "Syphon Mind", true);

        setStopAt(1, PhaseStep.BEGIN_COMBAT);
        execute();

        assertGraveyardCount(playerB, "Plains", 1);
        assertGraveyardCount(playerC, "Plains", 1);
        assertGraveyardCount(playerD, "Plains", 1);
        assertHandCount(playerA, 3);
    }

    @Test
    public void actualKedissCommanderDamageFanout() {
        addCard(Zone.COMMAND, playerA, "Rograkh, Son of Rohgahh");
        addCard(Zone.BATTLEFIELD, playerA, "Kediss, Emberclaw Familiar");
        addCard(Zone.HAND, playerA, "Giant Growth");
        addCard(Zone.BATTLEFIELD, playerA, "Forest");

        castSpell(1, PhaseStep.PRECOMBAT_MAIN, playerA, "Rograkh, Son of Rohgahh", true);
        castSpell(1, PhaseStep.PRECOMBAT_MAIN, playerA, "Giant Growth", "Rograkh, Son of Rohgahh", true);
        attack(1, playerA, "Rograkh, Son of Rohgahh", playerB);

        setStopAt(1, PhaseStep.POSTCOMBAT_MAIN);
        execute();

        assertLife(playerA, 20);
        assertLife(playerB, 17);
        assertLife(playerC, 17);
        assertLife(playerD, 17);
    }
}
