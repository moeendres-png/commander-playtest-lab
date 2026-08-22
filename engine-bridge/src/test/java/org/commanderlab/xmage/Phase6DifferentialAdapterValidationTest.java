package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class Phase6DifferentialAdapterValidationTest {

    @TempDir
    Path tempDir;

    @Test
    void rejectsNullRequest() throws Exception {
        assertRejects("null");
    }

    @Test
    void rejectsNonObjectInputState() throws Exception {
        assertRejects("""
                {
                  "case_id": "commander_tax_third_cast",
                  "input_state": []
                }
                """);
    }

    @Test
    void rejectsWrongFormatBeforeProviderScenarioCreation() throws Exception {
        assertRejects(taxFixture("modern", "cast_commander", "2", "5"));
    }

    @Test
    void rejectsWrongActionBeforeProviderScenarioCreation() throws Exception {
        assertRejects(taxFixture("commander", "check_state_based_actions", "2", "5"));
    }

    @Test
    void rejectsNegativePriorCasts() throws Exception {
        assertRejects(taxFixture("commander", "cast_commander", "-1", "5"));
    }

    @Test
    void rejectsFractionalPriorCasts() throws Exception {
        assertRejects(taxFixture("commander", "cast_commander", "1.5", "5"));
    }

    @Test
    void rejectsUnsupportedDefendingLifeBeforeProviderScenarioCreation() throws Exception {
        assertRejects(damageFixture("39", "12"));
    }

    @Test
    void rejectsNegativeCommanderDamageBeforeProviderScenarioCreation() throws Exception {
        assertRejects(damageFixture("40", "-1"));
    }

    @Test
    void rejectsFractionalCommanderDamageBeforeProviderScenarioCreation() throws Exception {
        assertRejects(damageFixture("40", "12.5"));
    }

    @Test
    void preservesNullLossReasonKeyForFrozenNonCombinedDamageFixture() throws Exception {
        Path input = tempDir.resolve("input.json");
        Path output = tempDir.resolve("output.json");
        Files.writeString(input, nonCombinedDamageFixture(), StandardCharsets.UTF_8);

        Phase6DifferentialAdapter.run(input, output);

        JsonObject response = JsonParser.parseString(
                Files.readString(output, StandardCharsets.UTF_8)
        ).getAsJsonObject();
        JsonObject normalized = response.getAsJsonObject("normalized_output");
        assertTrue(normalized.has("loss_reason"));
        assertTrue(normalized.get("loss_reason").isJsonNull());
    }

    private void assertRejects(String payload) throws Exception {
        Path input = tempDir.resolve("input.json");
        Path output = tempDir.resolve("output.json");
        Files.writeString(input, payload, StandardCharsets.UTF_8);
        assertThrows(
                IllegalArgumentException.class,
                () -> Phase6DifferentialAdapter.run(input, output)
        );
    }

    private static String taxFixture(
            String format,
            String action,
            String priorCasts,
            String printedManaValue
    ) {
        return """
                {
                  "case_id": "commander_tax_third_cast",
                  "input_state": {
                    "format": "%s",
                    "commander_name": "Korvold, Fae-Cursed King",
                    "printed_mana_value": %s,
                    "prior_command_zone_casts": %s,
                    "action": "%s"
                  }
                }
                """.formatted(format, printedManaValue, priorCasts, action);
    }

    private static String damageFixture(String defendingLife, String damage) {
        return """
                {
                  "case_id": "commander_damage_not_combined",
                  "input_state": {
                    "format": "commander",
                    "defending_player_life": %s,
                    "commander_damage": {
                      "Ishai, Ojutai Dragonspeaker": %s
                    },
                    "action": "check_state_based_actions"
                  }
                }
                """.formatted(defendingLife, damage);
    }

    private static String nonCombinedDamageFixture() {
        return """
                {
                  "case_id": "commander_damage_not_combined",
                  "input_state": {
                    "format": "commander",
                    "defending_player_life": 40,
                    "commander_damage": {
                      "Ishai, Ojutai Dragonspeaker": 12,
                      "Rograkh, Son of Rohgahh": 10
                    },
                    "action": "check_state_based_actions"
                  }
                }
                """;
    }
}
