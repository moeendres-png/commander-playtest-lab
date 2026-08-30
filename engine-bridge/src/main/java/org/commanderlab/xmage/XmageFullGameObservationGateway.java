package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonPrimitive;
import mage.game.Game;
import mage.players.Player;

import java.util.HashSet;
import java.util.Locale;
import java.util.Set;

/**
 * Single outbound visibility authority for external-pilot decision material.
 *
 * <p>The KnowledgeLedger is the only visibility model. This gateway only audits
 * free-form outbound channels (prompt, context, option identifiers/labels/
 * metadata, source metadata and future nested fields) against the ledger's
 * actor-entitled knowledge. It never reconstructs legality or maintains a
 * second hidden-information model.</p>
 */
final class XmageFullGameObservationGateway {

    record SafeDecision(
            JsonObject actorView,
            String prompt,
            JsonObject context,
            JsonArray legalOptions,
            JsonObject sourceObject
    ) {
    }

    private XmageFullGameObservationGateway() {
    }

    static SafeDecision validate(
            Game game,
            Player actor,
            String prompt,
            JsonObject context,
            JsonArray legalOptions,
            JsonObject sourceObject
    ) {
        return validate(game, actor, actor, prompt, context, legalOptions, sourceObject);
    }

    static SafeDecision validate(
            Game game,
            Player viewer,
            Player decisionSubject,
            String prompt,
            JsonObject context,
            JsonArray legalOptions,
            JsonObject sourceObject
    ) {
        XmageKnowledgeLedger ledger = XmageFullGameStateRedactor.knowledgeLedger(game);
        JsonObject actorView = ledger.snapshot(game, viewer, decisionSubject);
        VisibilityIndex index = visibilityIndex(ledger, game, viewer, actorView);

        String safePrompt = prompt == null ? "" : prompt;
        JsonObject safeContext = context == null ? new JsonObject() : context.deepCopy();
        JsonArray safeOptions = legalOptions == null ? new JsonArray() : legalOptions.deepCopy();
        JsonObject safeSource = sourceObject == null ? null : sourceObject.deepCopy();

        assertSafeString("prompt", safePrompt, index);
        assertSafeJson("context", safeContext, index);
        assertSafeJson("legal_options", safeOptions, index);
        if (safeSource != null) {
            assertSafeJson("source_object", safeSource, index);
        }
        return new SafeDecision(actorView, safePrompt, safeContext, safeOptions, safeSource);
    }

    private static VisibilityIndex visibilityIndex(
            XmageKnowledgeLedger ledger,
            Game game,
            Player viewer,
            JsonObject actorView
    ) {
        Set<String> visibleTokens = new HashSet<>();
        collectVisibleTokens(actorView, visibleTokens);

        Set<String> forbidden = new HashSet<>();
        for (String token : ledger.forbiddenIdentityTokens(game, viewer)) {
            if (token != null && !token.isBlank()) {
                String folded = token.toLowerCase(Locale.ROOT);
                if (!visibleTokens.contains(folded)) {
                    forbidden.add(folded);
                }
            }
        }
        return new VisibilityIndex(Set.copyOf(forbidden));
    }

    private static void collectVisibleTokens(JsonElement element, Set<String> tokens) {
        if (element == null || element.isJsonNull()) {
            return;
        }
        if (element.isJsonPrimitive()) {
            JsonPrimitive primitive = element.getAsJsonPrimitive();
            if (primitive.isString()) {
                String value = primitive.getAsString();
                if (!value.isBlank()) {
                    tokens.add(value.toLowerCase(Locale.ROOT));
                }
            }
            return;
        }
        if (element.isJsonArray()) {
            for (JsonElement item : element.getAsJsonArray()) {
                collectVisibleTokens(item, tokens);
            }
            return;
        }
        JsonObject object = element.getAsJsonObject();
        for (String key : object.keySet()) {
            collectVisibleTokens(object.get(key), tokens);
        }
    }

    private static void assertSafeJson(String path, JsonElement element, VisibilityIndex index) {
        if (element == null || element.isJsonNull()) {
            return;
        }
        if (element.isJsonPrimitive()) {
            JsonPrimitive primitive = element.getAsJsonPrimitive();
            if (primitive.isString()) {
                assertSafeString(path, primitive.getAsString(), index);
            }
            return;
        }
        if (element.isJsonArray()) {
            int i = 0;
            for (JsonElement item : element.getAsJsonArray()) {
                assertSafeJson(path + "[" + i++ + "]", item, index);
            }
            return;
        }
        JsonObject object = element.getAsJsonObject();
        for (String key : object.keySet()) {
            assertSafeJson(path + "." + key, object.get(key), index);
        }
    }

    private static void assertSafeString(String path, String value, VisibilityIndex index) {
        if (value == null || value.isEmpty()) {
            return;
        }
        String folded = value.toLowerCase(Locale.ROOT);
        for (String forbidden : index.forbiddenIdentityTokens()) {
            if (!forbidden.isBlank() && folded.contains(forbidden)) {
                throw new IllegalStateException(
                        "HIDDEN_INFORMATION_LEAK: unauthorized identity token in " + path
                );
            }
        }
    }

    private record VisibilityIndex(Set<String> forbiddenIdentityTokens) {
    }
}
