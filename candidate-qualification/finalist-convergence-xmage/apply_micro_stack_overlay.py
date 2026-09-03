#!/usr/bin/env python3
"""Qualification-only exact MICRO_STACK native-state overlay for XMage.

Extends the existing WS26 NATIVE_STATE_LOAD adapter with the minimum frozen
v1.0.1 stack surface: a fully cast native spell with exact controller/target.
No pilot-side legality or resolution is implemented here.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26Scenario.java"
LEDGER = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageKnowledgeLedger.java"
REPLAY = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26ReplayRecorder.java"
CANONICAL = ROOT / "candidate-qualification/finalist-convergence-xmage/canonical_v101.py"


def replace_exact(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor in {path}, observed {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    # Canonical scenario: retain stack semantic objects in an explicit stack zone
    # and carry the frozen provider-neutral stack_state verbatim.
    replace_exact(
        CANONICAL,
        'ZONE_KEYS = {"hand", "library", "graveyard", "exile", "battlefield"}\n',
        'ZONE_KEYS = {"hand", "library", "graveyard", "exile", "battlefield", "stack"}\n',
        "canonical zone surface",
    )
    replace_exact(
        CANONICAL,
        '        "players": players,\n    }\n',
        '        "players": players,\n        "stack_state": record.get("stack_state", []),\n    }\n',
        "canonical stack state",
    )

    # Native scenario imports and schema surface.
    replace_exact(
        SCENARIO,
        'import mage.game.PutToBattlefieldInfo;\n',
        'import mage.game.PutToBattlefieldInfo;\n'
        'import mage.game.stack.Spell;\n'
        'import mage.game.stack.StackObject;\n'
        'import mage.abilities.SpellAbility;\n'
        'import mage.target.Target;\n',
        "scenario stack imports",
    )
    replace_exact(
        SCENARIO,
        '            "execution_entry_mode", "temporal_state"\n',
        '            "execution_entry_mode", "temporal_state", "stack_state"\n',
        "scenario top-level stack field",
    )
    replace_exact(
        SCENARIO,
        '    private static final Set<String> ZONES = Set.of("hand", "library", "graveyard", "exile", "battlefield");\n',
        '    private static final Set<String> ZONES = Set.of("hand", "library", "graveyard", "exile", "battlefield", "stack");\n'
        '    private static final Set<String> STACK_ITEM = Set.of(\n'
        '            "semantic_stack_id", "source_object", "controller", "targets", "modes", "cast_complete"\n'
        '    );\n',
        "scenario stack zone/schema",
    )
    replace_exact(
        SCENARIO,
        '            "attached_to", "counters", "known_to", "native_object_id",\n'
        '            "stack", "mana", "priority_holder", "active_player", "turn", "phase", "step"\n',
        '            "attached_to", "counters", "known_to", "native_object_id",\n'
        '            "mana", "priority_holder", "active_player", "turn", "phase", "step"\n',
        "remove stack from unsupported dimensions",
    )

    # Bind stack-zone cards as semantic objects but do not place them through cheat().
    replace_exact(
        SCENARIO,
        '            List<Card> exile = bind(optionalArray(zones, "exile"), available, used, semanticMap);\n'
        '            List<PutToBattlefieldInfo> battlefield = bindBattlefield(\n',
        '            List<Card> exile = bind(optionalArray(zones, "exile"), available, used, semanticMap);\n'
        '            bind(optionalArray(zones, "stack"), available, used, semanticMap);\n'
        '            List<PutToBattlefieldInfo> battlefield = bindBattlefield(\n',
        "bind native stack source card",
    )
    replace_exact(
        SCENARIO,
        '        JsonObject validation = validateNative(game, players, bySeat, semanticMap, ledger);\n',
        '        applyStackState(scenario, game, players, semanticMap);\n'
        '        JsonObject validation = validateNative(game, players, bySeat, semanticMap, ledger);\n'
        '        validateStackState(scenario, game, players, semanticMap);\n',
        "apply and validate native stack",
    )
    replace_exact(
        SCENARIO,
        '            validateBattlefield(game, player, optionalArray(zones, "battlefield"), semanticMap);\n',
        '            validateBattlefield(game, player, optionalArray(zones, "battlefield"), semanticMap);\n'
        '            validateZone(game, player, optionalArray(zones, "stack"), Zone.STACK, semanticMap);\n',
        "validate stack-zone semantic object",
    )

    helper_anchor = '''    private static UUID nativeId(Map<UUID, String> map, String semantic) {
'''
    helper = '''    private static void applyStackState(
            JsonObject scenario,
            Game game,
            List<? extends Player> players,
            Map<UUID, String> semanticMap
    ) {
        JsonArray stackSpecs = optionalArray(scenario, "stack_state");
        if (!game.getStack().isEmpty()) {
            throw fail("NATIVE_VALIDATION_FAILED: initial native stack is not empty");
        }
        // Frozen stack_state is top-to-bottom. Push bottom-to-top so native peek is index 0.
        for (int index = stackSpecs.size() - 1; index >= 0; index--) {
            JsonObject spec = stackSpecs.get(index).getAsJsonObject();
            rejectUnknown(spec, STACK_ITEM, "stack_state");
            if (!booleanValue(spec, "cast_complete", false)) {
                throw fail("UNSUPPORTED_SCENARIO_DIMENSION: non-complete stack object");
            }
            JsonArray modes = optionalArray(spec, "modes");
            if (!modes.isEmpty()) {
                throw fail("UNSUPPORTED_SCENARIO_DIMENSION: explicit stack modes");
            }
            String sourceSemantic = text(spec, "source_object");
            UUID sourceId = nativeId(semanticMap, sourceSemantic);
            Card card = game.getCard(sourceId);
            if (card == null) throw fail("NATIVE_VALIDATION_FAILED: stack source " + sourceSemantic);
            int controllerSeat = playerSeatValue(text(spec, "controller"), players.size());
            Player controller = players.get(controllerSeat - 1);
            SpellAbility ability = card.getSpellAbility().copy();
            ability.setControllerId(controller.getId());

            JsonArray requestedTargets = optionalArray(spec, "targets");
            if (requestedTargets.size() != ability.getTargets().size()) {
                throw fail("NATIVE_VALIDATION_FAILED: stack target group cardinality " + sourceSemantic);
            }
            for (int targetIndex = 0; targetIndex < requestedTargets.size(); targetIndex++) {
                String targetSemantic = requestedTargets.get(targetIndex).getAsString();
                UUID targetId = nativeId(semanticMap, targetSemantic);
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

    private static void validateStackState(
            JsonObject scenario,
            Game game,
            List<? extends Player> players,
            Map<UUID, String> semanticMap
    ) {
        JsonArray specs = optionalArray(scenario, "stack_state");
        requireNative(game.getStack().size() == specs.size(), "stack-cardinality");
        int index = 0;
        for (StackObject stackObject : game.getStack()) {
            JsonObject spec = specs.get(index++).getAsJsonObject();
            UUID expectedSource = nativeId(semanticMap, text(spec, "source_object"));
            requireNative(expectedSource.equals(stackObject.getSourceId()), "stack-source:" + text(spec, "source_object"));
            int controllerSeat = playerSeatValue(text(spec, "controller"), players.size());
            requireNative(players.get(controllerSeat - 1).getId().equals(stackObject.getControllerId()), "stack-controller");
            JsonArray targets = optionalArray(spec, "targets");
            List<UUID> actualTargets = new ArrayList<>();
            for (Target target : stackObject.getStackAbility().getAllSelectedTargets()) {
                actualTargets.addAll(target.getTargets());
            }
            requireNative(actualTargets.size() == targets.size(), "stack-target-cardinality");
            for (int t = 0; t < targets.size(); t++) {
                requireNative(
                        nativeId(semanticMap, targets.get(t).getAsString()).equals(actualTargets.get(t)),
                        "stack-target:" + targets.get(t).getAsString()
                );
            }
        }
    }

    private static int playerSeatValue(String player, int playerCount) {
        if (!player.matches("P[1-9][0-9]*")) throw fail("INVALID_PLAYER_IDENTITY: " + player);
        int seat = Integer.parseInt(player.substring(1));
        if (seat < 1 || seat > playerCount) throw fail("INVALID_PLAYER_IDENTITY: " + player);
        return seat;
    }

    private static UUID nativeId(Map<UUID, String> map, String semantic) {
'''
    replace_exact(SCENARIO, helper_anchor, helper, "native stack helpers")

    # Stack targets are public game information. Emit only the same actor-entitled
    # opaque object identities already used for target legal options.
    replace_exact(
        LEDGER,
        'import mage.game.stack.StackObject;\n',
        'import mage.game.stack.StackObject;\nimport mage.target.Target;\n',
        "ledger target import",
    )
    replace_exact(
        LEDGER,
        '            item.addProperty("name", visible ? stackObject.getName() : "Face-down spell");\n'
        '            stack.add(item);\n',
        '            item.addProperty("name", visible ? stackObject.getName() : "Face-down spell");\n'
        '            JsonArray targetRefs = new JsonArray();\n'
        '            for (Target target : stackObject.getStackAbility().getAllSelectedTargets()) {\n'
        '                for (UUID targetId : target.getTargets()) {\n'
        '                    Player targetPlayer = game.getPlayer(targetId);\n'
        '                    if (targetPlayer != null && seat(targetPlayer.getId()) >= 0) {\n'
        '                        targetRefs.add(playerRef(targetPlayer.getId()));\n'
        '                        continue;\n'
        '                    }\n'
        '                    Permanent targetPermanent = game.getPermanent(targetId);\n'
        '                    if (targetPermanent != null) {\n'
        '                        targetRefs.add(incarnationRef(targetPermanent, game));\n'
        '                        continue;\n'
        '                    }\n'
        '                    throw new IllegalStateException("STACK_TARGET_IDENTITY_UNAVAILABLE");\n'
        '                }\n'
        '            }\n'
        '            item.add("target_object_ids", targetRefs);\n'
        '            stack.add(item);\n',
        "actor-entitled stack target identities",
    )

    # Privileged replay state records the provider-neutral stack identity separately
    # from outward opaque handles.
    replace_exact(
        REPLAY,
        'import mage.game.Game;\n',
        'import mage.game.Game;\nimport mage.game.stack.StackObject;\nimport mage.target.Target;\n',
        "replay stack imports",
    )
    replace_exact(
        REPLAY,
        '        state.add("scenario_objects", objects);\n        return state;\n',
        '        state.add("scenario_objects", objects);\n'
        '        JsonArray stack = new JsonArray();\n'
        '        for (StackObject stackObject : game.getStack()) {\n'
        '            JsonObject item = new JsonObject();\n'
        '            item.addProperty("source_semantic_id", scenarioObjectIds.get(stackObject.getSourceId()));\n'
        '            item.addProperty("controller_seat", seat(stackObject.getControllerId()));\n'
        '            JsonArray targets = new JsonArray();\n'
        '            for (Target target : stackObject.getStackAbility().getAllSelectedTargets()) {\n'
        '                for (UUID targetId : target.getTargets()) {\n'
        '                    String semantic = scenarioObjectIds.get(targetId);\n'
        '                    if (semantic == null) throw new IllegalStateException("UNMAPPED_REPLAY_STACK_TARGET");\n'
        '                    targets.add(semantic);\n'
        '                }\n'
        '            }\n'
        '            item.add("targets", targets);\n'
        '            item.addProperty("cast_complete", true);\n'
        '            stack.add(item);\n'
        '        }\n'
        '        state.add("stack", stack);\n'
        '        return state;\n',
        "privileged replay stack projection",
    )

    print("XMAGE_MICRO_STACK_OVERLAY=PASS")


if __name__ == "__main__":
    main()
