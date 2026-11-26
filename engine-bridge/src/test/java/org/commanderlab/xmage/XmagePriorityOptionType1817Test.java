package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.abilities.Ability;
import mage.abilities.PlayLandAbility;
import mage.abilities.SpellAbility;
import mage.abilities.common.SimpleActivatedAbility;
import mage.abilities.costs.common.TapSourceCost;
import mage.abilities.effects.common.DrawCardSourceControllerEffect;
import mage.abilities.mana.GreenManaAbility;
import mage.constants.SpellAbilityType;
import mage.constants.Zone;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;

/**
 * Verifies #1817: priority options distinguish play_land, cast_spell, mana_ability,
 * and activated_ability truthfully at the bridge payload boundary.
 */
class XmagePriorityOptionType1817Test {

    private static final String ROGRAKH = "Rograkh, Son of Rohgahh";

    private static XmageNativeStateRestoration.RequestedObject obj(
            String pid, String name, int index, Zone zone) {
        String slug = name.replaceAll("[^A-Za-z0-9]+", "");
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:" + zone.name().toLowerCase() + "-" + pid + "-" + index + "-" + slug,
                name, pid, pid, zone, false);
    }

    @Test
    void priorityOptionTypeClassifiesAbilitiesTruthfully() {
        Ability playLand = new PlayLandAbility("Forest");
        Ability spell = new SpellAbility(null, "Sol Ring", Zone.HAND, SpellAbilityType.BASE);
        Ability mana = new GreenManaAbility();
        Ability activated = new SimpleActivatedAbility(
                Zone.BATTLEFIELD, new DrawCardSourceControllerEffect(1), new TapSourceCost());

        assertEquals("play_land", XmageFullGamePlayer.priorityOptionType(playLand));
        assertEquals("cast_spell", XmageFullGamePlayer.priorityOptionType(spell));
        assertEquals("mana_ability", XmageFullGamePlayer.priorityOptionType(mana));
        assertEquals("activated_ability", XmageFullGamePlayer.priorityOptionType(activated));
        assertEquals("activated_ability", XmageFullGamePlayer.priorityOptionType(null));
    }

    @Test
    void realEngineMainPhasePriorityEmitsPlayLandCastSpellManaAndActivatedTypes() {
        List<XmageNativeStateRestoration.RequestedPlayer> players = List.of(
                new XmageNativeStateRestoration.RequestedPlayer("P1", 1, 40),
                new XmageNativeStateRestoration.RequestedPlayer("P2", 2, 40)
        );
        List<XmageNativeStateRestoration.RequestedCommander> commanders = List.of(
                new XmageNativeStateRestoration.RequestedCommander("cmd:P1-A", ROGRAKH, "P1", 0),
                new XmageNativeStateRestoration.RequestedCommander("cmd:P2-A", ROGRAKH, "P2", 0)
        );
        List<XmageNativeStateRestoration.RequestedObject> objects = List.of(
                obj("P1", "Mountain", 1, Zone.HAND),
                obj("P1", "Sol Ring", 2, Zone.HAND),
                obj("P1", "Mountain", 3, Zone.BATTLEFIELD),
                obj("P1", "Evolving Wilds", 4, Zone.BATTLEFIELD)
        );
        XmageNativeStateRestoration.Plan plan = new XmageNativeStateRestoration.Plan(
                "priority-types-1817", 2, 1817L, players, commanders, objects,
                1, mage.constants.TurnPhase.PRECOMBAT_MAIN,
                mage.constants.PhaseStep.PRECOMBAT_MAIN, "P1", "P1");
        XmageDeckImporter importer = new XmageDeckImporter();
        XmageNativeStateRestoration restoration =
                XmageNativeStateRestorationTest.restorationFor(plan);
        List<String> handles = new ArrayList<>();
        for (XmageNativeStateRestoration.RequestedPlayer player : players) {
            List<String> mainboard = new ArrayList<>();
            for (int i = 0; i < 99; i++) {
                mainboard.add("Mountain");
            }
            handles.add(importer.importCommanderDeck("p1817-" + player.playerId(),
                    "p1817-hash", mainboard, List.of(ROGRAKH)).deckHandle());
        }
        XmageFullGameSession session = new XmageFullGameSession(
                "priority-types-1817", handles, 0, 40, plan.seed(), importer, restoration);
        session.start();
        try {
            var seats = session.restorationSeats();
            XmageNativeStateRestorationTest.completeArrival(session, restoration, seats);

            JsonObject payload = session.pendingDecisionPayload().getAsJsonObject("decision");
            assertEquals("priority", payload.get("decision_class").getAsString());
            JsonArray options = payload.getAsJsonArray("legal_options");
            Map<String, String> typeBySourceAndAbility = new LinkedHashMap<>();
            for (JsonElement element : options) {
                JsonObject opt = element.getAsJsonObject();
                String ot = opt.get("option_type").getAsString();
                JsonObject meta = opt.has("metadata") && opt.get("metadata").isJsonObject()
                        ? opt.get("metadata").getAsJsonObject() : new JsonObject();
                String sourceName = meta.has("source_name")
                        ? meta.get("source_name").getAsString() : "";
                String abilityType = meta.has("ability_type")
                        ? meta.get("ability_type").getAsString() : "";
                if (!sourceName.isEmpty() && !abilityType.isEmpty()) {
                    typeBySourceAndAbility.put(sourceName + ":" + abilityType, ot);
                }
            }

            assertEquals("play_land", typeBySourceAndAbility.get("Mountain:play_land"),
                    "Playing Mountain must emit option_type=play_land, saw: " + options);
            assertEquals("cast_spell", typeBySourceAndAbility.get("Sol Ring:spell"),
                    "Casting Sol Ring must emit option_type=cast_spell, saw: " + options);
            assertEquals("mana_ability", typeBySourceAndAbility.get("Mountain:activated_mana"),
                    "Tapping Mountain for mana must emit option_type=mana_ability, saw: " + options);
            assertEquals("activated_ability", typeBySourceAndAbility.get("Evolving Wilds:activated_nonmana"),
                    "Activating Evolving Wilds must keep option_type=activated_ability, saw: " + options);

            for (JsonElement element : options) {
                JsonObject opt = element.getAsJsonObject();
                JsonObject meta = opt.has("metadata") && opt.get("metadata").isJsonObject()
                        ? opt.get("metadata").getAsJsonObject() : new JsonObject();
                String abilityType = meta.has("ability_type")
                        ? meta.get("ability_type").getAsString() : "";
                if ("play_land".equals(abilityType) || "spell".equals(abilityType)) {
                    assertFalse("activated_ability".equals(opt.get("option_type").getAsString()),
                            "Land/spell action must never fall back to activated_ability: " + opt);
                }
            }
            assertNotNull(typeBySourceAndAbility.get("Mountain:play_land"));
        } finally {
            session.shutdownGame();
        }
    }
}
