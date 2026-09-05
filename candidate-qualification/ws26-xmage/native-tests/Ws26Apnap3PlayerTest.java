package org.mage.test.ws26;

import mage.constants.PhaseStep;
import mage.constants.Zone;
import org.junit.Assert;
import org.junit.Test;
import org.mage.test.serverside.base.CardTestCommander3PlayersFFA;

/** Exact 3-player APNAP discriminator for WS05-MP-TRIG-3. */
public class Ws26Apnap3PlayerTest extends CardTestCommander3PlayersFFA {

    @Test
    public void apnapSimultaneousTriggers3P() {
        // A is active. Memnite entering under A simultaneously triggers A's
        // Soul Warden and nonactive B's Suture Priest. APNAP puts A's trigger
        // on the stack first and B's trigger on top. With A at one life, B's
        // loss-of-life trigger must resolve first and eliminate A before the
        // Soul Warden trigger can save A.
        setLife(playerA, 1);
        addCard(Zone.BATTLEFIELD, playerA, "Soul Warden");
        addCard(Zone.BATTLEFIELD, playerB, "Suture Priest");
        addCard(Zone.HAND, playerA, "Memnite");

        castSpell(1, PhaseStep.PRECOMBAT_MAIN, playerA, "Memnite", true);
        setChoice(playerB, true);

        setStopAt(1, PhaseStep.POSTCOMBAT_MAIN);
        execute();

        // The stopped Mage.Tests harness reports an unfinished match as DRAW,
        // so assert the engine's player-loss state directly. Runtime logs also
        // preserve the trigger push/resolve order for evidence materialization.
        Assert.assertTrue("APNAP top trigger must eliminate active player first", playerA.hasLost());
    }
}
