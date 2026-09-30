package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.game.Game;
import mage.game.permanent.Permanent;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * F-30 in the generic Protocol-2 lane: its priority enumeration offers the activated
 * ability of every permanent separately. With Prodigal Pyromancer and Prodigal Sorcerer
 * (both "{T}: deal 1 damage to any target"), the lane used XMage's AI getPlayable variant
 * and offered only one of them (equal rule text, deduplicated in a hash map). It also
 * ordered options by random ids (F-36); these two objects are distinguishable by content,
 * so their order must be the same in every game.
 */
class ExternalDecisionControllerCompletenessTest {

    @Test
    void everyPermanentsAbilityIsOfferedAndTheOrderIsStable() {
        List<String> first = pingerSources("generic-complete-a");
        List<String> second = pingerSources("generic-complete-b");
        assertEquals(2, first.size(), "each permanent's ability is its own legal activation: " + first);
        assertEquals(first, second, "the offered order does not depend on random ids");
    }

    /** Pinger options in offered order, identified by restored semantic object. */
    private static List<String> pingerSources(String tag) {
        List<XmageNativeStateRestoration.RequestedObject> objects = List.of(
                new XmageNativeStateRestoration.RequestedObject("obj:bf-P1-0-Pyromancer", "Prodigal Pyromancer",
                        "P1", "P1", mage.constants.Zone.BATTLEFIELD, false),
                new XmageNativeStateRestoration.RequestedObject("obj:bf-P1-1-Sorcerer", "Prodigal Sorcerer",
                        "P1", "P1", mage.constants.Zone.BATTLEFIELD, false));
        XmageActualCardCorpusTest.Started started = XmageActualCardCorpusTest.start(tag, 2, new ArrayList<>(objects));
        Game game = started.session().restorationGame();
        ExternalDecisionController.Decision decision =
                new ExternalDecisionController().capturePriority(started.seats().get("P1"), game);
        List<String> semantic = new ArrayList<>();
        Set<String> seen = new TreeSet<>();
        for (JsonObject action : decision.actions()) {
            if (action.get("source_object_id").isJsonNull()) {
                continue;
            }
            String sourceId = action.get("source_object_id").getAsString();
            Permanent permanent = game.getPermanent(UUID.fromString(sourceId));
            if (permanent == null || !permanent.getName().startsWith("Prodigal ") || !seen.add(sourceId)) {
                continue;
            }
            for (XmageNativeStateRestoration.RequestedObject object : objects) {
                if (started.restoration().injectedObjectId(object.semanticId()).toString().equals(sourceId)) {
                    semantic.add(object.semanticId());
                }
            }
        }
        return semantic;
    }
}
