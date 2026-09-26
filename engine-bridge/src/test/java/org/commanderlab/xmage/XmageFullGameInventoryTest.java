package org.commanderlab.xmage;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashSet;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class XmageFullGameInventoryTest {

    @Test
    void choiceInventoryCoversCastSelectionCallbacksAndRemainsFailClosed()
            throws Exception {
        String repoRoot = System.getProperty("commanderlab.repoRoot");
        assertNotNull(repoRoot, "commanderlab.repoRoot must be supplied by the bridge build");
        Path inventoryPath = Path.of(
                repoRoot,
                "artifacts",
                "xmage-full-game",
                "DECISION_CLASS_INVENTORY.json"
        );
        JsonObject payload = JsonParser.parseString(
                Files.readString(inventoryPath, StandardCharsets.UTF_8)
        ).getAsJsonObject();

        assertEquals(17, payload.getAsJsonArray("decision_classes").size());
        assertFalse(payload.get("random_or_default_discretionary_fallback").getAsBoolean());

        JsonObject choice = null;
        for (JsonElement element : payload.getAsJsonArray("decision_classes")) {
            JsonObject candidate = element.getAsJsonObject();
            if ("choice".equals(candidate.get("decision_class").getAsString())) {
                choice = candidate;
                break;
            }
        }
        assertNotNull(choice, "choice decision class must exist");
        assertTrue(choice.get("fail_closed").getAsBoolean());

        Set<String> entryPoints = new LinkedHashSet<>();
        for (JsonElement element : choice.getAsJsonArray("additional_xmage_entry_points")) {
            entryPoints.add(element.getAsString());
        }
        assertEquals(
                Set.of("Player.chooseAbilityForCast", "Player.chooseLandOrSpellAbility"),
                entryPoints
        );
    }
}
