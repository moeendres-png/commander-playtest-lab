// SPDX-License-Identifier: GPL-3.0-or-later
package forge.game.player;

import forge.CardStorageReader;
import forge.card.CardRarity;
import forge.card.CardRules;
import forge.card.MagicColor;
import forge.game.Game;
import forge.game.GameEntity;
import forge.game.ability.effects.FlipCoinEffect;
import forge.game.card.Card;
import forge.game.mana.Mana;
import forge.game.phase.PhaseType;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;
import forge.item.PaperCard;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/** GPL-side Gate-D extension layered over the already-qualified WS-23 authority helper. */
public final class Ws23ForgeGateD {
    private static int boltId = -1;
    private static int fogId = -1;
    private static int commanderId = -1;
    private static int attackerId = -1;
    private static int blockerId = -1;
    private static int warden1Id = -1;
    private static int warden2Id = -1;
    private static int baselineLife = -1;

    private static boolean boltChosen = false;
    private static boolean commanderChosen = false;
    private static boolean commanderChosenFromCommand = false;
    private static boolean fogChosen = false;
    private static boolean fogChosenFromHand = false;
    private static boolean fogManaInjected = false;
    private static boolean commanderProofEmitted = false;
    private static boolean triggerOrderExecuted = false;
    private static boolean triggerProofEmitted = false;
    private static boolean preventionProofEmitted = false;

    private Ws23ForgeGateD() {}

    private static String q(String value) {
        return Ws23ForgeVerticalProvider.esc(value);
    }

    private static String cardRef(Card card) {
        return "card:" + card.getId();
    }

    private static String playerRef(Player player) {
        return "player:" + player.getName();
    }

    private static boolean identityVisible(Card card, Player viewer) {
        return card.getView().canBeShownTo(viewer.getView())
                && card.getView().canFaceDownBeShownTo(viewer.getView());
    }

    private static Card findCard(Game game, int id, ZoneType zone) {
        for (Card card : game.getCardsIn(zone)) {
            if (card.getId() == id) {
                return card;
            }
        }
        return null;
    }

    private static Card findNamed(Iterable<Card> cards, String name) {
        for (Card card : cards) {
            if (name.equals(card.getName())) {
                return card;
            }
        }
        throw new IllegalStateException("WS23_GATE_D_CARD_NOT_FOUND:" + name);
    }

    private static CardStorageReader lazyRulesReader() {
        String languagesDirectory = System.getenv("COMMANDER_LAB_FORGE_LANG_DIR");
        if (languagesDirectory == null || languagesDirectory.isBlank()) {
            throw new IllegalStateException("COMMANDER_LAB_FORGE_LANG_DIR is required");
        }
        Path languages = Path.of(languagesDirectory).toAbsolutePath().normalize();
        Path root = languages.getParent().getParent().getParent();
        return new CardStorageReader(root.resolve("forge-gui/res/cardsfolder").toString(), null, true);
    }

    private static Card loadActualCard(
            Game game, Player owner, String name, String edition, CardRarity rarity) {
        CardRules rules = lazyRulesReader().attemptToLoadCard(name);
        if (rules == null) {
            throw new IllegalStateException("WS23_RULES_CARD_NOT_FOUND:" + name);
        }
        Card card = Card.fromPaperCard(new PaperCard(rules, edition, rarity), owner);
        if (card == null || !name.equals(card.getName())) {
            throw new IllegalStateException("WS23_RULES_CARD_LOAD_MISMATCH:" + name);
        }
        return card;
    }

    private static Card syntheticCard(Game game, Player owner, String name, ZoneType zone) {
        Card card = new Card(game.nextCardId(), game);
        card.setName(name);
        card.setOwner(owner);
        card.setController(owner, game.getNextTimestamp());
        owner.getZone(zone).add(card);
        return card;
    }

    private static void runRngProof(Game game, Ws23ForgeVerticalProvider.Broker broker) {
        Player seat1 = game.getPlayers().get(0);
        Card host = new Card(game.nextCardId(), game);
        host.setName("WS23_FORGE_RNG_HOST");
        host.setOwner(seat1);
        host.setController(seat1, game.getNextTimestamp());
        SpellAbility.EmptySa ability = new SpellAbility.EmptySa(host, seat1);
        ability.putParam("NoCall", "True");

        StringBuilder sequence = new StringBuilder();
        for (int i = 0; i < 16; i++) {
            int heads = FlipCoinEffect.flipCoins(seat1, ability, 1);
            if (heads != 0 && heads != 1) {
                throw new IllegalStateException("WS23_RNG_FLIP_NON_BOOLEAN_RESULT:" + heads);
            }
            sequence.append(heads == 1 ? 'H' : 'T');
        }
        broker.out.println("{\"protocol\":" + q(Ws23ForgeVerticalProvider.PROTOCOL)
                + ",\"message_type\":\"RNG_PROOF\",\"request_id\":\"ws23-rng-proof\""
                + ",\"session_id\":" + q(Ws23ForgeVerticalProvider.SESSION_ID)
                + ",\"payload\":{\"common_fixture_id\":\"RNG_RULES_TAPE\""
                + ",\"engine_path\":\"FlipCoinEffect/MyRandom\""
                + ",\"seed\":" + Ws23ForgeBootstrap.QUALIFICATION_SEED
                + ",\"flip_count\":16"
                + ",\"sequence\":" + q(sequence.toString()) + "}}");
        broker.out.flush();
    }

    static void installScenario(Game game, Ws23ForgeVerticalProvider.Broker broker) {
        Ws23ForgeAuthority.installScenario(game, broker);

        Player seat1 = game.getPlayers().get(0);
        Player seat2 = game.getPlayers().get(1);
        Card bolt = findNamed(seat1.getCardsIn(ZoneType.Hand), "Lightning Bolt");
        Card commander = findNamed(seat1.getCardsIn(ZoneType.Command), "Rograkh, Son of Rohgahh");
        Card attacker = findNamed(seat1.getCardsIn(ZoneType.Battlefield), "Grizzly Bears");
        Card blocker = findNamed(seat2.getCardsIn(ZoneType.Battlefield), "Grizzly Bears");
        boltId = bolt.getId();
        commanderId = commander.getId();
        attackerId = attacker.getId();
        blockerId = blocker.getId();

        Card fog = loadActualCard(game, seat1, "Fog", "M10", CardRarity.Common);
        seat1.getZone(ZoneType.Hand).add(fog);
        fogId = fog.getId();

        Card warden1 = loadActualCard(game, seat1, "Soul Warden", "M10", CardRarity.Common);
        seat1.getZone(ZoneType.Battlefield).add(warden1);
        warden1.setController(seat1, game.getNextTimestamp());
        warden1.setSickness(true);
        game.getTriggerHandler().registerActiveTrigger(warden1, true);
        warden1Id = warden1.getId();

        Card warden2 = loadActualCard(game, seat1, "Soul Warden", "M10", CardRarity.Common);
        seat1.getZone(ZoneType.Battlefield).add(warden2);
        warden2.setController(seat1, game.getNextTimestamp());
        warden2.setSickness(true);
        game.getTriggerHandler().registerActiveTrigger(warden2, true);
        warden2Id = warden2.getId();
        baselineLife = seat1.getLife();

        runRngProof(game, broker);
        broker.out.println("{\"protocol\":" + q(Ws23ForgeVerticalProvider.PROTOCOL)
                + ",\"message_type\":\"SCENARIO_READY\",\"request_id\":\"ws23-gate-d-scenario\""
                + ",\"session_id\":" + q(Ws23ForgeVerticalProvider.SESSION_ID)
                + ",\"payload\":{\"bolt_ref\":" + q(cardRef(bolt))
                + ",\"fog_ref\":" + q(cardRef(fog))
                + ",\"attacker_ref\":" + q(cardRef(attacker))
                + ",\"blocker_ref\":" + q(cardRef(blocker))
                + ",\"commander_ref\":" + q(cardRef(commander))
                + ",\"target_player_ref\":" + q(playerRef(seat2)) + "}}");
        broker.out.flush();
    }

    private static void emitStackProof(Game game, Ws23ForgeVerticalProvider.Broker broker) {
        Card bolt = findCard(game, boltId, ZoneType.Stack);
        if (bolt == null) {
            throw new IllegalStateException("WS23_BOLT_NOT_ON_STACK_AFTER_NATIVE_PLAY");
        }
        Player seat1 = game.getPlayers().get(0);
        Player seat2 = game.getPlayers().get(1);
        if (!identityVisible(bolt, seat1) || !identityVisible(bolt, seat2)) {
            throw new IllegalStateException("WS23_PUBLIC_STACK_OBSERVATION_FAILED");
        }
        broker.out.println("{\"protocol\":" + q(Ws23ForgeVerticalProvider.PROTOCOL)
                + ",\"message_type\":\"STACK_OBSERVATION_PROOF\",\"request_id\":\"ws23-stack-proof-gate-d\""
                + ",\"session_id\":" + q(Ws23ForgeVerticalProvider.SESSION_ID)
                + ",\"payload\":{\"public_stack_identity_visible\":true}}");
        broker.out.flush();
    }

    private static void maybeCommanderProof(Game game, Ws23ForgeVerticalProvider.Broker broker) {
        if (!commanderChosen || commanderProofEmitted) {
            return;
        }
        Card commander = findCard(game, commanderId, ZoneType.Battlefield);
        if (commander == null) {
            return;
        }
        int castCount = game.getPlayers().get(0).getCommanderCast(commander);
        if (!commanderChosenFromCommand || !commander.isCommander() || castCount != 1) {
            throw new IllegalStateException("WS23_COMMANDER_CAST_RUNTIME_INVARIANT_FAILED");
        }
        commanderProofEmitted = true;
        broker.out.println("{\"protocol\":" + q(Ws23ForgeVerticalProvider.PROTOCOL)
                + ",\"message_type\":\"COMMANDER_PROOF\",\"request_id\":\"ws23-commander-cast-proof\""
                + ",\"session_id\":" + q(Ws23ForgeVerticalProvider.SESSION_ID)
                + ",\"payload\":{\"card_identity\":\"Rograkh, Son of Rohgahh\""
                + ",\"actual_card_fixture_id\":\"CARD_02\""
                + ",\"common_fixture_id\":\"WS05-CMD-ZONE-HAND-YES\""
                + ",\"native_commander_replacement_applied\":true"
                + ",\"cast_from_command_runtime_verified\":true"
                + ",\"commander_cast_count\":1"
                + ",\"actual_card_behavior_verified\":true}}");
        broker.out.flush();
    }

    private static void maybeTriggerProof(Game game, Ws23ForgeVerticalProvider.Broker broker) {
        if (!triggerOrderExecuted || triggerProofEmitted || !game.getStack().isEmpty()) {
            return;
        }
        Player seat1 = game.getPlayers().get(0);
        int lifeGain = seat1.getLife() - baselineLife;
        if (lifeGain != 2) {
            return;
        }
        Card warden1 = findCard(game, warden1Id, ZoneType.Battlefield);
        Card warden2 = findCard(game, warden2Id, ZoneType.Battlefield);
        if (warden1 == null || warden2 == null) {
            throw new IllegalStateException("WS23_SOUL_WARDEN_TRIGGER_SOURCE_MISSING");
        }
        if (game.getPhaseHandler().getPhase() != PhaseType.MAIN1) {
            throw new IllegalStateException("WS23_TRIGGER_PROOF_NOT_IN_PRECOMBAT_MAIN");
        }
        triggerProofEmitted = true;
        broker.out.println("{\"protocol\":" + q(Ws23ForgeVerticalProvider.PROTOCOL)
                + ",\"message_type\":\"TRIGGER_PROOF\",\"request_id\":\"ws23-trigger-proof\""
                + ",\"session_id\":" + q(Ws23ForgeVerticalProvider.SESSION_ID)
                + ",\"payload\":{\"common_fixture_id\":\"PILOT_TRIGGER_ORDER\""
                + ",\"source_identity\":\"Soul Warden\""
                + ",\"ordered_trigger_count\":2"
                + ",\"life_gain_after_resolution\":2"
                + ",\"native_trigger_resolution_verified\":true}}");
        broker.out.flush();

        seat1.getZone(ZoneType.Battlefield).remove(warden1);
        seat1.getZone(ZoneType.Battlefield).remove(warden2);
        Card greenSource = syntheticCard(
                game, seat1, "WS23_PUBLIC_GREEN_MANA_SOURCE", ZoneType.Battlefield);
        seat1.getManaPool().addMana(new Mana(MagicColor.GREEN, greenSource, null, seat1));
        fogManaInjected = true;
        broker.recordAutomatic("fogManaFixture:POST_TRIGGER_MAIN1");
    }

    private static void emitPreventionProof(Game game, Ws23ForgeVerticalProvider.Broker broker) {
        if (preventionProofEmitted) {
            return;
        }
        if (!fogChosen
                || !fogChosenFromHand
                || !fogManaInjected
                || !commanderProofEmitted
                || !triggerProofEmitted) {
            throw new IllegalStateException("WS23_POST_COMBAT_REACHED_BEFORE_REQUIRED_GATE_D_ACTIONS");
        }
        Card attacker = findCard(game, attackerId, ZoneType.Battlefield);
        Card blocker = findCard(game, blockerId, ZoneType.Battlefield);
        Card fog = findCard(game, fogId, ZoneType.Graveyard);
        if (attacker == null || blocker == null || fog == null) {
            throw new IllegalStateException("WS23_FOG_PREVENTION_ZONE_INVARIANT_FAILED");
        }
        if (attacker.getDamage() != 0 || blocker.getDamage() != 0) {
            throw new IllegalStateException("WS23_FOG_DID_NOT_PREVENT_COMBAT_DAMAGE");
        }
        preventionProofEmitted = true;
        broker.out.println("{\"protocol\":" + q(Ws23ForgeVerticalProvider.PROTOCOL)
                + ",\"message_type\":\"PREVENTION_PROOF\",\"request_id\":\"ws23-prevention-proof\""
                + ",\"session_id\":" + q(Ws23ForgeVerticalProvider.SESSION_ID)
                + ",\"payload\":{\"common_fixture_id\":\"MICRO_PREVENTION\""
                + ",\"card_identity\":\"Fog\""
                + ",\"fog_resolved_to_graveyard\":true"
                + ",\"attacker_survived\":true"
                + ",\"blocker_survived\":true"
                + ",\"attacker_damage\":0"
                + ",\"blocker_damage\":0"
                + ",\"native_prevention_verified\":true}}");
        broker.out.flush();
    }

    static List<SpellAbility> choosePriority(
            Ws23ForgeVerticalProvider.Broker broker, Player actor, Game game) {
        maybeCommanderProof(game, broker);
        maybeTriggerProof(game, broker);
        if (game.getPhaseHandler().getPhase() == PhaseType.MAIN2) {
            emitPreventionProof(game, broker);
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS23_GATE_D_POST_COMBAT_MAIN2");
        }

        broker.priorityDecisions++;
        if (broker.priorityDecisions > broker.stopAfterPriorityDecisions) {
            throw new Ws23ForgeVerticalProvider.ControlledStop(
                    "WS23_CONTROLLED_AFTER_PRIORITY_" + broker.stopAfterPriorityDecisions);
        }

        LinkedHashSet<Card> candidates = new LinkedHashSet<>();
        candidates.addAll(actor.getAllCards());
        candidates.addAll(actor.getCardsActivatableInExternalZones(true));
        List<SpellAbility> nativeOptions = new ArrayList<>();
        List<String> labels = new ArrayList<>();
        List<String> refs = new ArrayList<>();
        labels.add("PASS");
        refs.add("pass");
        Set<SpellAbility> seen = Collections.newSetFromMap(new IdentityHashMap<>());
        for (Card card : candidates) {
            int abilityIndex = 0;
            for (SpellAbility ability : card.getAllPossibleAbilities(actor, true)) {
                if (seen.add(ability)) {
                    nativeOptions.add(ability);
                    labels.add("FORGE_LEGAL_ACTION");
                    refs.add("action:" + card.getId() + ":" + abilityIndex);
                }
                abilityIndex++;
            }
        }

        String choice = broker.chooseRefs("priority", actor, labels, refs);
        int index = Integer.parseInt(choice.substring(1));
        if (index == 0) {
            return List.of();
        }
        SpellAbility selected = nativeOptions.get(index - 1);
        if (!selected.canPlay(true)) {
            throw new Ws23ForgeVerticalProvider.ControlledStop(
                    "WS23_FORGE_REJECTED_OFFERED_PRIORITY_ACTION");
        }
        int hostId = selected.getHostCard().getId();
        if (hostId == boltId) {
            boltChosen = true;
        } else if (hostId == commanderId) {
            commanderChosen = true;
            commanderChosenFromCommand = selected.getHostCard().isInZone(ZoneType.Command);
        } else if (hostId == fogId) {
            fogChosen = true;
            fogChosenFromHand = selected.getHostCard().isInZone(ZoneType.Hand);
        }
        return List.of(selected);
    }

    static boolean playChosenSpellAbility(
            PlayerController controller,
            Ws23ForgeVerticalProvider.Broker broker,
            Player actor,
            SpellAbility ability,
            Game game) {
        boolean isBolt = ability.getHostCard().getId() == boltId;
        boolean played = PlaySpellAbility.playSpellAbility(controller, actor, ability);
        if (played && isBolt && boltChosen) {
            emitStackProof(game, broker);
        }
        return played;
    }

    static List<SpellAbility> orderSimultaneous(
            Ws23ForgeVerticalProvider.Broker broker,
            Player actor,
            List<SpellAbility> activePlayerSAs) {
        if (activePlayerSAs == null || activePlayerSAs.size() <= 1) {
            broker.recordAutomatic("orderSimultaneousSa:ZERO_OR_ONE");
            return activePlayerSAs;
        }
        if (activePlayerSAs.size() != 2) {
            throw new UnsupportedOperationException(
                    "WS23_FAIL_CLOSED_UNSUPPORTED:orderSimultaneousSa:MORE_THAN_TWO");
        }
        for (SpellAbility ability : activePlayerSAs) {
            if (!ability.isTrigger()
                    || ability.isCopied()
                    || !"Soul Warden".equals(ability.getHostCard().getName())) {
                throw new UnsupportedOperationException(
                        "WS23_FAIL_CLOSED_UNSUPPORTED:orderSimultaneousSa:UNEXPECTED_TRIGGER_PAIR");
            }
        }
        String choice = broker.chooseRefs(
                "orderSimultaneousSa",
                actor,
                List.of("ORDER", "ORDER"),
                List.of("order:0,1", "order:1,0"));
        triggerOrderExecuted = true;
        if ("o0".equals(choice)) {
            return List.of(activePlayerSAs.get(0), activePlayerSAs.get(1));
        }
        return List.of(activePlayerSAs.get(1), activePlayerSAs.get(0));
    }

    static void orderAndPlaySimultaneous(
            PlayerController controller,
            Ws23ForgeVerticalProvider.Broker broker,
            Player actor,
            List<SpellAbility> activePlayerSAs) {
        if (activePlayerSAs == null || activePlayerSAs.isEmpty()) {
            broker.recordAutomatic("orderAndPlaySimultaneousSa:EMPTY");
            return;
        }
        List<SpellAbility> ordered = orderSimultaneous(broker, actor, activePlayerSAs);
        for (int i = ordered.size() - 1; i >= 0; i--) {
            SpellAbility next = ordered.get(i);
            if (!next.isTrigger() || next.isCopied()) {
                throw new UnsupportedOperationException(
                        "WS23_FAIL_CLOSED_UNSUPPORTED:orderAndPlaySimultaneousSa:NON_NATIVE_TRIGGER");
            }
            if (!PlaySpellAbility.playSpellAbility(controller, actor, next)) {
                throw new Ws23ForgeVerticalProvider.ControlledStop(
                        "WS23_FORGE_TRIGGER_STACK_ORCHESTRATION_REJECTED");
            }
        }
        broker.recordAutomatic("orderAndPlaySimultaneousSa:FORGE_CORE_TRIGGER_STACK");
    }
}
