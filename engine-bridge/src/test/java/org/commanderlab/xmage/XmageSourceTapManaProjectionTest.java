package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.abilities.keyword.HasteAbility;
import mage.constants.Zone;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.game.permanent.PermanentImpl;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Field;
import java.util.List;

import static org.commanderlab.xmage.XmageFullGameUnchoosableCostTest.onBattlefield;
import static org.junit.jupiter.api.Assertions.*;

class XmageSourceTapManaProjectionTest {
    private static final String FIELD = "source_tap_mana_abilities_blocked";

    @Test
    void nativeTapGateAndViewerScope() throws Exception {
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("source-tap-projection", 2, "P1", List.of(
                XmageMultiplayerScenario.obj("P1", "Elvish Mystic", 0, Zone.BATTLEFIELD),
                XmageMultiplayerScenario.obj("P1", "Llanowar Elves", 1, Zone.BATTLEFIELD),
                XmageMultiplayerScenario.obj("P1", "Skycloud Expanse", 2, Zone.BATTLEFIELD),
                XmageMultiplayerScenario.obj("P2", "Forest", 0, Zone.BATTLEFIELD)));
        Game game = s.session.restorationGame();
        Permanent sick = onBattlefield(game, "Elvish Mystic");
        Permanent ready = onBattlefield(game, "Llanowar Elves");
        // Restoration advances the fixture to a main phase; set the native
        // control-duration state to that of a permanent just entering.
        Field controlled = PermanentImpl.class.getDeclaredField("controlledFromStartOfControllerTurn");
        controlled.setAccessible(true);
        controlled.setBoolean(sick, false);
        assertTrue(sick.hasSummoningSickness());
        ((PermanentImpl) ready).removeSummoningSickness();
        assertEquals(0, s.seats.get("P1").getManaPool().getMana().count());

        JsonObject own = XmageFullGameStateRedactor.actorView(game, s.seats.get("P1"));
        assertTrue(permanent(own, "Elvish Mystic").get(FIELD).getAsBoolean());
        assertFalse(permanent(own, "Llanowar Elves").get(FIELD).getAsBoolean());
        assertFalse(permanent(own, "Skycloud Expanse").get(FIELD).getAsBoolean());
        assertFalse(permanent(own, "Forest").has(FIELD));
        assertFalse(permanent(XmageFullGameStateRedactor.actorView(game, s.seats.get("P2")),
                "Elvish Mystic").has(FIELD));
        assertFalse(permanent(XmageFullGameStateRedactor.publicView(game), "Elvish Mystic").has(FIELD));

        sick.addAbility(HasteAbility.getInstance(), sick.getId(), game);
        assertFalse(permanent(XmageFullGameStateRedactor.actorView(game, s.seats.get("P1")),
                "Elvish Mystic").get(FIELD).getAsBoolean());
        ((PermanentImpl) sick).setFaceDown(true, game);
        assertFalse(permanent(XmageFullGameStateRedactor.actorView(game, s.seats.get("P1")),
                "Elvish Mystic").has(FIELD));
    }

    @Test
    void asThoughEffectAllowsTapWithoutGrantingHaste() throws Exception {
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("source-tap-as-though", 2, "P1", List.of(
                XmageMultiplayerScenario.obj("P1", "Elvish Mystic", 0, Zone.BATTLEFIELD),
                XmageMultiplayerScenario.obj("P1", "Thousand-Year Elixir", 1, Zone.BATTLEFIELD)));
        Game game = s.session.restorationGame();
        Permanent creature = onBattlefield(game, "Elvish Mystic");
        Field controlled = PermanentImpl.class.getDeclaredField("controlledFromStartOfControllerTurn");
        controlled.setAccessible(true);
        controlled.setBoolean(creature, false);
        assertTrue(creature.hasSummoningSickness());
        assertFalse(permanent(XmageFullGameStateRedactor.actorView(game, s.seats.get("P1")),
                "Elvish Mystic").get(FIELD).getAsBoolean());
    }

    private static JsonObject permanent(JsonObject view, String name) {
        for (JsonElement player : view.getAsJsonArray("players")) {
            for (JsonElement item : player.getAsJsonObject().getAsJsonArray("battlefield")) {
                JsonObject object = item.getAsJsonObject();
                if (name.equals(object.get("name").getAsString())) {
                    return object;
                }
            }
        }
        throw new AssertionError("permanent not found: " + name);
    }
}
