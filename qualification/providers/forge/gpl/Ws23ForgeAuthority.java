// SPDX-License-Identifier: GPL-3.0-or-later
package forge.game.player;

import forge.CardStorageReader;
import forge.card.CardRarity;
import forge.card.CardRules;
import forge.card.MagicColor;
import forge.card.mana.ManaCost;
import forge.game.Game;
import forge.game.GameEntity;
import forge.game.GameObject;
import forge.game.card.Card;
import forge.game.card.CardCollection;
import forge.game.combat.Combat;
import forge.game.combat.CombatUtil;
import forge.game.cost.CostPartMana;
import forge.game.mana.Mana;
import forge.game.mana.ManaConversionMatrix;
import forge.game.mana.ManaCostBeingPaid;
import forge.game.replacement.ReplacementEffect;
import forge.game.spellability.SpellAbility;
import forge.game.spellability.TargetRestrictions;
import forge.game.zone.ZoneType;
import forge.item.PaperCard;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * GPL-side WS-23 vertical-slice authority adapter.
 *
 * <p>This class may inspect Forge-native objects because it runs inside the isolated Forge JVM. It never
 * exports Forge class layouts. Every externally offered choice is produced from Forge-owned candidate or
 * validation APIs and represented by opaque WS-10R option IDs plus independent public object refs.</p>
 */
public final class Ws23ForgeAuthority {
    private static int scenarioBoltId = -1;
    private static int scenarioAttackerId = -1;
    private static int scenarioBlockerId = -1;
    private static boolean scenarioActionChosen = false;

    private Ws23ForgeAuthority() {}

    private static String q(String s) {
        return Ws23ForgeVerticalProvider.esc(s);
    }

    private static String playerRef(Player player) {
        return "player:" + player.getName();
    }

    private static String cardRef(Card card) {
        return "card:" + card.getId();
    }

    private static boolean identityVisible(Card card, Player viewer) {
        return card.getView().canBeShownTo(viewer.getView())
                && card.getView().canFaceDownBeShownTo(viewer.getView());
    }

    private static Card syntheticCard(Game game, Player owner, String name, ZoneType zone) {
        Card card = new Card(game.nextCardId(), game);
        card.setName(name);
        card.setOwner(owner);
        card.setController(owner, game.getNextTimestamp());
        owner.getZone(zone).add(card);
        return card;
    }

    private static CardStorageReader lazyRulesReader() {
        String languagesDirectory = System.getenv("COMMANDER_LAB_FORGE_LANG_DIR");
        if (languagesDirectory == null || languagesDirectory.isBlank()) {
            throw new IllegalStateException("COMMANDER_LAB_FORGE_LANG_DIR is required");
        }
        Path languages = Path.of(languagesDirectory).toAbsolutePath().normalize();
        Path root = languages.getParent().getParent().getParent();
        Path cards = root.resolve("forge-gui/res/cardsfolder");
        return new CardStorageReader(cards.toString(), null, true);
    }

    private static Card loadActualCard(Game game, Player owner, String name, String edition, CardRarity rarity) {
        CardRules rules = lazyRulesReader().attemptToLoadCard(name);
        if (rules == null) {
            throw new IllegalStateException("WS23_RULES_CARD_NOT_FOUND:" + name);
        }
        PaperCard paper = new PaperCard(rules, edition, rarity);
        Card card = Card.fromPaperCard(paper, owner);
        if (card == null || !name.equals(card.getName())) {
            throw new IllegalStateException("WS23_RULES_CARD_LOAD_MISMATCH:" + name);
        }
        return card;
    }

    private static String visibleHand(Player owner, Player viewer) {
        StringBuilder sb = new StringBuilder();
        sb.append("{\"owner_id\":").append(q(owner.getName()))
                .append(",\"count\":").append(owner.getCardsIn(ZoneType.Hand).size())
                .append(",\"visible_cards\":[");
        boolean first = true;
        for (Card card : owner.getCardsIn(ZoneType.Hand)) {
            if (!identityVisible(card, viewer)) {
                continue;
            }
            if (!first) sb.append(',');
            first = false;
            sb.append("{\"object_id\":").append(q(cardRef(card)))
                    .append(",\"name\":").append(q(card.getName())).append('}');
        }
        return sb.append("]}").toString();
    }

    private static String battlefield(Player viewer, Game game) {
        StringBuilder sb = new StringBuilder("[");
        boolean first = true;
        for (Card card : game.getCardsIn(ZoneType.Battlefield)) {
            if (!first) sb.append(',');
            first = false;
            boolean visible = identityVisible(card, viewer);
            sb.append("{\"object_id\":").append(q(cardRef(card)))
                    .append(",\"face_down\":").append(card.isFaceDown());
            if (visible) {
                sb.append(",\"name\":").append(q(card.getName()));
            }
            sb.append('}');
        }
        return sb.append(']').toString();
    }

    private static String observation(Player viewer, Game game) {
        StringBuilder hands = new StringBuilder("[");
        int i = 0;
        for (Player owner : game.getPlayers()) {
            if (i++ > 0) hands.append(',');
            hands.append(visibleHand(owner, viewer));
        }
        hands.append(']');

        StringBuilder libraries = new StringBuilder("[");
        i = 0;
        for (Player owner : game.getPlayers()) {
            if (i++ > 0) libraries.append(',');
            libraries.append("{\"owner_id\":").append(q(owner.getName()))
                    .append(",\"count\":").append(owner.getCardsIn(ZoneType.Library).size()).append('}');
        }
        libraries.append(']');

        return "{\"actor_id\":" + q(viewer.getName())
                + ",\"hands\":" + hands
                + ",\"battlefield\":" + battlefield(viewer, game)
                + ",\"libraries\":" + libraries
                + ",\"stack_count\":" + game.getStack().size() + "}";
    }

    private static void runHoneycardProof(Game game, Ws23ForgeVerticalProvider.Broker broker) {
        Player seat1 = game.getPlayers().get(0);
        Player seat2 = game.getPlayers().get(1);

        String ownName = "WS23_HONEY_OWN_HAND_7B3D";
        String oppName = "WS23_HONEY_OPP_HAND_A91C";
        String publicName = "WS23_HONEY_PUBLIC_BATTLEFIELD_44E2";
        String facedownName = "WS23_HONEY_FACEDOWN_126F";
        String libraryName = "WS23_HONEY_LIBRARY_88D0";

        Card ownHand = syntheticCard(game, seat1, ownName, ZoneType.Hand);
        Card oppHand = syntheticCard(game, seat2, oppName, ZoneType.Hand);
        Card publicBattlefield = syntheticCard(game, seat2, publicName, ZoneType.Battlefield);
        Card facedown = syntheticCard(game, seat2, facedownName, ZoneType.Battlefield);
        if (!facedown.turnFaceDown()) {
            throw new IllegalStateException("WS23_HONEY_FACEDOWN_SETUP_FAILED");
        }
        Card library = syntheticCard(game, seat2, libraryName, ZoneType.Library);

        String seat1Obs = observation(seat1, game);
        String seat2Obs = observation(seat2, game);
        boolean ownVisible = seat1Obs.contains(ownName);
        boolean opponentHidden = !seat1Obs.contains(oppName);
        boolean opponentOwnVisible = seat2Obs.contains(oppName);
        boolean publicVisible = seat1Obs.contains(publicName) && seat2Obs.contains(publicName);
        boolean facedownHidden = !seat1Obs.contains(facedownName);
        boolean libraryHidden = !seat1Obs.contains(libraryName) && !seat2Obs.contains(libraryName);

        if (!(ownVisible && opponentHidden && opponentOwnVisible && publicVisible && facedownHidden && libraryHidden)) {
            throw new IllegalStateException("WS23_HONEY_OBSERVATION_LEAK_OR_OMISSION");
        }

        broker.out.println("{\"protocol\":" + q(Ws23ForgeVerticalProvider.PROTOCOL)
                + ",\"message_type\":\"OBSERVATION_PROOF\",\"request_id\":\"ws23-observation-proof\""
                + ",\"session_id\":" + q(Ws23ForgeVerticalProvider.SESSION_ID)
                + ",\"payload\":{\"own_hand_identity_visible\":true"
                + ",\"opponent_hand_identity_hidden\":true"
                + ",\"opponent_own_hand_identity_visible\":true"
                + ",\"public_battlefield_visible\":true"
                + ",\"facedown_identity_hidden\":true"
                + ",\"library_identity_hidden\":true"
                + ",\"seat1_observation\":" + seat1Obs
                + ",\"seat2_observation\":" + seat2Obs + "}}");
        broker.out.flush();

        seat1.getZone(ZoneType.Hand).remove(ownHand);
        seat2.getZone(ZoneType.Hand).remove(oppHand);
        seat2.getZone(ZoneType.Battlefield).remove(publicBattlefield);
        seat2.getZone(ZoneType.Battlefield).remove(facedown);
        seat2.getZone(ZoneType.Library).remove(library);
    }

    /** Called by the real Match.startGame start hook after mulligans and before the first priority loop. */
    static void installScenario(Game game, Ws23ForgeVerticalProvider.Broker broker) {
        runHoneycardProof(game, broker);

        Player seat1 = game.getPlayers().get(0);
        Player seat2 = game.getPlayers().get(1);

        Card bolt = loadActualCard(game, seat1, "Lightning Bolt", "M10", CardRarity.Common);
        seat1.getZone(ZoneType.Hand).add(bolt);
        scenarioBoltId = bolt.getId();

        Card manaSource = syntheticCard(game, seat1, "WS23_PUBLIC_MANA_SOURCE", ZoneType.Battlefield);
        seat1.getManaPool().addMana(new Mana(MagicColor.RED, manaSource, null, seat1));

        Card attacker = loadActualCard(game, seat1, "Grizzly Bears", "10E", CardRarity.Common);
        seat1.getZone(ZoneType.Battlefield).add(attacker);
        attacker.setSickness(false);
        scenarioAttackerId = attacker.getId();

        Card blocker = loadActualCard(game, seat2, "Grizzly Bears", "10E", CardRarity.Common);
        seat2.getZone(ZoneType.Battlefield).add(blocker);
        blocker.setSickness(false);
        scenarioBlockerId = blocker.getId();

        broker.out.println("{\"protocol\":" + q(Ws23ForgeVerticalProvider.PROTOCOL)
                + ",\"message_type\":\"SCENARIO_READY\",\"request_id\":\"ws23-scenario\""
                + ",\"session_id\":" + q(Ws23ForgeVerticalProvider.SESSION_ID)
                + ",\"payload\":{\"bolt_ref\":" + q(cardRef(bolt))
                + ",\"attacker_ref\":" + q(cardRef(attacker))
                + ",\"blocker_ref\":" + q(cardRef(blocker))
                + ",\"target_player_ref\":" + q(playerRef(seat2)) + "}}");
        broker.out.flush();
    }

    static List<SpellAbility> choosePriority(
            Ws23ForgeVerticalProvider.Broker broker, Player actor, Game game) {
        broker.priorityDecisions++;
        if (broker.priorityDecisions > broker.stopAfterPriorityDecisions) {
            throw new Ws23ForgeVerticalProvider.ControlledStop(
                    "WS23_CONTROLLED_AFTER_PRIORITY_" + broker.stopAfterPriorityDecisions);
        }

        LinkedHashSet<Card> candidateCards = new LinkedHashSet<>();
        candidateCards.addAll(actor.getAllCards());
        candidateCards.addAll(actor.getCardsActivatableInExternalZones(true));

        List<SpellAbility> nativeOptions = new ArrayList<>();
        List<String> labels = new ArrayList<>();
        List<String> refs = new ArrayList<>();
        labels.add("PASS");
        refs.add("pass");
        Set<SpellAbility> seen = Collections.newSetFromMap(new IdentityHashMap<>());
        for (Card card : candidateCards) {
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
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS23_FORGE_REJECTED_OFFERED_PRIORITY_ACTION");
        }
        if (selected.getHostCard().getId() == scenarioBoltId) {
            scenarioActionChosen = true;
        }
        return List.of(selected);
    }

    static boolean chooseTargets(
            Ws23ForgeVerticalProvider.Broker broker, Player actor, SpellAbility ability) {
        TargetRestrictions restrictions = ability.getTargetRestrictions();
        if (restrictions == null) {
            broker.recordAutomatic("chooseTargetsFor:NO_TARGET_RESTRICTIONS");
            return true;
        }
        Card host = ability.getHostCard();
        int min = restrictions.getMinTargets(host, ability);
        int max = restrictions.getMaxTargets(host, ability);
        if (min != 1 || max != 1 || !ability.getTargets().isEmpty()) {
            throw new UnsupportedOperationException("WS23_FAIL_CLOSED_UNSUPPORTED:chooseTargetsFor:NON_SINGLE_TARGET");
        }

        List<GameEntity> candidates = restrictions.getAllCandidates(ability);
        if (candidates.isEmpty()) {
            return false;
        }
        List<String> labels = new ArrayList<>();
        List<String> refs = new ArrayList<>();
        for (GameEntity candidate : candidates) {
            if (!ability.canTarget(candidate)) {
                continue;
            }
            if (candidate instanceof Card card && !identityVisible(card, actor)) {
                throw new UnsupportedOperationException("WS23_FAIL_CLOSED_UNSUPPORTED:chooseTargetsFor:HIDDEN_TARGET");
            }
            labels.add("NATIVE_TARGET");
            if (candidate instanceof Player p) {
                refs.add(playerRef(p));
            } else if (candidate instanceof Card card) {
                refs.add(cardRef(card));
            } else {
                refs.add("entity:" + candidate.getId());
            }
        }
        if (labels.isEmpty()) {
            return false;
        }
        String choice = broker.chooseRefs("target", actor, labels, refs);
        int index = Integer.parseInt(choice.substring(1));
        GameEntity chosen = candidates.stream().filter(ability::canTarget).toList().get(index);
        if (!ability.getTargets().add(chosen)) {
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS23_TARGET_NATIVE_ADD_REJECTED");
        }
        return restrictions.isMinTargetsChosen(host, ability);
    }

    static boolean payManaCost(
            PlayerController controller,
            ManaCost toPay,
            CostPartMana costPartMana,
            SpellAbility ability,
            Player actor,
            String prompt,
            ManaConversionMatrix matrix,
            boolean effect) {
        return PlaySpellAbility.payManaCost(
                controller, toPay, costPartMana, ability, actor, prompt, matrix, effect);
    }

    static boolean applyManaToCost(
            Ws23ForgeVerticalProvider.Broker broker,
            Player actor,
            ManaCostBeingPaid toPay,
            SpellAbility ability,
            ManaConversionMatrix matrix) {
        while (!toPay.isPaid()) {
            List<Mana> legal = new ArrayList<>();
            for (Mana mana : actor.getManaPool()) {
                if (toPay.isNeeded(mana, actor.getManaPool())
                        && mana.meetsManaRestrictions(ability)
                        && ability.allowsPayingWithShard(mana.getSourceCard(), mana.getColor())) {
                    legal.add(mana);
                }
            }
            if (legal.isEmpty()) {
                throw new UnsupportedOperationException("WS23_FAIL_CLOSED_UNSUPPORTED:applyManaToCost:NO_FLOATING_MANA_OPTION");
            }
            List<String> labels = new ArrayList<>();
            List<String> refs = new ArrayList<>();
            for (int i = 0; i < legal.size(); i++) {
                labels.add("NATIVE_MANA");
                refs.add("mana:" + i);
            }
            String choice = broker.chooseRefs("mana_payment", actor, labels, refs);
            Mana selected = legal.get(Integer.parseInt(choice.substring(1)));
            if (!actor.getManaPool().tryPayCostWithMana(ability, toPay, selected, false)) {
                throw new Ws23ForgeVerticalProvider.ControlledStop("WS23_FORGE_REJECTED_OFFERED_MANA");
            }
        }
        return true;
    }

    static boolean confirmReplacement(
            Ws23ForgeVerticalProvider.Broker broker,
            Player actor,
            ReplacementEffect replacementEffect,
            SpellAbility effectSA,
            GameEntity affected,
            String question) {
        return broker.chooseBoolean("confirmReplacementEffect", actor, "APPLY", "DECLINE");
    }

    static void declareAttackers(
            Ws23ForgeVerticalProvider.Broker broker, Player actor, Player attacker, Combat combat) {
        CardCollection possibleAttackers = CombatUtil.getPossibleAttackers(attacker);
        if (possibleAttackers.size() > 1) {
            throw new UnsupportedOperationException("WS23_FAIL_CLOSED_UNSUPPORTED:declareAttackers:MULTI_ATTACKER");
        }

        List<String> labels = new ArrayList<>();
        List<String> refs = new ArrayList<>();
        if (CombatUtil.validateAttackers(combat)) {
            labels.add("NO_ATTACK");
            refs.add("pass");
        }
        List<GameEntity> defenders = new ArrayList<>();
        Card only = possibleAttackers.isEmpty() ? null : possibleAttackers.get(0);
        if (only != null) {
            for (GameEntity defender : CombatUtil.getAllPossibleDefenders(attacker)) {
                if (CombatUtil.canAttack(only, defender)
                        && CombatUtil.getAttackCost(attacker.getGame(), only, defender) == null) {
                    labels.add("ATTACK");
                    if (defender instanceof Player p) {
                        refs.add("attack:" + cardRef(only) + "->" + playerRef(p));
                    } else if (defender instanceof Card c) {
                        refs.add("attack:" + cardRef(only) + "->" + cardRef(c));
                    } else {
                        refs.add("attack:" + cardRef(only) + "->entity:" + defender.getId());
                    }
                    defenders.add(defender);
                }
            }
        }
        if (labels.isEmpty()) {
            broker.recordAutomatic("declareAttackers:NO_LEGAL_DECLARATION");
            return;
        }
        String choice = broker.chooseRefs("declareAttackers", actor, labels, refs);
        int idx = Integer.parseInt(choice.substring(1));
        if ("NO_ATTACK".equals(labels.get(idx))) {
            return;
        }
        int defenderIndex = 0;
        for (int i = 0; i < idx; i++) {
            if ("ATTACK".equals(labels.get(i))) defenderIndex++;
        }
        combat.addAttacker(only, defenders.get(defenderIndex));
        if (!CombatUtil.validateAttackers(combat)) {
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS23_FORGE_REJECTED_OFFERED_ATTACK");
        }
    }

    static void declareBlockers(
            Ws23ForgeVerticalProvider.Broker broker, Player actor, Player defender, Combat combat) {
        List<Card> attackers = new ArrayList<>(combat.getAttackers());
        CardCollection blockers = defender.getCreaturesInPlay();
        if (attackers.size() > 1 || blockers.size() > 1) {
            throw new UnsupportedOperationException("WS23_FAIL_CLOSED_UNSUPPORTED:declareBlockers:COMPLEX_COMBAT");
        }
        List<String> labels = new ArrayList<>();
        List<String> refs = new ArrayList<>();
        labels.add("NO_BLOCK");
        refs.add("pass");
        if (attackers.size() == 1 && blockers.size() == 1
                && CombatUtil.canBlock(attackers.get(0), blockers.get(0), combat)
                && CombatUtil.getBlockCost(defender.getGame(), blockers.get(0), attackers.get(0)) == null) {
            labels.add("BLOCK");
            refs.add("block:" + cardRef(blockers.get(0)) + "->" + cardRef(attackers.get(0)));
        }
        String choice = broker.chooseRefs("declareBlockers", actor, labels, refs);
        int idx = Integer.parseInt(choice.substring(1));
        if (idx == 1) {
            combat.addBlocker(attackers.get(0), blockers.get(0));
        }
        String validation = CombatUtil.validateBlocks(combat, defender);
        if (validation != null) {
            throw new Ws23ForgeVerticalProvider.ControlledStop("WS23_FORGE_REJECTED_OFFERED_BLOCK:" + validation);
        }
    }
}
