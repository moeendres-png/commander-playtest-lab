#!/usr/bin/env python3
"""WS-39 qualification-only native stack snapshot support for WS-32 v1.0.2.

This overlay materializes only already-cast stack objects from the frozen
requested starting state. It delegates target legality and modal structure to
XMage-native SpellAbility/Target/Mode objects. It does not cast spells, pay
costs, resolve effects, or choose pilot decisions.
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
        raise SystemExit(f"WS39_STACK_STATE_ANCHOR_MISMATCH:{label}:count={count}")
    return text.replace(old, new, 1)


def main() -> int:
    text = SCENARIO.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "import mage.game.PutToBattlefieldInfo;\n",
        "import mage.game.PutToBattlefieldInfo;\n"
        "import mage.game.stack.Spell;\n"
        "import mage.game.stack.StackObject;\n"
        "import mage.abilities.Ability;\n"
        "import mage.abilities.Mode;\n"
        "import mage.abilities.SpellAbility;\n"
        "import mage.abilities.effects.Effect;\n"
        "import mage.abilities.effects.common.PutOnLibraryTargetEffect;\n"
        "import mage.target.Target;\n",
        "stack-imports",
    )
    text = replace_once(
        text,
        '            "commander_history"\n    );\n',
        '            "commander_history", "stack_state"\n    );\n',
        "top-level-stack-state",
    )
    text = replace_once(
        text,
        '    private static final Set<String> ZONES = Set.of("hand", "library", "graveyard", "exile", "battlefield");\n',
        '    private static final Set<String> ZONES = Set.of("hand", "library", "graveyard", "exile", "battlefield", "stack");\n'
        '    private static final Set<String> STACK_ITEM = Set.of(\n'
        '            "source_semantic_id", "controller", "targets", "modes", "cast_complete", "costs_paid"\n'
        '    );\n',
        "stack-schema",
    )
    text = replace_once(
        text,
        '            "attached_to", "counters", "known_to", "native_object_id",\n'
        '            "stack", "mana", "priority_holder", "active_player", "turn", "phase", "step"\n',
        '            "attached_to", "counters", "known_to", "native_object_id",\n'
        '            "mana", "priority_holder", "active_player", "turn", "phase", "step"\n',
        "remove-stack-unsupported-marker",
    )

    preflight_anchor = '''        // Full preflight before any native game mutation: malformed input must be retry-safe.
'''
    preflight = '''        for (JsonElement element : optionalArray(scenario, "stack_state")) {
            if (!element.isJsonObject()) throw fail("INVALID_SCENARIO: stack_state entry must be object");
            JsonObject stackSpec = element.getAsJsonObject();
            rejectUnknown(stackSpec, STACK_ITEM, "stack_state");
            if (!booleanValue(stackSpec, "cast_complete", false)) {
                throw fail("UNSUPPORTED_SCENARIO_DIMENSION: stack cast_complete=false");
            }
            if (!booleanValue(stackSpec, "costs_paid", false)) {
                throw fail("UNSUPPORTED_SCENARIO_DIMENSION: stack costs_paid=false");
            }
            text(stackSpec, "source_semantic_id");
            playerSeatValue(text(stackSpec, "controller"), players.size());
            JsonArray modes = optionalArray(stackSpec, "modes");
            if (modes.size() > 1) {
                throw fail("UNSUPPORTED_SCENARIO_DIMENSION: multiple explicit stack modes");
            }
            for (JsonElement mode : modes) {
                if (!mode.isJsonPrimitive() || !mode.getAsJsonPrimitive().isString()) {
                    throw fail("INVALID_SCENARIO: stack mode must be string");
                }
                if (!"put_creature_on_bottom_of_owners_library".equals(mode.getAsString())) {
                    throw fail("UNSUPPORTED_SCENARIO_DIMENSION: unknown explicit stack mode " + mode.getAsString());
                }
            }
            for (JsonElement target : optionalArray(stackSpec, "targets")) {
                if (!target.isJsonPrimitive() || !target.getAsJsonPrimitive().isString()) {
                    throw fail("INVALID_SCENARIO: stack target must be semantic string");
                }
            }
        }

        // Full preflight before any native game mutation: malformed input must be retry-safe.
'''
    text = replace_once(text, preflight_anchor, preflight, "stack-preflight")

    bind_anchor = '''            List<Card> exile = bind(optionalArray(zones, "exile"), available, used, semanticMap);
            List<PutToBattlefieldInfo> battlefield = bindBattlefield(
'''
    bind_new = '''            List<Card> exile = bind(optionalArray(zones, "exile"), available, used, semanticMap);
            bind(optionalArray(zones, "stack"), available, used, semanticMap);
            List<PutToBattlefieldInfo> battlefield = bindBattlefield(
'''
    text = replace_once(text, bind_anchor, bind_new, "bind-stack-source")

    validation_anchor = '''        JsonObject validation = validateNative(game, players, bySeat, semanticMap, ledger);
        JsonObject commanderHistoryValidation = restoreCommanderHistory(
'''
    validation_new = '''        applyStackState(scenario, game, players, semanticMap);
        JsonObject validation = validateNative(game, players, bySeat, semanticMap, ledger);
        validation.add("stack_state", validateStackState(scenario, game, players, semanticMap));
        JsonObject commanderHistoryValidation = restoreCommanderHistory(
'''
    text = replace_once(text, validation_anchor, validation_new, "apply-stack-before-validation")

    validate_zone_anchor = '''            validateBattlefield(game, player, optionalArray(zones, "battlefield"), semanticMap);
'''
    validate_zone_new = '''            validateBattlefield(game, player, optionalArray(zones, "battlefield"), semanticMap);
            validateZone(game, player, optionalArray(zones, "stack"), Zone.STACK, semanticMap);
'''
    text = replace_once(text, validate_zone_anchor, validate_zone_new, "validate-stack-zone")

    helper_anchor = '''    private static UUID nativeId(Map<UUID, String> map, String semantic) {
'''
    helper = r'''    private static void applyStackState(
            JsonObject scenario,
            Game game,
            List<? extends Player> players,
            Map<UUID, String> semanticMap
    ) {
        JsonArray stackSpecs = optionalArray(scenario, "stack_state");
        if (!game.getStack().isEmpty()) {
            throw fail("NATIVE_VALIDATION_FAILED: initial native stack is not empty");
        }
        // Frozen stack_state is top-to-bottom. Push bottom-to-top so native iteration
        // returns the frozen top object first.
        for (int index = stackSpecs.size() - 1; index >= 0; index--) {
            JsonObject spec = stackSpecs.get(index).getAsJsonObject();
            String sourceSemantic = text(spec, "source_semantic_id");
            UUID sourceId = nativeId(semanticMap, sourceSemantic);
            Card card = game.getCard(sourceId);
            if (card == null) throw fail("NATIVE_VALIDATION_FAILED: stack source " + sourceSemantic);
            int controllerSeat = playerSeatValue(text(spec, "controller"), players.size());
            Player controller = players.get(controllerSeat - 1);
            SpellAbility ability = card.getSpellAbility().copy();
            ability.setControllerId(controller.getId());

            applyRequestedStackMode(spec, ability, sourceSemantic);
            JsonArray requestedTargets = optionalArray(spec, "targets");
            if (requestedTargets.size() != ability.getTargets().size()) {
                throw fail("NATIVE_VALIDATION_FAILED: stack target group cardinality " + sourceSemantic);
            }
            for (int targetIndex = 0; targetIndex < requestedTargets.size(); targetIndex++) {
                String targetSemantic = requestedTargets.get(targetIndex).getAsString();
                UUID targetId = stackTargetNativeId(targetSemantic, players, semanticMap);
                Target target = ability.getTargets().get(targetIndex);
                if (!target.canTarget(controller.getId(), targetId, ability, game)) {
                    throw fail("NATIVE_VALIDATION_FAILED: illegal pre-cast target " + targetSemantic);
                }
                target.addTarget(targetId, ability, game);
            }
            if (!ability.getTargets().isChosen(game)) {
                throw fail("NATIVE_VALIDATION_FAILED: incomplete pre-cast targets " + sourceSemantic);
            }
            game.setZone(card.getMainCard().getId(), Zone.STACK);
            Spell spell = new Spell(card, ability, controller.getId(), Zone.HAND, game);
            game.getStack().push(game, spell);
        }
    }

    private static void applyRequestedStackMode(JsonObject spec, SpellAbility ability, String sourceSemantic) {
        JsonArray requestedModes = optionalArray(spec, "modes");
        if (requestedModes.isEmpty()) {
            if (ability.getModes().size() != 1) {
                throw fail("NATIVE_VALIDATION_FAILED: modal stack spell lacks explicit frozen mode " + sourceSemantic);
            }
            return;
        }
        if (requestedModes.size() != 1
                || !"put_creature_on_bottom_of_owners_library".equals(requestedModes.get(0).getAsString())) {
            throw fail("UNSUPPORTED_SCENARIO_DIMENSION: unsupported explicit stack mode " + sourceSemantic);
        }
        Mode match = null;
        for (Mode nativeMode : ability.getModes().values()) {
            boolean putOnLibrary = false;
            for (Effect effect : nativeMode.getEffects()) {
                if (effect instanceof PutOnLibraryTargetEffect) {
                    putOnLibrary = true;
                }
            }
            if (putOnLibrary) {
                if (match != null) {
                    throw fail("NATIVE_VALIDATION_FAILED: stack mode mapping not unique " + sourceSemantic);
                }
                match = nativeMode;
            }
        }
        if (match == null) {
            throw fail("NATIVE_VALIDATION_FAILED: requested stack mode absent " + sourceSemantic);
        }
        ability.getModes().clearSelectedModes();
        ability.getModes().addSelectedMode(match.getId());
        ability.getModes().setActiveMode(match);
        ability.getModes().setPreselected(true);
    }

    private static JsonObject validateStackState(
            JsonObject scenario,
            Game game,
            List<? extends Player> players,
            Map<UUID, String> semanticMap
    ) {
        JsonArray specs = optionalArray(scenario, "stack_state");
        requireNative(game.getStack().size() == specs.size(), "stack-cardinality");
        JsonArray readback = new JsonArray();
        int index = 0;
        for (StackObject stackObject : game.getStack()) {
            JsonObject spec = specs.get(index++).getAsJsonObject();
            String sourceSemantic = text(spec, "source_semantic_id");
            UUID expectedSource = nativeId(semanticMap, sourceSemantic);
            requireNative(expectedSource.equals(stackObject.getSourceId()), "stack-source:" + sourceSemantic);
            int controllerSeat = playerSeatValue(text(spec, "controller"), players.size());
            requireNative(
                    players.get(controllerSeat - 1).getId().equals(stackObject.getControllerId()),
                    "stack-controller:" + sourceSemantic
            );
            Ability stackAbility = stackObject.getStackAbility();
            JsonArray targets = optionalArray(spec, "targets");
            List<UUID> actualTargets = new ArrayList<>();
            for (Target target : stackAbility.getAllSelectedTargets()) {
                actualTargets.addAll(target.getTargets());
            }
            requireNative(actualTargets.size() == targets.size(), "stack-target-cardinality:" + sourceSemantic);
            for (int targetIndex = 0; targetIndex < targets.size(); targetIndex++) {
                String targetSemantic = targets.get(targetIndex).getAsString();
                requireNative(
                        stackTargetNativeId(targetSemantic, players, semanticMap).equals(actualTargets.get(targetIndex)),
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
        }
        JsonObject result = new JsonObject();
        result.addProperty("validator", "xmage-native-stack-state/1.0.0");
        result.addProperty("rules_core_authoritative", true);
        result.addProperty("stack_count", specs.size());
        result.add("objects_top_to_bottom", readback);
        result.addProperty("valid", true);
        return result;
    }

    private static void validateRequestedStackMode(JsonObject spec, Ability ability, String sourceSemantic) {
        JsonArray requestedModes = optionalArray(spec, "modes");
        if (requestedModes.isEmpty()) {
            requireNative(ability.getModes().size() == 1, "stack-mode-unambiguous:" + sourceSemantic);
            return;
        }
        requireNative(ability.getModes().getSelectedModes().size() == 1, "stack-selected-mode-count:" + sourceSemantic);
        UUID selectedId = ability.getModes().getSelectedModes().get(0);
        Mode selected = ability.getModes().get(selectedId);
        requireNative(selected != null, "stack-selected-mode-present:" + sourceSemantic);
        boolean putOnLibrary = false;
        for (Effect effect : selected.getEffects()) {
            if (effect instanceof PutOnLibraryTargetEffect) putOnLibrary = true;
        }
        requireNative(putOnLibrary, "stack-mode-bottom-library:" + sourceSemantic);
    }

    private static UUID stackTargetNativeId(
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

    private static int playerSeatValue(String player, int playerCount) {
        if (!player.matches("P[1-9][0-9]*")) throw fail("INVALID_PLAYER_IDENTITY: " + player);
        int seat = Integer.parseInt(player.substring(1));
        if (seat < 1 || seat > playerCount) throw fail("INVALID_PLAYER_IDENTITY: " + player);
        return seat;
    }

    private static UUID nativeId(Map<UUID, String> map, String semantic) {
'''
    text = replace_once(text, helper_anchor, helper, "stack-native-helpers")

    SCENARIO.write_text(text, encoding="utf-8")
    print("WS39_STACK_STATE_OVERLAY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
