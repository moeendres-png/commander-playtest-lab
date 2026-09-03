#!/usr/bin/env python3
"""WS-39 qualification-only stack identity/completion remediation.

Run after apply_ws39_stack_state_overlay.py.  The transform does not implement
Magic legality in Commander Lab: target legality and forced-target completion
remain XMage-native.  Frozen semantic target references are resolved only by
exact semantic id, unique case-insensitive semantic id, or exact frozen
card-lineage identity from successor_requested_state.  If a fully-cast frozen
stack object omits a target group that XMage requires, completion is permitted
only when XMage Target.tryToAutoChoose proves the choice is forced; otherwise
setup fails closed.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26Scenario.java"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"WS39_STACK_IDENTITY_ANCHOR_MISMATCH:{label}:count={count}")
    return text.replace(old, new, 1)


def replace_count(text: str, old: str, new: str, expected: int, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != expected:
        raise SystemExit(
            f"WS39_STACK_IDENTITY_ANCHOR_MISMATCH:{label}:count={count}:expected={expected}"
        )
    return text.replace(old, new)


def main() -> int:
    text = SCENARIO.read_text(encoding="utf-8")

    apply_old = '''            applyRequestedStackMode(spec, ability, sourceSemantic);
            JsonArray requestedTargets = optionalArray(spec, "targets");
            if (requestedTargets.size() != ability.getTargets().size()) {
                throw fail("NATIVE_VALIDATION_FAILED: stack target group cardinality " + sourceSemantic);
            }
            for (int targetIndex = 0; targetIndex < requestedTargets.size(); targetIndex++) {
                String targetSemantic = requestedTargets.get(targetIndex).getAsString();
'''
    apply_new = '''            applyRequestedStackMode(spec, ability, sourceSemantic);
            JsonArray requestedTargets = optionalArray(spec, "targets");
            JsonArray nativeTargets = stackTargetsForConstruction(
                    requestedTargets, ability, game, players, semanticMap, sourceSemantic
            );
            if (nativeTargets.size() != ability.getTargets().size()) {
                throw fail("NATIVE_VALIDATION_FAILED: stack target group cardinality " + sourceSemantic);
            }
            for (int targetIndex = 0; targetIndex < nativeTargets.size(); targetIndex++) {
                String targetSemantic = nativeTargets.get(targetIndex).getAsString();
'''
    text = replace_once(text, apply_old, apply_new, "forced-target-construction")

    text = replace_count(
        text,
        "stackTargetNativeId(targetSemantic, players, semanticMap)",
        "stackTargetNativeId(targetSemantic, scenario, players, semanticMap)",
        2,
        "target-resolver-call-sites",
    )

    validate_old = '''            JsonArray targets = optionalArray(spec, "targets");
            List<UUID> actualTargets = new ArrayList<>();
            for (Target target : stackAbility.getAllSelectedTargets()) {
                actualTargets.addAll(target.getTargets());
            }
            requireNative(actualTargets.size() == targets.size(), "stack-target-cardinality:" + sourceSemantic);
            for (int targetIndex = 0; targetIndex < targets.size(); targetIndex++) {
                String targetSemantic = targets.get(targetIndex).getAsString();
                requireNative(
                        stackTargetNativeId(targetSemantic, scenario, players, semanticMap).equals(actualTargets.get(targetIndex)),
                        "stack-target:" + targetSemantic
                );
            }
            validateRequestedStackMode(spec, stackAbility, sourceSemantic);

            JsonObject row = new JsonObject();
            row.addProperty("source_semantic_id", sourceSemantic);
            row.addProperty("controller", "P" + controllerSeat);
            row.addProperty("cast_complete", true);
            row.addProperty("costs_paid", true);
            row.add("targets", targets.deepCopy());
            row.add("modes", optionalArray(spec, "modes").deepCopy());
            readback.add(row);
'''
    validate_new = '''            JsonArray targets = optionalArray(spec, "targets");
            List<UUID> actualTargets = new ArrayList<>();
            for (Target target : stackAbility.getAllSelectedTargets()) {
                actualTargets.addAll(target.getTargets());
            }
            JsonArray nativeCompletionTargets = new JsonArray();
            if (!targets.isEmpty()) {
                requireNative(actualTargets.size() == targets.size(), "stack-target-cardinality:" + sourceSemantic);
                for (int targetIndex = 0; targetIndex < targets.size(); targetIndex++) {
                    String targetSemantic = targets.get(targetIndex).getAsString();
                    requireNative(
                            stackTargetNativeId(targetSemantic, scenario, players, semanticMap).equals(actualTargets.get(targetIndex)),
                            "stack-target:" + targetSemantic
                    );
                }
            } else if (!stackAbility.getTargets().isEmpty()) {
                requireNative(
                        actualTargets.size() == stackAbility.getTargets().size(),
                        "stack-forced-target-cardinality:" + sourceSemantic
                );
                for (int targetIndex = 0; targetIndex < stackAbility.getTargets().size(); targetIndex++) {
                    Target target = stackAbility.getTargets().get(targetIndex);
                    requireNative(
                            target.getMinNumberOfTargets() == 1 && target.getMaxNumberOfTargets() == 1,
                            "stack-forced-target-not-single-required:" + sourceSemantic
                    );
                    String semantic = stackTargetSemanticId(actualTargets.get(targetIndex), players, semanticMap);
                    requireNative(semantic != null, "stack-forced-target-semantic-id:" + sourceSemantic);
                    nativeCompletionTargets.add(semantic);
                }
            } else {
                requireNative(actualTargets.isEmpty(), "stack-target-cardinality:" + sourceSemantic);
            }
            validateRequestedStackMode(spec, stackAbility, sourceSemantic);

            JsonObject row = new JsonObject();
            row.addProperty("source_semantic_id", sourceSemantic);
            row.addProperty("controller", "P" + controllerSeat);
            row.addProperty("cast_complete", true);
            row.addProperty("costs_paid", true);
            row.add("targets", targets.deepCopy());
            if (!nativeCompletionTargets.isEmpty()) {
                row.add("native_forced_completion_targets", nativeCompletionTargets);
                row.addProperty("native_completion_selector", "XMAGE_TARGET_TRY_TO_AUTO_CHOOSE");
            }
            row.add("modes", optionalArray(spec, "modes").deepCopy());
            readback.add(row);
'''
    text = replace_once(text, validate_old, validate_new, "forced-target-readback")

    resolver_old = '''    private static UUID stackTargetNativeId(
            String semantic,
            List<? extends Player> players,
            Map<UUID, String> semanticMap
    ) {
        if (semantic.matches("P[1-9][0-9]*")) {
            int seat = playerSeatValue(semantic, players.size());
            return players.get(seat - 1).getId();
        }
        return nativeId(semanticMap, semantic);
    }

'''
    resolver_new = r'''    private static JsonArray stackTargetsForConstruction(
            JsonArray requestedTargets,
            Ability ability,
            Game game,
            List<? extends Player> players,
            Map<UUID, String> semanticMap,
            String sourceSemantic
    ) {
        if (!requestedTargets.isEmpty() || ability.getTargets().isEmpty()) {
            return requestedTargets.deepCopy();
        }
        JsonArray completed = new JsonArray();
        for (Target target : ability.getTargets()) {
            if (target.getMinNumberOfTargets() != 1 || target.getMaxNumberOfTargets() != 1) {
                throw fail("NATIVE_VALIDATION_FAILED: stack omitted non-forced target " + sourceSemantic);
            }
            UUID forced = target.tryToAutoChoose(ability.getControllerId(), ability, game);
            if (forced == null) {
                throw fail("NATIVE_VALIDATION_FAILED: stack omitted target is not uniquely forced " + sourceSemantic);
            }
            String semantic = stackTargetSemanticId(forced, players, semanticMap);
            if (semantic == null) {
                throw fail("NATIVE_VALIDATION_FAILED: forced stack target lacks semantic identity " + sourceSemantic);
            }
            completed.add(semantic);
        }
        return completed;
    }

    private static UUID stackTargetNativeId(
            String semantic,
            JsonObject scenario,
            List<? extends Player> players,
            Map<UUID, String> semanticMap
    ) {
        if (semantic.matches("P[1-9][0-9]*")) {
            int seat = playerSeatValue(semantic, players.size());
            return players.get(seat - 1).getId();
        }

        List<UUID> exact = semanticMap.entrySet().stream()
                .filter(entry -> semantic.equals(entry.getValue()))
                .map(Map.Entry::getKey)
                .toList();
        if (exact.size() == 1) return exact.get(0);
        if (exact.size() > 1) {
            throw fail("NATIVE_VALIDATION_FAILED: stack semantic id not unique " + semantic);
        }

        List<UUID> caseInsensitive = semanticMap.entrySet().stream()
                .filter(entry -> semantic.equalsIgnoreCase(entry.getValue()))
                .map(Map.Entry::getKey)
                .toList();
        if (caseInsensitive.size() == 1) return caseInsensitive.get(0);
        if (caseInsensitive.size() > 1) {
            throw fail("NATIVE_VALIDATION_FAILED: stack case-insensitive semantic alias not unique " + semantic);
        }

        JsonObject requested = object(scenario, "successor_requested_state");
        JsonArray semanticObjects = optionalArray(requested, "semantic_objects");
        String requestedLineage = "line:" + semantic;
        List<UUID> lineageMatches = new ArrayList<>();
        for (JsonElement element : semanticObjects) {
            if (!element.isJsonObject()) continue;
            JsonObject object = element.getAsJsonObject();
            if (!requestedLineage.equals(optionalText(object, "card_lineage_id", ""))) continue;
            String currentSemantic = text(object, "semantic_id");
            for (Map.Entry<UUID, String> entry : semanticMap.entrySet()) {
                if (currentSemantic.equals(entry.getValue())) {
                    lineageMatches.add(entry.getKey());
                }
            }
        }
        if (lineageMatches.size() == 1) return lineageMatches.get(0);
        if (lineageMatches.size() > 1) {
            throw fail("NATIVE_VALIDATION_FAILED: stack lineage alias not unique " + semantic);
        }
        throw fail("NATIVE_VALIDATION_FAILED: stale semantic id " + semantic);
    }

    private static String stackTargetSemanticId(
            UUID nativeTarget,
            List<? extends Player> players,
            Map<UUID, String> semanticMap
    ) {
        for (int zero = 0; zero < players.size(); zero++) {
            if (players.get(zero).getId().equals(nativeTarget)) return "P" + (zero + 1);
        }
        return semanticMap.get(nativeTarget);
    }

'''
    text = replace_once(text, resolver_old, resolver_new, "stack-target-resolver")

    SCENARIO.write_text(text, encoding="utf-8")
    print("WS39_STACK_IDENTITY_COMPLETION_OVERLAY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
