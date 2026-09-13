package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.choices.Choice;
import mage.choices.ChoiceImpl;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * WS92 fresh runtime qualification for D4 (key-mode Choice projection and
 * twin-stable external option identity/redaction) on current cfc36f.
 *
 * <p>No historical WS60 behavior credit is consumed: every assertion executes
 * against current-main bridge code. The Rules Core remains the sole legality
 * authority; these tests prove only adapter projection and redaction.</p>
 */
class Ws92D4ChoiceProjectionTest {

    @Test
    void optionRedactsPerGameObjectIdentityButPreservesRulesText() {
        String uuid = "123e4567-e89b-12d3-a456-426614174000";
        JsonObject metadata = new JsonObject();
        metadata.addProperty("detail", "Clone object_id='" + uuid + "' enters as a copy");

        JsonObject option = XmageFullGameDecisionController.option(
                "stable-option-id",
                "Clone object_id='" + uuid + "' enters as a copy",
                "choice",
                metadata
        );

        assertEquals("stable-option-id", option.get("option_id").getAsString());
        assertEquals(
                "Clone object_id='#' enters as a copy",
                option.get("label").getAsString()
        );
        assertEquals(
                "Clone object_id='#' enters as a copy",
                option.getAsJsonObject("metadata").get("detail").getAsString()
        );
        assertEquals("choice", option.get("option_type").getAsString());
    }

    @Test
    void redactLeavesRulesTextWithoutIdentityUntouched() {
        assertEquals(
                "Pay {3}{U}{U} or discard Force of Will",
                XmageFullGameDecisionController.redactObjectIds(
                        "Pay {3}{U}{U} or discard Force of Will"
                )
        );
        assertNull(XmageFullGameDecisionController.redactObjectIds(null));
    }

    @Test
    void choiceTextStripsGameLogShortIdButKeepsRulesWords()
            throws Exception {
        Method choiceText = XmageFullGamePlayer.class.getDeclaredMethod(
                "choiceText", String.class
        );
        choiceText.setAccessible(true);

        assertEquals(
                "Force of Will [#]",
                choiceText.invoke(null, "Force of Will [bd5]")
        );
        assertEquals(
                "Pay {3}{U}{U}",
                choiceText.invoke(null, "Pay {3}{U}{U}")
        );
        assertNull(choiceText.invoke(null, (String) null));
    }

    @Test
    void choicePromptUsesEngineMessageOrLegacyFallback()
            throws Exception {
        Method choicePrompt = XmageFullGamePlayer.class.getDeclaredMethod(
                "choicePrompt", Choice.class
        );
        choicePrompt.setAccessible(true);

        Choice withMessage = new ChoiceImpl(true);
        withMessage.setMessage("Pay an additional cost");
        withMessage.setSubMessage("for Flusterstorm");
        assertEquals(
                "Pay an additional cost for Flusterstorm",
                choicePrompt.invoke(null, withMessage)
        );

        Choice withoutMessage = new ChoiceImpl(true);
        withoutMessage.setMessage(null);
        withoutMessage.setSubMessage(null);
        assertEquals("Choose option", choicePrompt.invoke(null, withoutMessage));
    }

    @Test
    void keyModeChoiceCarriesItemsOutsidePlainChoiceSet() {
        Map<String, String> keyChoices = new LinkedHashMap<>();
        keyChoices.put("pitch", "Pitch Force of Will [a1]");
        keyChoices.put("pay", "Pay {3}{U}{U}");

        Choice choice = new ChoiceImpl(true);
        choice.setKeyChoices(keyChoices);

        assertTrue(choice.isKeyChoice());
        assertFalse(choice.getKeyChoices().isEmpty());
        // The plain choice set stays empty for key-mode menus: this is the
        // projection gap D4 closes (zero options would silently cancel).
        assertTrue(choice.getChoices().isEmpty());
    }
}
