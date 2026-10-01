package org.commanderlab.xmage;

import mage.constants.MultiAmountType;
import mage.game.combat.CombatGroup;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * F-43: the bridge retires a departed player's {@code multi_amount} frame only
 * for CombatGroup combat damage assignment, and only because the pinned engine
 * re-resolves the damage source after that callback. These checks bind both
 * facts to the engine on the classpath, so a repin to an engine without the
 * F-43 revalidation, or one that renames the dialogues, fails here instead of
 * silently widening or narrowing the unwind.
 */
class XmageCombatDamageLeaverUnwindQualificationTest {

    @Test
    void theQualifiedDialoguesAreExactlyCombatGroupsCombatDamageTitles() throws IOException {
        assertEquals(3, XmageFullGamePlayer.COMBAT_DAMAGE_DIALOGUES.size());
        String constantPool = combatGroupBytes();
        for (String title : XmageFullGamePlayer.COMBAT_DAMAGE_DIALOGUES) {
            assertTrue(constantPool.contains(title), "CombatGroup at the pin uses dialogue title " + title);
        }
    }

    @Test
    void noGenericMultiAmountDialogueIsQualified() {
        for (MultiAmountType generic : List.of(
                MultiAmountType.MANA,
                MultiAmountType.DAMAGE,
                MultiAmountType.P1P1,
                MultiAmountType.COUNTERS,
                MultiAmountType.REMOVE_COUNTERS,
                MultiAmountType.CHEAT_LANDS)) {
            assertFalse(XmageFullGamePlayer.COMBAT_DAMAGE_DIALOGUES.contains(generic.getTitle()),
                    "non-combat multi_amount stays fail-closed for a departed player: " + generic.getTitle());
        }
    }

    @Test
    void thePinnedCombatGroupRevalidatesTheDamageSourceAfterTheCallback() {
        Method revalidate = Arrays.stream(CombatGroup.class.getDeclaredMethods())
                .filter(m -> m.getName().equals("revalidateCombatDamageSource"))
                .findFirst()
                .orElse(null);
        assertNotNull(revalidate, "F-43 CombatGroup.revalidateCombatDamageSource is on the classpath");
    }

    private static String combatGroupBytes() throws IOException {
        try (InputStream in = CombatGroup.class.getResourceAsStream("CombatGroup.class")) {
            assertNotNull(in, "CombatGroup.class is readable");
            return new String(in.readAllBytes(), StandardCharsets.ISO_8859_1);
        }
    }
}
