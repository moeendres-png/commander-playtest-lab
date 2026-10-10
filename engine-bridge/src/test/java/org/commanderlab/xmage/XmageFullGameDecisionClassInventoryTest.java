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

    /**
     * #690: the engine callers of {@code chooseLandOrSpellAbility} at the pinned
     * commit, and what this lane does with each one.
     *
     * <p>The key is the engine caller's own class#method, the value names the
     * support this lane declares for it and the evidence that proves it. A
     * caller with no declared legality carries a coded fail-closed reason
     * instead of a matrix row; it is still named here, and its reason is proven
     * on the real engine.</p>
     */
    record LandOrSpellCaller(String engineCaller, String card, String support, String reason, String proof) {
    }

    static final Map<String, LandOrSpellCaller> LAND_OR_SPELL_CALLERS = landOrSpellCallers();

    private static Map<String, LandOrSpellCaller> landOrSpellCallers() {
        Map<String, LandOrSpellCaller> callers = new LinkedHashMap<>();
        callers.put(XmageFullGamePlayer.LAND_OR_SPELL_CALLER, new LandOrSpellCaller(
                XmageFullGamePlayer.LAND_OR_SPELL_CALLER, "(engine effect, not one card)", "supported",
                "the land components follow this caller's own component enumeration",
                "matrix row land_or_spell"));
        callers.put(VAULT_112_CALLER, new LandOrSpellCaller(
                VAULT_112_CALLER, "Vault 112: Sadistic Simulation, chapter III", "fail_closed",
                UNSUPPORTED_DECISION_CLASS + ": land-or-spell choice from an undeclared engine caller",
                "XmageLandOrSpellCallerTest.vault112ChapterThreeFailsClosedOnTheRealEngine"));
        return callers;
    }

    /** Vault 112's chapter III effect, the only other caller at the pin. */
    static final String VAULT_112_CALLER =
            "mage.cards.v.Vault112SadisticSimulationChapterEffect#apply";

    static final String UNSUPPORTED_DECISION_CLASS = "UNSUPPORTED_DECISION_CLASS";

    /**
     * Both callers are named, the supported one is the matrix row's own caller,
     * and the other carries the coded reason the real-engine test observes.
     */
    @Test
    void landOrSpellCallersAreInventoried() {
        assertEquals(2, LAND_OR_SPELL_CALLERS.size(), "the pin has exactly two callers");
        assertEquals("mage.util.CardUtil#castSpellWithAttributesForFree",
                XmageFullGamePlayer.LAND_OR_SPELL_CALLER,
                "the supported caller is the declared engine caller");
        LandOrSpellCaller supported = LAND_OR_SPELL_CALLERS.get(XmageFullGamePlayer.LAND_OR_SPELL_CALLER);
        assertEquals("supported", supported.support(), "the declared caller is supported");
        assertEquals("matrix row land_or_spell", supported.proof(), "its matrix row proves it");
        assertTrue(CALLBACK_ROWS.get("chooseLandOrSpellAbility").contains("land_or_spell"));

        LandOrSpellCaller vault = LAND_OR_SPELL_CALLERS.get(VAULT_112_CALLER);
        assertEquals("fail_closed", vault.support(), "Vault 112 has no declared legality here");
        assertEquals(UNSUPPORTED_DECISION_CLASS
                + ": land-or-spell choice from an undeclared engine caller", vault.reason(),
                "its coded fail-closed reason");
        assertEquals("XmageLandOrSpellCallerTest.vault112ChapterThreeFailsClosedOnTheRealEngine",
                vault.proof(), "the reason is proven on the real engine, not only in a comment");
    }

    /**
     * The guard accepts exactly one caller: the declared constant and nothing
     * else. Adding a second accepted caller changes this method and fails here.
     */
    @Test
    void theAcceptedLandOrSpellCallerIsExactlyTheDeclaredOne() throws Exception {
        String source = Files.readString(repoRoot().resolve(
                "engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGamePlayer.java"));
        int guard = source.indexOf("calledFromCastWithAttributesForFree() {");
        assertTrue(guard > 0, "the land-or-spell caller guard is present");
        String body = source.substring(guard, source.indexOf("public ActivatedAbility chooseLandOrSpellAbility",
                guard));
        assertEquals(1, count(body, XmageFullGamePlayer.LAND_OR_SPELL_CALLER),
                "exactly one accepted caller is named: " + body);
        assertEquals(0, count(body, VAULT_112_CALLER),
                "no second caller is accepted by the guard: " + body);
    }

    private static int count(String haystack, String needle) {
        int found = 0;
        for (int at = haystack.indexOf(needle); at >= 0; at = haystack.indexOf(needle, at + needle.length())) {
            found++;
        }
        return found;
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
