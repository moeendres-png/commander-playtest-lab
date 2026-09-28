package org.commanderlab.xmage;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * The capability payload must describe the external decision surface truthfully,
 * and the two must not be able to drift apart.
 *
 * <p>Two properties are enforced here.
 *
 * <p>First, precision: the lane publishes both what it does support (legal options
 * for the decision it is currently asking about) and what it does not (a
 * free-standing legal-action API queryable at any time). The global flags stay
 * false because the scoped claim is not the global claim, and a reader that
 * consumed only the global flags would otherwise under-report a real capability.
 *
 * <p>Second, non-drift: {@code LEGAL_ACTION_DECISION_CLASSES} is declared beside
 * the payload, and this test re-derives the classes the player can actually
 * request straight from its source. A new decision class added to the player
 * without being declared in the capability set fails here, instead of the
 * capability payload quietly under-reporting the surface.
 */
class XmageFullGameDecisionSurfaceTest {

    /** decision_class literals as they appear in the player's request calls. */
    private static final Pattern DECISION_CLASS_LITERAL = Pattern.compile(
            "request\\(game,\\s*\"([a-z_]+)\"");

    private static Set<String> playerRequestableClasses() throws IOException {
        // Surefire runs with workingDirectory=target, so the module source tree is
        // resolved from the repoRoot property the pom injects, not from the CWD.
        Path module = Path.of(System.getProperty("commanderlab.repoRoot", ".."),
                "engine-bridge");
        Path source = module.resolve("src/main/java/org/commanderlab/xmage/XmageFullGamePlayer.java");
        String text = Files.readString(source, StandardCharsets.UTF_8);
        Set<String> classes = new LinkedHashSet<>();
        Matcher matcher = DECISION_CLASS_LITERAL.matcher(text);
        while (matcher.find()) {
            classes.add(matcher.group(1));
        }
        // Some call sites pass the class through a local variable; capture the
        // remaining string literals that are decision-class arguments too, so a
        // reformatted call site cannot slip past the guard.
        Matcher literal = Pattern.compile(
                "^\\s*String decisionClass = \"([a-z_]+)\";", Pattern.MULTILINE).matcher(text);
        while (literal.find()) {
            classes.add(literal.group(1));
        }
        return classes;
    }

    @Test
    void publishedDecisionClassesCoverEveryClassThePlayerCanRequest() throws IOException {
        Set<String> requested = playerRequestableClasses();
        assertFalse(requested.isEmpty(), "no decision classes were derived from the player source");
        Set<String> published = XmageFullGameJsonlBridge.LEGAL_ACTION_DECISION_CLASSES;
        List<String> undeclared = new ArrayList<>();
        for (String decisionClass : requested) {
            if (!published.contains(decisionClass)) {
                undeclared.add(decisionClass);
            }
        }
        assertTrue(undeclared.isEmpty(),
                () -> "the player can request decision classes the capability payload does not "
                        + "declare: " + undeclared + "; declared=" + published);
        assertEquals(17, published.size(),
                "the enumerated external decision surface changed; update this test and the "
                        + "readiness packet together rather than letting the number drift");
    }

    @Test
    void globalFreeStandingLegalActionFlagsRemainFalse() {
        JsonObject capabilities = XmageFullGameJsonlBridge.capabilitiesPayload()
                .getAsJsonObject("capabilities");
        // The global claim is about a free-standing API queryable at any time,
        // which this lane does not offer.
        assertFalse(capabilities.get("legal_actions_supported").getAsBoolean());
        assertFalse(capabilities.get("action_submission_supported").getAsBoolean());
        assertFalse(capabilities.get("legal_action_global_enumeration_supported").getAsBoolean());
    }

    @Test
    void decisionScopedCapabilitiesArePublishedAlongsideTheGlobalRefusals() {
        JsonObject capabilities = XmageFullGameJsonlBridge.capabilitiesPayload()
                .getAsJsonObject("capabilities");
        assertTrue(capabilities.get("decision_scoped_legal_actions_supported").getAsBoolean());
        assertTrue(capabilities.get("decision_scoped_action_submission_supported").getAsBoolean());

        JsonArray classes = capabilities.getAsJsonArray("legal_action_decision_classes");
        assertEquals(XmageFullGameJsonlBridge.LEGAL_ACTION_DECISION_CLASSES.size(), classes.size());
        assertEquals(classes.size(),
                capabilities.get("legal_action_decision_class_count").getAsInt());
        for (String decisionClass : XmageFullGameJsonlBridge.LEGAL_ACTION_DECISION_CLASSES) {
            assertTrue(classes.toString().contains(decisionClass),
                    () -> "published decision class list is missing " + decisionClass);
        }
    }

    @Test
    void scopedAndGlobalFlagsNeverContradictEachOther() {
        JsonObject capabilities = XmageFullGameJsonlBridge.capabilitiesPayload()
                .getAsJsonObject("capabilities");
        boolean globalLegal = capabilities.get("legal_actions_supported").getAsBoolean();
        boolean scopedLegal = capabilities.get("decision_scoped_legal_actions_supported").getAsBoolean();
        boolean globalSubmission = capabilities.get("action_submission_supported").getAsBoolean();
        boolean scopedSubmission =
                capabilities.get("decision_scoped_action_submission_supported").getAsBoolean();
        // A global claim of support would require the scoped claim too; the
        // converse is legitimate and is the current state.
        assertTrue(!globalLegal || scopedLegal,
                "a global legal-action claim requires the scoped claim it depends on");
        assertTrue(!globalSubmission || scopedSubmission,
                "a global action-submission claim requires the scoped claim it depends on");
    }
}
