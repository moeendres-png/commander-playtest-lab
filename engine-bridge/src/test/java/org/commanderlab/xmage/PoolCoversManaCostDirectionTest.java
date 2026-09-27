package org.commanderlab.xmage;

import mage.Mana;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Guards the direction of the engine-native payability fact projected as
 * {@code pool_covers_mana_cost}: {@code cost.enough(pool)} answers whether
 * the pool can pay the cost. The inverted call ({@code pool.enough(cost)})
 * reports coverage for an empty pool against a generic cost and re-opens
 * the shared-resource activation failure.
 */
final class PoolCoversManaCostDirectionTest {

    private static Mana cost(int generic) {
        return new Mana(0, 0, 0, 0, 0, generic, 0, 0);
    }

    private static Mana pool(int colorless) {
        Mana mana = new Mana();
        mana.setColorless(colorless);
        return mana;
    }

    @Test
    void emptyPoolDoesNotCoverGenericCost() {
        assertFalse(cost(1).enough(pool(0)));
    }

    @Test
    void colorlessPoolCoversGenericCost() {
        assertTrue(cost(1).enough(pool(1)));
    }

    @Test
    void invertedCallWouldLie() {
        // Documents why the projection must call cost.enough(pool):
        // the inverted direction claims coverage here.
        assertTrue(pool(0).enough(cost(1)));
    }
}
