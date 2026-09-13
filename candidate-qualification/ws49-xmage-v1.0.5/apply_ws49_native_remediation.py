#!/usr/bin/env python3
"""Apply only freshly source-audited WS-49 XMage/provider construction repairs.

Must run after the inherited WS39 state-surface and WS46 v1.0.4 construction
overlays. No Magic legality or discretionary policy is implemented here.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs46NativeConstructionState.java"
SCENARIO = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs26Scenario.java"
COMMANDER_PROBE = ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageWs39QualificationProbe.java"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"WS49_REMEDIATION_ANCHOR_MISMATCH:{label}:count={count}")
    return text.replace(old, new, 1)


def patch_combat_blocker_defender_scoping() -> None:
    text = NATIVE.read_text(encoding="utf-8")

    # canBlock answers capability, not declaration authority: it does not
    # scope the blocker to the attacked defender, so aggregating it across
    # every non-attacking player lists creatures that defend nothing (a
    # latent primitive gap invisible in real play, where the declaration UI
    # scopes defenders first). Scope eligibility per native combat group:
    # a blocker is eligible only against attackers its own controller
    # defends. No requested data enters this computation.
    old_loop = '''        Set<UUID> nativeAttackers = combat.getAttackers();
        for (Player player : players) {
            if (attackingPlayer != null && player.getId().equals(attackingPlayer.getId())) continue;
            for (Permanent blocker : player.getAvailableBlockers(game)) {
                boolean canBlock = nativeAttackers.isEmpty();
                for (UUID attackerId : nativeAttackers) {
                    if (blocker.canBlock(attackerId, game)) {
                        canBlock = true;
                        break;
                    }
                }
'''
    new_loop = '''        Set<UUID> nativeAttackers = combat.getAttackers();
        for (Player player : players) {
            if (attackingPlayer != null && player.getId().equals(attackingPlayer.getId())) continue;
            for (Permanent blocker : player.getAvailableBlockers(game)) {
                boolean canBlock = nativeAttackers.isEmpty();
                for (UUID attackerId : nativeAttackers) {
                    if (blocker.canBlock(attackerId, game)
                            && defendsAttacker(game, combat, blocker, attackerId)) {
                        canBlock = true;
                        break;
                    }
                }
'''
    text = replace_once(text, old_loop, new_loop, "blocker-defender-scoping")

    anchor = '''        result.addProperty("native_surface", "GameState.Combat/CombatGroup");
        return result;
    }

    private static JsonObject applyExtraTurns(JsonObject scenario, Game game, List<? extends Player> players) {
'''
    helper = '''        result.addProperty("native_surface", "GameState.Combat/CombatGroup");
        return result;
    }

    private static boolean defendsAttacker(
            Game game,
            Combat combat,
            Permanent blocker,
            UUID attackerId
    ) {
        // Declaration authority (CR 509.1a) belongs to the defending player:
        // the blocker must control the attacked player, planeswalker, or
        // battle of at least one group holding this attacker.
        for (CombatGroup group : combat.getGroups()) {
            if (!group.getAttackers().contains(attackerId)) continue;
            UUID defenderId = group.getDefenderId();
            if (defenderId == null) continue;
            if (blocker.getControllerId().equals(defenderId)) return true;
            Permanent defendingPermanent = game.getPermanent(defenderId);
            if (defendingPermanent == null) continue;
            if (defendingPermanent.isBattle(game)) {
                if (blocker.getControllerId().equals(defendingPermanent.getProtectorId())) return true;
            } else if (blocker.getControllerId().equals(defendingPermanent.getControllerId())) {
                return true;
            }
        }
        return false;
    }

    private static JsonObject applyExtraTurns(JsonObject scenario, Game game, List<? extends Player> players) {
'''
    text = replace_once(text, anchor, helper, "defends-attacker-helper")
    NATIVE.write_text(text, encoding="utf-8")


def patch_sick_preserving_battlefield_placement() -> None:
    text = SCENARIO.read_text(encoding="utf-8")

    # game.cheat exercises the native ETB path but unconditionally lifts
    # summoning sickness for every placed permanent, erasing the per-object
    # controlled-since-turn-began state the immutable scenario models. Place
    # battlefield permanents through the same native ETB mechanics minus that
    # single lifting call instead: ETB default is sick, and sickness is then
    # lifted only where modeled (the existing post-hoc WS39 lift stays as a
    # harmless idempotent net). No turn is ever begun before the snapshot
    # (jump model), so installed sickness persists to readback.
    text = replace_once(
        text,
        "import java.util.UUID;\n",
        "import java.util.UUID;\n"
        "import mage.abilities.Ability;\n"
        "import mage.abilities.common.SimpleStaticAbility;\n"
        "import mage.abilities.effects.ContinuousEffect;\n"
        "import mage.abilities.effects.common.InfoEffect;\n"
        "import mage.cards.MeldCard;\n"
        "import mage.game.permanent.PermanentCard;\n"
        "import mage.game.permanent.PermanentMeld;\n"
        "import mage.util.CardUtil;\n"
        "import java.util.Optional;\n",
        "sick-aware-placement-imports",
    )

    old_bind = '''    private static List<PutToBattlefieldInfo> bindBattlefield(
            JsonArray specs,
            Map<String, List<Card>> available,
            Set<UUID> used,
            Map<UUID, String> semanticMap
    ) {
        List<PutToBattlefieldInfo> result = new ArrayList<>();
        for (JsonElement element : specs) {
            JsonObject spec = element.getAsJsonObject();
            Card card = bindOne(spec, available, used);
            semanticMap.put(card.getId(), text(spec, "semantic_id"));
            result.add(new PutToBattlefieldInfo(card, booleanValue(spec, "tapped", false)));
        }
        return result;
    }
'''
    new_bind = '''    record BattlefieldPlacement(
            Card card, boolean tapped, boolean controlledSinceTurnBegan, String semanticId) {
    }

    private static List<BattlefieldPlacement> bindBattlefield(
            JsonArray specs,
            Map<String, List<Card>> available,
            Set<UUID> used,
            Map<UUID, String> semanticMap
    ) {
        List<BattlefieldPlacement> result = new ArrayList<>();
        for (JsonElement element : specs) {
            JsonObject spec = element.getAsJsonObject();
            Card card = bindOne(spec, available, used);
            semanticMap.put(card.getId(), text(spec, "semantic_id"));
            result.add(
                    new BattlefieldPlacement(
                            card,
                            booleanValue(spec, "tapped", false),
                            booleanValue(spec, "controlled_since_turn_began", false),
                            text(spec, "semantic_id")));
        }
        return result;
    }
'''
    text = replace_once(text, old_bind, new_bind, "battlefield-placement-record")

    text = replace_once(
        text,
        """            List<PutToBattlefieldInfo> battlefield = bindBattlefield(
                    optionalArray(zones, "battlefield"), available, used, semanticMap
            );
""",
        """            List<BattlefieldPlacement> battlefield = bindBattlefield(
                    optionalArray(zones, "battlefield"), available, used, semanticMap
            );
""",
        "battlefield-placement-call",
    )

    text = replace_once(
        text,
        "            game.cheat(player.getId(), insertion, hand, battlefield, grave, List.of(), exile);\n",
        "            game.cheat(player.getId(), insertion, hand, List.of(), grave, List.of(), exile);\n"
        "            placeBattlefieldPreservingSickness(game, player, battlefield);\n",
        "battlefield-placement-site",
    )

    anchor = "    private static Card bindOne(JsonObject spec, Map<String, List<Card>> available, Set<UUID> used) {\n"
    method = '''    private static void placeBattlefieldPreservingSickness(
            Game game,
            Player player,
            List<BattlefieldPlacement> placements
    ) {
        // Step-for-step mirror of CardUtil.putCardOntoBattlefieldWithEffects
        // at the locked engine revision, minus its unconditional
        // removeSummoningSickness: ETB default (sick) is the correct
        // installation for scenario-unmodeled sickness, and modeled
        // controlled-since-turn-began is lifted explicitly below.
        Ability fakeSourceAbilityTemplate =
                new SimpleStaticAbility(Zone.OUTSIDE, new InfoEffect("fake ability"));
        fakeSourceAbilityTemplate.setControllerId(player.getId());
        Set<Card> toLoad = new HashSet<>();
        for (BattlefieldPlacement placement : placements) {
            if (placement.card() instanceof PermanentCard) {
                throw fail(
                        "NATIVE_STATE_LOAD_REAL_PERMANENT_CARD:"
                                + placement.semanticId());
            }
            toLoad.add(placement.card());
        }
        game.loadCards(toLoad, player.getId());
        for (BattlefieldPlacement placement : placements) {
            Card newCard = placement.card();
            Ability fakeSourceAbility = fakeSourceAbilityTemplate.copy();
            fakeSourceAbility.setSourceId(newCard.getId());
            Card permCard = CardUtil.getDefaultCardSideForBattlefield(game, newCard);
            permCard.setZone(Zone.BATTLEFIELD, game);
            permCard.setOwnerId(player.getId());
            PermanentCard permanent;
            if (permCard instanceof MeldCard meldCard) {
                permanent = new PermanentMeld(meldCard, player.getId(), game);
            } else {
                permanent = new PermanentCard(permCard, player.getId(), game);
            }
            game.getPermanentsEntering().put(permanent.getId(), permanent);
            permCard.applyEnterWithCounters(permanent, fakeSourceAbility, game);
            permanent.entersBattlefield(fakeSourceAbility, game, Zone.OUTSIDE, false);
            game.addPermanent(permanent, game.getState().getNextPermanentOrderNumber());
            game.getPermanentsEntering().remove(permanent.getId());
            if (placement.tapped()) {
                permanent.setTapped(true);
            }
            if (placement.controlledSinceTurnBegan()) {
                permanent.removeSummoningSickness();
            }
            for (ContinuousEffect effect :
                    game.getState().getContinuousEffects().getLayeredEffects(game)) {
                Optional<Ability> ability = game.getState()
                        .getContinuousEffects()
                        .getLayeredEffectAbilities(effect)
                        .stream()
                        .findFirst();
                if (ability.isPresent() && permanent.getId().equals(ability.get().getSourceId())) {
                    effect.init(ability.get(), game, player.getId());
                }
            }
        }
        game.applyEffects();
    }

'''
    text = replace_once(text, anchor, method + anchor, "battlefield-placement-method")
    SCENARIO.write_text(text, encoding="utf-8")


def patch_native_state() -> None:
    text = NATIVE.read_text(encoding="utf-8")

    # Keep the later source-audited immutable shape. The superseded WS46 fix
    # script must not rename these to resolution_sequence/source_object.
    required = (
        'int sequence = requireInt(spec, "sequence");',
        'String source = requireString(spec, "source");',
        'row.addProperty("sequence", Integer.parseInt(parts[1]));',
        'row.addProperty("source", parts[2]);',
    )
    for token in required:
        if token not in text:
            raise SystemExit(f"WS49_EXTRA_TURN_IMMUTABLE_SHAPE_REGRESSION:{token}")
    forbidden = ('"resolution_sequence"', '"source_object"')
    for token in forbidden:
        if token in text:
            raise SystemExit(f"WS49_EXTRA_TURN_SUPERSEDED_SHAPE_PRESENT:{token}")

    # Bind combat eligibility readback to the exact native attacking Player
    # already selected from immutable temporal state. No heuristic fallback.
    text = replace_once(
        text,
        '        JsonObject readback = readCombat(game, players, semanticMap);\n',
        '        JsonObject readback = readCombat(game, players, semanticMap, attacker);\n',
        "combat-readback-attacker-argument",
    )
    text = replace_once(
        text,
        '    private static JsonObject readCombat(\n'
        '            Game game,\n'
        '            List<? extends Player> players,\n'
        '            Map<UUID, String> semanticMap\n'
        '    ) {\n',
        '    private static JsonObject readCombat(\n'
        '            Game game,\n'
        '            List<? extends Player> players,\n'
        '            Map<UUID, String> semanticMap,\n'
        '            Player attackingPlayer\n'
        '    ) {\n',
        "combat-readback-signature",
    )
    old_fallback = '''        Player attackingPlayer = game.getPlayer(game.getActivePlayerId());
        if (attackingPlayer == null) {
            JsonObject temporalAttacker = new JsonObject();
            // Native temporal state is applied by WS42 immediately after this
            // extension.  For construction legality discovery use Combat's own
            // attacker identity if active-player state is not yet installed.
            for (Player player : players) {
                for (UUID defender : combat.getDefenders()) {
                    if (player.getAvailableAttackers(defender, game).stream().anyMatch(p -> semanticMap.containsKey(p.getId()))) {
                        attackingPlayer = player;
                        break;
                    }
                }
                if (attackingPlayer != null) break;
            }
        }
'''
    text = replace_once(
        text,
        old_fallback,
        '''        // Exact native attacking Player is supplied by applyCombat().
        // No active-player/order/first-match fallback is permitted here.
''',
        "combat-remove-fallback",
    )

    # Immutable v1.0.5 elimination entry uses reason, not condition. Keep the
    # native pre-SBA boundary check (life == 0 and !hasLost()) untouched.
    text = replace_once(
        text,
        '        String condition = requireString(requested, "condition");\n',
        '        String reason = requireString(requested, "reason");\n',
        "elimination-reason-key",
    )
    text = replace_once(
        text,
        '        if (!"life_total_0".equals(condition)) {\n',
        '        if (!"life_total_0".equals(reason)) {\n',
        "elimination-reason-value",
    )
    text = replace_once(
        text,
        '            throw fail("WS46_ELIMINATION_CONDITION_UNSUPPORTED:" + condition);\n',
        '            throw fail("WS49_ELIMINATION_REASON_UNSUPPORTED:" + reason);\n',
        "elimination-reason-error",
    )
    text = replace_once(
        text,
        '        result.addProperty("condition", "life_total_0");\n',
        '        result.addProperty("reason", "life_total_0");\n',
        "elimination-readback-key",
    )

    NATIVE.write_text(text, encoding="utf-8")


def patch_face_down_exile_and_hidden_library_substrate() -> None:
    text = SCENARIO.read_text(encoding="utf-8")

    # The native Card state supports face-down outside battlefield. Permit only
    # the immutable surfaces actually required here: battlefield and exile.
    text = replace_once(
        text,
        '                    if (!"battlefield".equals(zone) && booleanValue(card, "face_down", false)) {\n'
        '                        throw fail("INVALID_SCENARIO: face_down only applies to battlefield");\n'
        '                    }\n',
        '                    if (!Set.of("battlefield", "exile").contains(zone) && booleanValue(card, "face_down", false)) {\n'
        '                        throw fail("INVALID_SCENARIO: face_down only applies to battlefield or exile");\n'
        '                    }\n',
        "face-down-exile-preflight",
    )

    # HIDDEN_10/HIDDEN_11 request knowledge of a top-N library range without
    # assigning semantic identities to those physical cards. NATIVE_STATE_LOAD
    # previously cleared the imported inert deck and retained only semantically
    # named library objects, leaving a zero-card native Library. Keep exactly as
    # many *unbound* imported cards as native substrate as the requested ranges
    # require. These cards never enter semanticMap and therefore cannot become
    # fabricated requested objects. Selection is deterministic by native UUID;
    # it is setup materialization, not a player decision or Magic legality.
    old_insertion = '''            List<Card> insertion = new ArrayList<>(library);
            java.util.Collections.reverse(insertion); // native put-on-top => preserve semantic top-to-bottom
            game.cheat(player.getId(), insertion, hand, battlefield, grave, List.of(), exile);
'''
    new_insertion = '''            int requiredKnowledgeLibrarySize = 0;
            JsonObject knowledge = optionalObject(scenario, "ws42_knowledge_state");
            if (knowledge != null) {
                for (JsonElement viewerElement : optionalArray(knowledge, "viewer_states")) {
                    JsonObject viewerState = viewerElement.getAsJsonObject();
                    for (JsonElement rangeElement : optionalArray(viewerState, "known_library_ranges")) {
                        JsonObject range = rangeElement.getAsJsonObject();
                        if (!("P" + seat).equals(text(range, "player"))) continue;
                        int start = integer(range, "start");
                        int count = integer(range, "count");
                        if (start < 0 || count < 0) {
                            throw fail("WS49_KNOWLEDGE_LIBRARY_RANGE_NEGATIVE:P" + seat + ":" + start + ":" + count);
                        }
                        requiredKnowledgeLibrarySize = Math.max(requiredKnowledgeLibrarySize, Math.addExact(start, count));
                    }
                }
            }
            if (library.size() < requiredKnowledgeLibrarySize) {
                Set<String> commanderNames = new HashSet<>();
                for (JsonElement commanderElement : array(spec, "commander_names")) {
                    commanderNames.add(commanderElement.getAsString());
                }
                List<Card> substrate = new ArrayList<>();
                for (List<Card> cards : available.values()) {
                    for (Card candidate : cards) {
                        if (used.contains(candidate.getId())) continue;
                        if (commanderNames.contains(candidate.getName())) continue;
                        substrate.add(candidate);
                    }
                }
                substrate.sort(Comparator.comparing(card -> card.getId().toString()));
                int needed = requiredKnowledgeLibrarySize - library.size();
                if (substrate.size() < needed) {
                    throw fail("WS49_KNOWLEDGE_LIBRARY_SUBSTRATE_UNAVAILABLE:P" + seat
                            + ":required=" + requiredKnowledgeLibrarySize
                            + ":semantic=" + library.size()
                            + ":available=" + substrate.size());
                }
                for (int index = 0; index < needed; index++) {
                    Card filler = substrate.get(index);
                    used.add(filler.getId());
                    library.add(filler);
                }
            }

            List<Card> insertion = new ArrayList<>(library);
            java.util.Collections.reverse(insertion); // native put-on-top => preserve semantic top-to-bottom
            game.cheat(player.getId(), insertion, hand, battlefield, grave, List.of(), exile);
'''
    text = replace_once(text, old_insertion, new_insertion, "knowledge-library-native-substrate")

    # After native zone placement, set the exact exiled Card state through the
    # XMage Card API, then independently query it in validateZone().
    text = replace_once(
        text,
        '            game.cheat(player.getId(), insertion, hand, battlefield, grave, List.of(), exile);\n',
        '''            game.cheat(player.getId(), insertion, hand, battlefield, grave, List.of(), exile);
            for (JsonElement element : optionalArray(zones, "exile")) {
                JsonObject exileSpec = element.getAsJsonObject();
                if (!booleanValue(exileSpec, "face_down", false)) continue;
                UUID exileId = nativeId(semanticMap, text(exileSpec, "semantic_id"));
                Card exileCard = game.getCard(exileId);
                if (exileCard == null) throw fail("NATIVE_STATE_LOAD_EXILE_CARD_MISSING:" + text(exileSpec, "semantic_id"));
                exileCard.setFaceDown(true, game);
            }
''',
        "face-down-exile-native-apply",
    )

    text = replace_once(
        text,
        '            requireNative(card != null && player.getId().equals(card.getOwnerId()), "owner:" + semantic);\n'
        '            if (expected == Zone.LIBRARY && spec.has("zone_position")) {\n',
        '            requireNative(card != null && player.getId().equals(card.getOwnerId()), "owner:" + semantic);\n'
        '            if (expected == Zone.EXILED) {\n'
        '                requireNative(card.isFaceDown(game) == booleanValue(spec, "face_down", false), "exile-face-down:" + semantic);\n'
        '            }\n'
        '            if (expected == Zone.LIBRARY && spec.has("zone_position")) {\n',
        "face-down-exile-readback",
    )

    SCENARIO.write_text(text, encoding="utf-8")


def patch_eliminated_commander_probe() -> None:
    text = COMMANDER_PROBE.read_text(encoding="utf-8")

    # A construction fixture with elimination_trigger is restored at the
    # pre-SBA boundary (life 0, not yet lost). By the later qualification-state
    # query XMage has correctly executed SBA/CR 800.4 and the eliminated
    # player's commander is no longer a live game Card. The legacy generic
    # commander-cost probe incorrectly required that removed Card to still map.
    # Recognize only the exact configured elimination target after native loss,
    # prove that no live matching commander remains, retain watcher readback,
    # and mark commander-cost probing inapplicable at this post-elimination
    # observation point. Other commander paths remain unchanged and strict.
    old = '''            Player player = currentPlayer(game, sessionPlayers.get(seat - 1));
            Card commander = uniqueCommander(game, player, cardName, semanticId);
            int actual = watcher.getPlaysCount(commander.getMainCard().getId());
            expectedBySeat.merge(seat, expectedInitial, Math::addExact);
            actualBySeat.merge(seat, actual, Math::addExact);

            JsonObject historyRow = new JsonObject();
            historyRow.addProperty("seat", seat);
            historyRow.addProperty("commander_id", semanticId);
            historyRow.addProperty("card_name", cardName);
            historyRow.addProperty("initial_prior_command_zone_cast_count", expectedInitial);
            historyRow.addProperty("live_command_zone_cast_count", actual);
            history.add(historyRow);

            SpellAbility original = commander.getSpellAbility();
'''
    new = '''            Player player = currentPlayer(game, sessionPlayers.get(seat - 1));
            boolean configuredEliminationTarget = false;
            if (configuredScenario.has("ws42_elimination_trigger")
                    && configuredScenario.get("ws42_elimination_trigger").isJsonObject()) {
                JsonObject trigger = configuredScenario.getAsJsonObject("ws42_elimination_trigger");
                String target = trigger.has("player") ? trigger.get("player").getAsString() : "";
                String reason = trigger.has("reason") ? trigger.get("reason").getAsString() : "";
                configuredEliminationTarget = ("P" + seat).equals(target) && "life_total_0".equals(reason);
            }

            if (configuredEliminationTarget && player.hasLost()) {
                for (UUID commanderId : game.getCommandersIds(player, CommanderCardType.ANY, false)) {
                    Card liveCard = game.getCard(commanderId);
                    if (liveCard != null && cardName.equals(liveCard.getName())) {
                        throw new IllegalStateException(
                                "WS49_ELIMINATED_COMMANDER_STILL_LIVE:" + semanticId + ":" + commanderId
                        );
                    }
                }
                int actual = watcher.getPlayerCount(player.getId());
                expectedBySeat.merge(seat, expectedInitial, Math::addExact);
                actualBySeat.merge(seat, actual, Math::addExact);

                JsonObject historyRow = new JsonObject();
                historyRow.addProperty("seat", seat);
                historyRow.addProperty("commander_id", semanticId);
                historyRow.addProperty("card_name", cardName);
                historyRow.addProperty("initial_prior_command_zone_cast_count", expectedInitial);
                historyRow.addProperty("live_command_zone_cast_count", actual);
                historyRow.addProperty("native_player_lost", true);
                historyRow.addProperty("native_commander_absent_after_elimination", true);
                history.add(historyRow);

                JsonObject costRow = new JsonObject();
                costRow.addProperty("seat", seat);
                costRow.addProperty("commander_id", semanticId);
                costRow.addProperty("card_name", cardName);
                costRow.addProperty("native_commander_absent_after_elimination", true);
                costRow.addProperty("commander_cost_probe_applicable", false);
                costRow.addProperty("native_surface", "Player.hasLost + Game.getCommandersIds/Game.getCard");
                costs.add(costRow);
                continue;
            }

            Card commander = uniqueCommander(game, player, cardName, semanticId);
            int actual = watcher.getPlaysCount(commander.getMainCard().getId());
            expectedBySeat.merge(seat, expectedInitial, Math::addExact);
            actualBySeat.merge(seat, actual, Math::addExact);

            JsonObject historyRow = new JsonObject();
            historyRow.addProperty("seat", seat);
            historyRow.addProperty("commander_id", semanticId);
            historyRow.addProperty("card_name", cardName);
            historyRow.addProperty("initial_prior_command_zone_cast_count", expectedInitial);
            historyRow.addProperty("live_command_zone_cast_count", actual);
            history.add(historyRow);

            SpellAbility original = commander.getSpellAbility();
'''
    text = replace_once(text, old, new, "eliminated-commander-post-sba-probe")
    COMMANDER_PROBE.write_text(text, encoding="utf-8")


def main() -> int:
    patch_native_state()
    patch_combat_blocker_defender_scoping()
    patch_face_down_exile_and_hidden_library_substrate()
    patch_eliminated_commander_probe()
    patch_sick_preserving_battlefield_placement()
    print("WS49_NATIVE_REMEDIATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
