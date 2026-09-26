package org.commanderlab.xmage;

import com.google.common.collect.Iterables;
import mage.MageItem;
import mage.MageObject;
import mage.abilities.Ability;
import mage.abilities.ActivatedAbility;
import mage.abilities.Mode;
import mage.abilities.Modes;
import mage.abilities.SpellAbility;
import mage.abilities.TriggeredAbility;
import mage.abilities.costs.mana.ManaCost;
import mage.cards.Card;
import mage.cards.Cards;
import mage.cards.decks.Deck;
import mage.choices.Choice;
import mage.constants.MultiAmountType;
import mage.constants.Outcome;
import mage.constants.RangeOfInfluence;
import mage.players.net.UserData;
import mage.game.Game;
import mage.game.draft.Draft;
import mage.game.match.Match;
import mage.game.tournament.Tournament;
import mage.players.Player;
import mage.players.PlayerImpl;
import mage.target.Target;
import mage.target.TargetAmount;
import mage.target.TargetCard;
import mage.target.TargetPlayer;
import mage.util.MultiAmountMessage;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Headless bridge player for the real pinned XMage lifecycle.
 *
 * <p>The no-controller constructor preserves the validated B3 behavior: keep
 * the opening hand, decline optional choices, declare no attackers/blockers,
 * and pass priority. When an ExternalDecisionController is attached (B4
 * external control), priority is paused and published rather than silently
 * auto-passed, the init-phase starting-player selection honors the requested
 * seat by self-selecting, and every other discretionary Player callback fails
 * closed with UNSUPPORTED_COMPATIBILITY_DECISION instead of silently returning
 * a tactical default. ChooseMulligan (keep), shuffleLibrary (no-op, unseeded),
 * and the GUI/out-of-scope lifecycle methods remain bounded compatibility
 * behavior on both paths; they are not gameplay evidence.</p>
 */
final class XmageBridgePlayer extends PlayerImpl {

    private final ExternalDecisionController externalDecisionController;

    XmageBridgePlayer(
            String name,
            RangeOfInfluence range
    ) {
        this(name, range, null);
    }

    XmageBridgePlayer(
            String name,
            RangeOfInfluence range,
            ExternalDecisionController externalDecisionController
    ) {
        super(name, range);
        this.externalDecisionController = externalDecisionController;
        setUserData(
                UserData.getDefaultUserDataView()
        );
    }

    private XmageBridgePlayer(
            XmageBridgePlayer player
    ) {
        super(player);
        this.externalDecisionController = player.externalDecisionController;
    }

    @Override
    public XmageBridgePlayer copy() {
        return new XmageBridgePlayer(this);
    }

    /**
     * Fail-closed boundary for the B4 externally controlled compatibility path.
     *
     * <p>The null-controller constructor preserves the validated B3 behavior
     * (keep the opening hand, decline optional choices, declare no
     * attackers/blockers, pass priority). When an ExternalDecisionController is
     * attached, the lane publishes only priority decisions; any other
     * discretionary Player callback is unsupported and must fail the game
     * rather than silently return a tactical default (first/min/false/null or
     * no-op). The failure surfaces as {@link XmageGameManager.GameException}
     * so {@code game.start()} reports {@code XMAGE_GAME_START_FAILED} and
     * {@code game.resume()} inside pass/submit reports a fail-closed action
     * failure instead of advancing state on a hidden default.</p>
     */
    private void failIfExternallyControlled(String callback) {
        if (externalDecisionController != null) {
            throw new XmageGameManager.GameException(
                    "UNSUPPORTED_COMPATIBILITY_DECISION: " + callback
                            + " requires external decision control;"
                            + " B4 compatibility supports only priority pass"
                            + " and submission-ready targetless/nonmodal actions"
            );
        }
    }

    /**
     * Narrow init-phase exception for the validated bounded start.
     *
     * <p>{@code GameImpl.init} asks the choosing player to {@code Select a
     * starting player} (a {@link TargetPlayer} with no source before any phase
     * exists). The bounded bridge honors the requested
     * {@code starting_player_seat} by selecting the choosing player itself.
     * Every other {@code choose(Target)} on the externally controlled path
     * remains unsupported and fails closed.</p>
     */
    private boolean isStartingPlayerInitChoice(
            Target target,
            Ability source,
            Game game
    ) {
        if (!(target instanceof TargetPlayer) || source != null || game == null) {
            return false;
        }
        if (game.getTurnPhaseType() != null) {
            return false;
        }
        try {
            return "Select a starting player".equals(target.getMessage(game))
                    && "target starting player".equals(target.getDescription())
                    && target.getMinNumberOfTargets() == 1
                    && target.getMaxNumberOfTargets() == 1;
        } catch (Exception exc) {
            return false;
        }
    }

    @Override
    public SpellAbility chooseAbilityForCast(
            Card card,
            Game game,
            boolean noMana
    ) {
        failIfExternallyControlled("chooseAbilityForCast");
        return super.chooseAbilityForCast(card, game, noMana);
    }

    @Override
    public ActivatedAbility chooseLandOrSpellAbility(
            Card card,
            Game game,
            boolean noMana
    ) {
        failIfExternallyControlled("chooseLandOrSpellAbility");
        return super.chooseLandOrSpellAbility(card, game, noMana);
    }

    @Override
    public boolean priority(Game game) {
        if (externalDecisionController == null) {
            /*
             * Validated B3 lifecycle path. XMage playPriority() loops until
             * isPassed() becomes true, so returning false alone is insufficient.
             */
            pass(game);
            return false;
        }

        /*
         * B4-B external-control path. Capture the real XMage decision before
         * pausing. GameImpl checks isPaused() on the priority loop and returns
         * control to the JSONL bridge without a busy wait or tactical fallback.
         */
        externalDecisionController.capturePriority(this, game);
        game.pause();
        return false;
    }

    @Override
    public boolean choose(
            Outcome outcome,
            Target target,
            Ability source,
            Game game
    ) {
        if (externalDecisionController != null
                && !isStartingPlayerInitChoice(target, source, game)) {
            failIfExternallyControlled("choose(Target)");
        }
        if (target instanceof TargetPlayer) {
            for (Player player : game.getPlayers().values()) {
                if (player.getId().equals(getId())
                        && target.canTarget(
                                getId(),
                                source,
                                game
                        )
                        && !target.contains(getId())) {

                    target.add(
                            player.getId(),
                            game
                    );

                    return true;
                }
            }
        }

        return false;
    }

    @Override
    public boolean choose(
            Outcome outcome,
            Cards cards,
            TargetCard target,
            Ability source,
            Game game
    ) {
        failIfExternallyControlled("choose(Cards,TargetCard)");
        cards.getCards(game)
                .stream()
                .map(MageItem::getId)
                .forEach(
                        cardId -> target.add(
                                cardId,
                                game
                        )
                );

        return true;
    }

    @Override
    public boolean chooseTarget(
            Outcome outcome,
            Cards cards,
            TargetCard target,
            Ability source,
            Game game
    ) {
        failIfExternallyControlled("chooseTarget(Cards,TargetCard)");
        UUID cardId =
                Iterables.getOnlyElement(
                        cards.getCards(game)
                ).getId();

        if (chooseScry(game, cardId)) {
            target.add(cardId, game);
            return true;
        }

        return false;
    }

    List<UUID> chooseDiscardBottom(
            Game game,
            int count,
            List<UUID> cardIds
    ) {
        return cardIds.subList(0, count);
    }

    boolean chooseScry(
            Game game,
            UUID cardId
    ) {
        return false;
    }

    @Override
    public void shuffleLibrary(
            Ability source,
            Game game
    ) {
        /*
         * B3/B4 compatibility bridge testing is not seeded gameplay evidence.
         * Deterministic/randomized gameplay is promoted only after a real gate.
         */
    }

    @Override
    public void abort() {
    }

    @Override
    public void skip() {
    }

    @Override
    public boolean choose(
            Outcome outcome,
            Target target,
            Ability source,
            Game game,
            Map<String, Serializable> options
    ) {
        failIfExternallyControlled("choose(Target,options)");
        return false;
    }

    @Override
    public boolean chooseTarget(
            Outcome outcome,
            Target target,
            Ability source,
            Game game
    ) {
        failIfExternallyControlled("chooseTarget(Target)");
        if (target.getFilter().getMessage() != null
                && target.getFilter()
                        .getMessage()
                        .endsWith(
                                " more) to put on the bottom of your library"
                        )) {

            chooseDiscardBottom(
                    game,
                    target.getMinNumberOfTargets(),
                    new ArrayList<>(
                            target.possibleTargets(
                                    null,
                                    source,
                                    game
                            )
                    )
            ).forEach(
                    cardId -> target.add(
                            cardId,
                            game
                    )
            );
        }

        return false;
    }

    @Override
    public boolean chooseTargetAmount(
            Outcome outcome,
            TargetAmount target,
            Ability source,
            Game game
    ) {
        failIfExternallyControlled("chooseTargetAmount");
        return false;
    }

    @Override
    public boolean chooseMulligan(
            Game game
    ) {
        return false;
    }

    @Override
    public boolean chooseUse(
            Outcome outcome,
            String message,
            Ability source,
            Game game
    ) {
        failIfExternallyControlled("chooseUse");
        return false;
    }

    @Override
    public boolean chooseUse(
            Outcome outcome,
            String message,
            String secondMessage,
            String trueText,
            String falseText,
            Ability source,
            Game game
    ) {
        failIfExternallyControlled("chooseUse(detailed)");
        return false;
    }

    @Override
    public boolean choose(
            Outcome outcome,
            Choice choice,
            Game game
    ) {
        failIfExternallyControlled("choose(Choice)");
        return false;
    }

    @Override
    public boolean choosePile(
            Outcome outcome,
            String message,
            List<? extends Card> pile1,
            List<? extends Card> pile2,
            Game game
    ) {
        failIfExternallyControlled("choosePile");
        return false;
    }

    @Override
    public boolean playMana(
            Ability ability,
            ManaCost unpaid,
            String promptText,
            Game game
    ) {
        failIfExternallyControlled("playMana");
        return false;
    }

    @Override
    public int announceX(
            int min,
            int max,
            String message,
            Game game,
            Ability source,
            boolean isManaPay
    ) {
        failIfExternallyControlled("announceX");
        return min;
    }

    @Override
    public int chooseReplacementEffect(
            Map<String, String> effectsMap,
            Map<String, MageObject> objectsMap,
            Game game
    ) {
        failIfExternallyControlled("chooseReplacementEffect");
        return 0;
    }

    @Override
    public TriggeredAbility chooseTriggeredAbility(
            List<TriggeredAbility> abilities,
            Game game
    ) {
        failIfExternallyControlled("chooseTriggeredAbility");
        return null;
    }

    @Override
    public Mode chooseMode(
            Modes modes,
            Ability source,
            Game game
    ) {
        failIfExternallyControlled("chooseMode");
        return null;
    }

    @Override
    public void selectAttackers(
            Game game,
            UUID attackingPlayerId
    ) {
        failIfExternallyControlled("selectAttackers");
    }

    @Override
    public void selectBlockers(
            Ability source,
            Game game,
            UUID defendingPlayerId
    ) {
        failIfExternallyControlled("selectBlockers");
    }

    @Override
    public int getAmount(
            int min,
            int max,
            String message,
            Ability source,
            Game game
    ) {
        failIfExternallyControlled("getAmount");
        return min;
    }

    @Override
    public List<Integer> getMultiAmountWithIndividualConstraints(
            Outcome outcome,
            List<MultiAmountMessage> messages,
            int totalMin,
            int totalMax,
            MultiAmountType type,
            Game game
    ) {
        failIfExternallyControlled("getMultiAmountWithIndividualConstraints");
        return null;
    }

    @Override
    public void sideboard(
            Match match,
            Deck deck
    ) {
    }

    @Override
    public void construct(
            Tournament tournament,
            Deck deck
    ) {
    }

    @Override
    public void pickCard(
            List<Card> cards,
            Deck deck,
            Draft draft
    ) {
    }
}
