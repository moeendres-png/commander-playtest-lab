package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.abilities.Ability;
import mage.abilities.mana.AnyColorPermanentTypesManaAbility;
import mage.abilities.mana.ConditionalAnyColorManaAbility;
import mage.constants.Zone;
import mage.constants.TargetController;
import mage.filter.FilterPermanent;
import mage.game.Game;
import mage.game.permanent.Permanent;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class XmageManaProductionObservationTest {
    private static XmageMultiplayerScenario scenario(String tag, String... legends) {
        var objects = new java.util.ArrayList<XmageNativeStateRestoration.RequestedObject>();
        objects.add(XmageMultiplayerScenario.obj("P1", "Plaza of Heroes", 0, Zone.BATTLEFIELD));
        for (int i = 0; i < legends.length; i++) {
            objects.add(XmageMultiplayerScenario.obj("P1", legends[i], i + 1, Zone.BATTLEFIELD));
        }
        return XmageMultiplayerScenario.start(tag, 2, "P1", objects);
    }

    private static Ability ability(XmageMultiplayerScenario s, Class<?> type) {
        Permanent plaza = s.session.restorationGame().getBattlefield().getAllActivePermanents().stream()
                .filter(p -> p.getName().equals("Plaza of Heroes")).findFirst().orElseThrow();
        return plaza.getAbilities().stream().filter(a -> a.getClass() == type).findFirst().orElseThrow();
    }

    private static JsonObject metadata(XmageMultiplayerScenario s, Ability ability, Game game) throws Exception {
        Method method = XmageFullGamePlayer.class.getDeclaredMethod("abilityMetadata", Ability.class, Game.class);
        method.setAccessible(true);
        return (JsonObject) method.invoke(s.seats.get("P1"), ability, game);
    }

    @Test
    void nativeBoardPaletteIsObservedWithoutConfusingRestrictedMana() throws Exception {
        XmageMultiplayerScenario s = scenario("mana-hint-red", "Rograkh, Son of Rohgahh");
        Game game = s.session.restorationGame();
        Ability board = ability(s, AnyColorPermanentTypesManaAbility.class);
        String before = board.getRule();
        JsonObject production = metadata(s, board, game).getAsJsonObject("mana_production");
        assertNotNull(production);
        assertEquals("unrestricted_board_colors", production.get("scope").getAsString());
        assertEquals(1, production.get("amount").getAsInt());
        assertEquals(List.of("R"), production.getAsJsonArray("colors").asList().stream()
                .map(e -> e.getAsString()).toList());
        assertEquals(before, board.getRule());
        assertFalse(metadata(s, ability(s, ConditionalAnyColorManaAbility.class), game).has("mana_production"));
        Ability mixed = board.copy();
        mixed.addEffect(ability(s, ConditionalAnyColorManaAbility.class).getEffects().get(0).copy());
        assertFalse(metadata(s, mixed, game).has("mana_production"));
        assertFalse(metadata(s, new DerivedAbility(), game).has("mana_production"));
        assertFalse(metadata(s, board, override(game, "getPhase", null)).has("mana_production"));
        assertFalse(metadata(s, board, override(game, "inCheckPlayableState", true)).has("mana_production"));
    }

    private static Game override(Game game, String methodName, Object value) {
        return (Game) Proxy.newProxyInstance(Game.class.getClassLoader(), new Class<?>[]{Game.class},
                (proxy, method, args) -> method.getName().equals(methodName)
                        ? value : method.invoke(game, args));
    }

    private static final class DerivedAbility extends AnyColorPermanentTypesManaAbility {
        DerivedAbility() { super(TargetController.YOU, new FilterPermanent()); }
    }

    @Test
    void emptyPaletteHasNoHintAndMulticolorUsesCanonicalOrder() throws Exception {
        XmageMultiplayerScenario empty = scenario("mana-hint-empty");
        assertFalse(metadata(empty, ability(empty, AnyColorPermanentTypesManaAbility.class),
                empty.session.restorationGame()).has("mana_production"));
        XmageMultiplayerScenario colored = scenario("mana-hint-wu", "Raff Capashen, Ship's Mage");
        JsonObject production = metadata(colored, ability(colored, AnyColorPermanentTypesManaAbility.class),
                colored.session.restorationGame()).getAsJsonObject("mana_production");
        assertNotNull(production);
        assertEquals(List.of("W", "U"), production.getAsJsonArray("colors").asList().stream()
                .map(e -> e.getAsString()).toList());
    }
}
