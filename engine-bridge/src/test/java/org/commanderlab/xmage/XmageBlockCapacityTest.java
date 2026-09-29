package org.commanderlab.xmage;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * CR 509.1a block capacity as XMage encodes it. CanBlockAdditionalCreatureEffect
 * sets maxBlocks = 0 for "can block any number of creatures" (Palace Guard,
 * Guardian of the Gateless). Treating zero as "cannot block" silently skipped
 * those blockers' block decision entirely.
 */
class XmageBlockCapacityTest {

    @Test
    void zeroMeansAnyNumberOfOfferedAttackers() {
        assertEquals(3, XmageFullGamePlayer.blockCapacity(0, 3));
        assertEquals(1, XmageFullGamePlayer.blockCapacity(0, 1));
    }

    @Test
    void positiveCapacityCapsTheSelection() {
        assertEquals(1, XmageFullGamePlayer.blockCapacity(1, 3));
        assertEquals(2, XmageFullGamePlayer.blockCapacity(2, 3));
        assertEquals(2, XmageFullGamePlayer.blockCapacity(5, 2));
    }

    @Test
    void noOfferedAttackerMeansNoBlockDecision() {
        assertEquals(0, XmageFullGamePlayer.blockCapacity(0, 0));
        assertEquals(0, XmageFullGamePlayer.blockCapacity(1, 0));
    }
}
