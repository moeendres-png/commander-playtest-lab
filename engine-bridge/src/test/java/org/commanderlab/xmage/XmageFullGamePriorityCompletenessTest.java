package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * Priority offers every activatable ability of every permanent (CR 117.1b,
 * 602.2), on the full-game lane at 2–4 players.
 *
 * <p>P1 controls two Prodigal Pyromancers ("{T}: Prodigal Pyromancer deals 1
 * damage to any target"), an Island and a Prairie Stream ("{T}: Add {W} or
 * {U}"). Each Pyromancer's ability must be offered separately. The Island's
 * {U} ability and Prairie Stream's {U} ability must both be offered, although
 * their rule text is identical.</p>
 *
 * <p>F-30: the lane used XMage's AI variant of {@code getPlayable}, which
 * deduplicates activated abilities of different permanents by rule text in a
 * hash map. So one Pyromancer and one of the two {U} sources were never
 * offered, and which one depended on hash order. The legal option set was
 * incomplete and differed between otherwise identical games.</p>
 */
class XmageFullGamePriorityCompletenessTest {

    private static final String PYROMANCER = "Prodigal Pyromancer";

    @ParameterizedTest(name = "{0} players")
    @ValueSource(ints = {2, 3, 4})
    void everyPermanentsAbilityIsOfferedSeparately(int playerCount) {
        String tag = "priority-complete-" + playerCount + "p";
        List<XmageNativeStateRestoration.RequestedObject> objects = new ArrayList<>();
        objects.add(obj("P1", PYROMANCER, 0));
        objects.add(obj("P1", PYROMANCER, 1));
        objects.add(obj("P1", "Island", 0));
        objects.add(obj("P1", "Prairie Stream", 0));
        XmageActualCardCorpusTest.Started started =
                XmageActualCardCorpusTest.start(tag, playerCount, objects);
        assertEquals("priority", XmageActualCardCorpusTest.decisionClass(started));

        Set<String> pyromancerSources = new TreeSet<>();
        List<String> blueSources = new ArrayList<>();
        for (JsonElement element : started.session().legalActionsPayload().getAsJsonArray("actions")) {
            JsonObject meta = element.getAsJsonObject().getAsJsonObject("metadata");
            String label = meta.get("label").getAsString();
            JsonObject engine = meta.getAsJsonObject("xmage_option_metadata");
            if (label.startsWith(PYROMANCER + " — {T}")) {
                pyromancerSources.add(engine.get("source_object_id").getAsString());
            }
            if (label.endsWith("{T}: Add {U}.")) {
                blueSources.add(label.substring(0, label.indexOf(" — ")));
            }
        }
        assertEquals(2, pyromancerSources.size(), "each Pyromancer's ability is its own legal activation");
        blueSources.sort(String::compareTo);
        assertEquals(List.of("Island", "Prairie Stream"), blueSources,
                "equal rule text on different permanents is still two different abilities");
    }

    private static XmageNativeStateRestoration.RequestedObject obj(String pid, String name, int index) {
        return new XmageNativeStateRestoration.RequestedObject(
                "obj:bf-" + pid + "-" + index + "-" + name.replaceAll("[^A-Za-z]", ""),
                name, pid, pid, mage.constants.Zone.BATTLEFIELD, false);
    }
}
