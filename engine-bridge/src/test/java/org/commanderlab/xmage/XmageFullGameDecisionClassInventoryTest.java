package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #662 SLOT-06 L4: the decision-class inventory of the full-game production lane.
 *
 * <p>Three sources must agree, and every entry needs a matrix row in
 * {@link XmageFullGameDecisionClassMatrixTest}:</p>
 * <ul>
 *   <li>the controller's declared {@code DECISION_CLASSES} (any other class fails
 *       closed at runtime);</li>
 *   <li>the class literals the player source can publish;</li>
 *   <li>every discretionary {@link Player} callback the player overrides, plus the
 *       audited parent delegations.</li>
 * </ul>
 * <p>No class is listed as unreachable: every declared class is exercised.</p>
 */
class XmageFullGameDecisionClassInventoryTest {

    /** Callback name -> matrix scenario keys that exercise it on the real engine. */
    static final Map<String, List<String>> CALLBACK_ROWS = new LinkedHashMap<>();

    static {
        CALLBACK_ROWS.put("priority", List.of("priority"));
        CALLBACK_ROWS.put("choose", List.of("choose_object", "ring_bearer", "starting_player", "choice"));
        CALLBACK_ROWS.put("chooseTarget", List.of("target", "london_bottom", "london_bottom_two"));
        CALLBACK_ROWS.put("chooseTargetAmount", List.of("target_amount"));
        CALLBACK_ROWS.put("chooseMulligan", List.of("mulligan"));
        CALLBACK_ROWS.put("chooseUse", List.of("choose_use"));
        CALLBACK_ROWS.put("choosePile", List.of("pile"));
        CALLBACK_ROWS.put("playMana", List.of("mana_payment"));
        CALLBACK_ROWS.put("announceX", List.of("announce_x"));
        CALLBACK_ROWS.put("chooseReplacementEffect", List.of("replacement_effect"));
        CALLBACK_ROWS.put("chooseTriggeredAbility", List.of("trigger_order"));
        CALLBACK_ROWS.put("chooseMode", List.of("mode"));
        CALLBACK_ROWS.put("selectAttackers", List.of("declare_attacker"));
        CALLBACK_ROWS.put("selectBlockers", List.of("declare_blocker"));
        CALLBACK_ROWS.put("getAmount", List.of("amount"));
        CALLBACK_ROWS.put("getMultiAmountWithIndividualConstraints", List.of("multi_amount", "multi_amount_combat"));
        CALLBACK_ROWS.put("chooseAbilityForCast", List.of("cast_ability"));
        CALLBACK_ROWS.put("chooseLandOrSpellAbility", List.of("land_or_spell"));
        // Audited parent delegations: they reach the overridden callbacks above.
        CALLBACK_ROWS.put("chooseRingBearer", List.of("ring_bearer"));
        CALLBACK_ROWS.put("getMultiAmount", List.of("multi_amount"));
    }

    @Test
    void declaredClassesEqualTheMatrixRows() {
        Set<String> matrixClasses = new TreeSet<>();
        XmageFullGameDecisionClassMatrixTest.SCENARIOS.values()
                .forEach(scenario -> matrixClasses.add(scenario.targetClass()));
        assertEquals(new TreeSet<>(XmageFullGameDecisionController.DECISION_CLASSES), matrixClasses,
                "every declared decision class needs a matrix row, and every row a declared class");
    }

    @Test
    void playerSourcePublishesOnlyDeclaredClasses() throws Exception {
        String source = Files.readString(repoRoot().resolve(
                "engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGamePlayer.java"));
        Set<String> published = new TreeSet<>();
        for (Pattern pattern : List.of(
                Pattern.compile("request\\(\\s*game,\\s*(?:this,\\s*)?\"([a-z_]+)\""),
                Pattern.compile("chooseBoolean\\(\\s*[^,]+,\\s*\"([a-z_]+)\""),
                Pattern.compile("chooseNumber\\(\\s*\"([a-z_]+)\""),
                Pattern.compile("targeted \\? \"([a-z_]+)\" : \"([a-z_]+)\""))) {
            Matcher matcher = pattern.matcher(source);
            while (matcher.find()) {
                for (int group = 1; group <= matcher.groupCount(); group++) {
                    published.add(matcher.group(group));
                }
            }
        }
        assertEquals(new TreeSet<>(XmageFullGameDecisionController.DECISION_CLASSES), published,
                "the player source and the declared classes must agree");
    }

    @Test
    void everyDiscretionaryCallbackHasAMatrixRow() {
        Set<String> callbacks = new TreeSet<>();
        for (Method method : Player.class.getMethods()) {
            if (isDiscretionary(method)) {
                callbacks.add(method.getName());
            }
        }
        assertEquals(new TreeSet<>(CALLBACK_ROWS.keySet()), callbacks,
                "every discretionary callback (and nothing else) maps to matrix rows");
        Set<String> rows = XmageFullGameDecisionClassMatrixTest.SCENARIOS.keySet();
        CALLBACK_ROWS.forEach((callback, keys) -> keys.forEach(
                key -> assertTrue(rows.contains(key), callback + " -> unknown matrix row " + key)));
        Set<String> unused = new HashSet<>(rows);
        CALLBACK_ROWS.values().forEach(unused::removeAll);
        unused.remove("mana_payment");
        assertTrue(unused.isEmpty(), "matrix rows without a callback: " + unused);
    }

    @Test
    void undeclaredClassFailsClosed() {
        XmageFullGameDecisionController controller = new XmageFullGameDecisionController();
        XmageFullGameSession session = XmageFullGameCancelRewindTest.started("issue662-inventory", 6630L);
        XmageFullGameDecisionController.DecisionException failure = assertThrows(
                XmageFullGameDecisionController.DecisionException.class,
                () -> controller.request(session.restorationGame(),
                        session.restorationGame().getPlayers().values().iterator().next(),
                        "wsr22_undeclared_class", "prompt", 1, 1, new JsonArray(), new JsonObject(), null));
        assertTrue(failure.getMessage().startsWith("UNDECLARED_DECISION_CLASS"), failure.getMessage());
    }

    /** Same selection rule as XmageFullGamePlayerBoundaryTest. */
    private static boolean isDiscretionary(Method method) {
        if (Modifier.isStatic(method.getModifiers())) {
            return false;
        }
        String name = method.getName();
        return name.startsWith("choose") || Set.of("priority", "playMana", "announceX", "getAmount",
                "getMultiAmount", "getMultiAmountWithIndividualConstraints", "selectAttackers",
                "selectBlockers").contains(name);
    }

    private static Path repoRoot() {
        return XmageNativeStateRestorationTest.repoRoot();
    }
}
