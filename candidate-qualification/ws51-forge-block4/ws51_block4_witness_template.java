// WS51 BLOCK-4 witness (WS51-owned, qualification-only, GPL-side test).
//
// Hand-built native combat equivalent of the WS05-MP-BLOCK-4 restore shape,
// WITHOUT the WS51 state-restore mechanism: no Ws40SuccessorState, no
// applyCombat, no snapshots, no provider protocol. Uses ONLY pinned Forge
// engine classes plus a mechanical stub controller (abstracts generated from
// the pinned PlayerController.java surface, exactly like the WS48 R1d probe).
//
// Shape mirrors the frozen BLOCK-4 record (turn 1, combat/declare_blockers,
// attackers mp-a2->P2 and mp-a3->P3, eligible P2 blockers) projected onto a
// 2-seat hand-built game: bearA(P1)->P2 BLOCKED by runeclaw(P2),
// bearB(P1)->P2 UNBLOCKED. The loader sequence is mirrored step for step:
// devModeSet(COMBAT_DECLARE_BLOCKERS) BEFORE new Combat + setCombat (the
// loader calls devModeSet first, then applyCombat), addAttacker per A-row,
// addBlocker + setBlocked(true) per B-row, updateCombatForView.
//
// Variants:
//   A LOAD_UNREPAIRED ......... loader-exact, no finalization.
//   B LOAD_FLAGMIRROR ......... A + WS51_MIRROR_UNDER_TEST, the exact
//                               provisional formula shipped in the WS48
//                               overlay (ws48FinalizeLoadedCombatBands):
//                               band.setBlocked(!combat.getBlockers(band)
//                               .isEmpty()). Formula parity with the overlay
//                               is asserted textually by the driver.
//   C LOAD_NATIVE_FINALIZE .... A + combat.fireTriggersForUnblockedAttackers,
//                               the native PhaseHandler:746 finalization.
//   D LOAD_FLAGMIRROR_TRIGGER . B with the unblocked attacker replaced by
//                               Abyssal Nightstalker (mandatory
//                               Mode$ AttackerUnblocked trigger). Adversarial:
//                               the skipped pipeline effect is Rules-relevant.
//   E LOAD_NATIVE_TRIGGER .... C with Abyssal Nightstalker.
//   F LOAD_PIPELINE_TAIL ..... A + the exact skipped declare-blockers tail in
//                               pipeline order (orderBlockersForDamageAssign-
//                               ment, orderAttackersForDamageAssignment,
//                               removeAbsentCombatants, fireTriggersForUn-
//                               blockedAttackers): what native continuation
//                               would have computed for the injected combat.
//
// Observation only: chooseCombatDamage is overridden SOLELY in the harness
// role (the production provider likewise chooses among core-authorized
// tuples): it records the presented native view, returns the deterministic
// first-recipient-full selection, and relies on the engine's own
// CombatDamageAssignmentValidator (which runs natively before commit) to
// reject anything illegal — an illegal pick fails the run instead of
// passing. Trigger firing is observed via
// MagicStack.hasSimultaneousStackEntries() before/after finalization:
// fired triggers land in the simultaneous-entry holding list, NOT on the
// main stack (addSimultaneousStackEntry). Post-deal damage ledgers
// (Card.getDamage / Player.getLife) expose silent assignment divergence.
// Life base is the Constructed default (20): the hand-built game never
// applies the Commander variant, exactly as in the R1d probe; only the
// damage/life DELTAS are under test. No engine state is mutated except
// through native APIs under test; no reflection is used.
//
// Expected (adjudicated by the driver, never assumed here):
//   A -> NULL_POINTER AttackingBand.isBlocked() null at Combat:873
//   B -> RETURNED, chooser never consulted, ledger shows blocked combat
//        dealing NOTHING (bearA_taken 0, runeclaw_taken 0; only the
//        unblocked attacker hits: p2_life 18): silent damage loss
//   C -> same as B (flag parity with B; ordering still skipped)
//   D -> RETURNED with sim_after_finalize false (mandatory trigger lost)
//   E -> RETURNED with sim_after_finalize true (native fires the trigger)
//   F -> chooser consulted exactly for the bearA division over exactly
//        the two injected blockers (source/recipient ids bind the injected
//        native objects), ledger shows bearA dealing 2 (runeclaw_taken 2)
// D-vs-E sim divergence (false vs true) proves trigger loss; B-vs-F
// ledger divergence (0 vs 2 dealt by the blocked attacker) proves silent
// damage loss on VANILLA cards. Crash prevention != semantic restoration.
package forge.game.player;

import forge.CardStorageReader;
import forge.LobbyPlayer;
import forge.StaticData;
import forge.card.CardRules;
import forge.card.CardType;
import forge.deck.Deck;
import forge.deck.DeckSection;
import forge.game.Game;
import forge.game.GameRules;
import forge.game.GameType;
import forge.game.Match;
import forge.game.card.Card;
import forge.game.combat.AttackingBand;
import forge.game.combat.Combat;
import forge.game.combat.CombatDamageDecisionView;
import forge.game.combat.CombatDamageSelection;
import forge.game.player.IGameEntitiesFactory;
import forge.item.PaperCard;
import forge.util.FileSection;
import forge.util.Lang;
import forge.util.Localizer;
import forge.util.MyRandom;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;

public final class Ws51Block4Witness {
    static final class Ws51StubReached extends RuntimeException {
        Ws51StubReached(String method) { super("WS51_STUB_BOUNDARY:" + method); }
    }

    // Observation records (written by the observing override, read by main).
    static int chooserCalls = 0;
    static final List<Integer> observedDamageSourceIds = new ArrayList<>();
    static final List<Integer> observedDamageRecipientIds = new ArrayList<>();
    static String observedDamageDetail = "none";

    static int entityId(forge.game.GameEntity e) {
        if (e instanceof Card c) return c.getId();
        return -1;
    }

    static final class Ws51Lobby extends LobbyPlayer implements IGameEntitiesFactory {
        Ws51Lobby(String name) { super(name); }

        @Override
        public void hear(LobbyPlayer from, String message) { }

        @Override
        public Player createIngamePlayer(Game game, int id) {
            Player p = new Player(getName(), game, id);
            p.dangerouslySetController(new Ws51StubController(game, p, this));
            return p;
        }

        @Override
        public PlayerController createMindSlaveController(Player master, Player slave) {
            throw new Ws51StubReached("createMindSlaveController");
        }
    }

    public static final class Ws51StubController extends PlayerController {
        public Ws51StubController(Game game0, Player p, LobbyPlayer lp) {
            super(game0, p, lp);
        }

        // HARNESS-ROLE override (not part of the mechanical abstract
        // surface): records the presented native view, returns the
        // deterministic first-recipient-full selection, and relies on the
        // engine's own CombatDamageAssignmentValidator to reject anything
        // illegal. Mirrors the production provider role (choose among
        // core-authorized tuples); the engine path up to the call and the
        // validation/commit after it are 100% native.
        @Override
        public CombatDamageSelection chooseCombatDamage(final CombatDamageDecisionView decision) {
            chooserCalls++;
            observedDamageSourceIds.clear();
            observedDamageRecipientIds.clear();
            if (decision == null || decision.getSources().isEmpty()) {
                throw new Ws51StubReached("chooseCombatDamage:EMPTY_CORE_VIEW");
            }
            CombatDamageDecisionView.SourceView first = decision.getSources().get(0);
            for (CombatDamageDecisionView.SourceView sv : decision.getSources()) {
                observedDamageSourceIds.add(sv.getSource() == null ? -1 : sv.getSource().getId());
            }
            if (first.getRecipients().isEmpty()) {
                throw new Ws51StubReached("chooseCombatDamage:NO_CORE_RECIPIENTS");
            }
            for (CombatDamageDecisionView.RecipientView rv : first.getRecipients()) {
                observedDamageRecipientIds.add(entityId(rv.getRecipient()));
            }
            observedDamageDetail = "sources=" + observedDamageSourceIds
                    + ":recipients=" + observedDamageRecipientIds
                    + ":remaining=" + first.getRemainingDamage();
            CombatDamageDecisionView.RecipientView pick = first.getRecipients().get(0);
            return new CombatDamageSelection(first.getSource(), pick.getRecipient(), first.getRemainingDamage());
        }

__STUB_METHODS__
    }

    static void initForge(Path languagesDirectory) throws Exception {
        MyRandom.setRandom(new Random(510051L));
        Lang.createInstance("en-US");
        Localizer.getInstance().initialize("en-US", languagesDirectory.toString());
        Path root = languagesDirectory.toAbsolutePath().normalize()
                .getParent().getParent().getParent();
        Path res = root.resolve("forge-gui/res");
        if (!CardType.Constant.LOADED.isSet()) {
            for (var section : FileSection.parseSections(
                    Files.readAllLines(res.resolve("lists/TypeLists.txt"))).entrySet()) {
                CardType.Helper.parseTypes(section.getKey(), section.getValue());
            }
            CardType.Constant.LOADED.set();
        }
        Path emptyCustomEditions = Files.createTempDirectory("ws51-forge-custom-editions-");
        CardStorageReader reader = new CardStorageReader(
                res.resolve("cardsfolder").toString(), null, true);
        StaticData data = new StaticData(reader, null,
                res.resolve("editions").toString(), emptyCustomEditions.toString(),
                res.resolve("blockdata").toString(), "latest", true, true);
        data.setFilteredHandsEnabled(false);
    }

    static PaperCard loadPaperCard(Path langDir, String name) throws Exception {
        PaperCard pc = StaticData.instance().getCommonCards().getCard(name);
        if (pc != null) return pc;
        // Identical to the production card-registration mechanism
        // (Ws40SuccessorState.registerCardRules): lazy per-card load plus
        // explicit index registration.
        Path cardsFolder = langDir.toAbsolutePath().normalize()
                .getParent().getParent().getParent()
                .resolve("forge-gui/res/cardsfolder");
        CardStorageReader cardReader = new CardStorageReader(cardsFolder.toString(), null, true);
        CardRules rules = cardReader.attemptToLoadCard(name);
        if (rules == null) throw new IllegalStateException("WS51_CARD_RULES_MISSING:" + name);
        PaperCard fresh = new PaperCard(rules, "M11", forge.card.CardRarity.Common);
        StaticData.instance().getCommonCards().addCard(fresh);
        return fresh;
    }

    static Card putIntoPlay(Game game, Player owner, String name, Path langDir) throws Exception {
        PaperCard pc = loadPaperCard(langDir, name);
        Card c = Card.fromPaperCard(pc, owner);
        owner.getZone(forge.game.zone.ZoneType.Hand).add(c);
        game.getAction().moveToPlay(c, null, null);
        c.setSickness(false);
        c.setTapped(false);
        if (c.getZone() == null || !c.getZone().is(forge.game.zone.ZoneType.Battlefield)) {
            throw new IllegalStateException("WS51_SETUP_NOT_ON_BATTLEFIELD:" + name);
        }
        return c;
    }

    static String esc(String s) {
        if (s == null) return "null";
        return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"")
                .replace("\n", "\\n") + "\"";
    }

    public static void main(String[] args) throws Exception {
        String variant = args.length > 0 ? args[0] : "A";
        boolean triggerBearer = "D".equals(variant) || "E".equals(variant);
        boolean flagMirror = "B".equals(variant) || "D".equals(variant);
        boolean nativeFinalize = "C".equals(variant) || "E".equals(variant);
        boolean pipelineTail = "F".equals(variant);
        if ("ABCDEF".indexOf(variant) < 0) throw new IllegalStateException("WS51_BAD_VARIANT:" + variant);
        Path langDir = Path.of(args.length > 1 ? args[1]
                : System.getenv("COMMANDER_LAB_FORGE_LANG_DIR"));
        initForge(langDir);

        GameRules rules = new GameRules(GameType.Constructed);
        java.util.List<RegisteredPlayer> registrations = new java.util.ArrayList<>();
        PaperCard mountain = loadPaperCard(langDir, "Mountain");
        for (int i = 1; i <= 2; i++) {
            Deck deck = new Deck("WS51-SEAT-" + i);
            deck.getMain().add(mountain, 40);
            deck.getOrCreate(DeckSection.Sideboard).add(mountain, 15);
            RegisteredPlayer rp = new RegisteredPlayer(deck);
            rp.setPlayer(new Ws51Lobby("ws51-seat-" + i));
            registrations.add(rp);
        }
        Match match = new Match(rules, registrations, "WS51 BLOCK-4 witness");
        Game game = match.createGame();
        // Hook-time fidelity: in production the restore hook runs inside
        // Match.startGame AFTER GameAction.startGame sets GameStage.Play
        // (mulligan/opening-hands/NewGame triggers precede the hook).
        // Trigger.requirementsCheck rejects GameStage != Play, so a
        // hand-built game that never starts would suppress every trigger
        // for setup reasons unrelated to the restore question.
        game.setAge(forge.game.GameStage.Play);
        Player p1 = game.getPlayers().get(0);
        Player p2 = game.getPlayers().get(1);

        Card bearA = putIntoPlay(game, p1, "Grizzly Bears", langDir);
        Card attackerB = putIntoPlay(game, p1, triggerBearer ? "Abyssal Nightstalker" : "Grizzly Bears", langDir);
        Card runeclaw = putIntoPlay(game, p2, "Runeclaw Bear", langDir);
        // Second P2 blocker mirrors the frozen v1.0.5 eligible_blockers pair
        // [obj:P2-bears, obj:mp-p2-blocker]: a multi-blocker band forces a
        // genuine damage-division decision, so native continuation reaches the
        // controller boundary (single-blocker bands auto-assign and would
        // return without ever consulting the controller).
        Card p2bears = putIntoPlay(game, p2, "Grizzly Bears", langDir);
        if (triggerBearer && attackerB.getTriggers().isEmpty()) {
            throw new IllegalStateException("WS51_SETUP_TRIGGER_NOT_PARSED:Abyssal Nightstalker");
        }
        int idA = bearA.getId();
        int idB = attackerB.getId();
        int idR = runeclaw.getId();
        int idP2B = p2bears.getId();

        // Loader-exact order (Ws40SuccessorState.applyNativeState): devModeSet
        // FIRST (positions the restored phase, skipping its entry effects),
        // then hand-built combat injection (applyCombat equivalent).
        game.getPhaseHandler().devModeSet(
                forge.game.phase.PhaseType.COMBAT_DECLARE_BLOCKERS, p1, 1);
        Combat combat = new Combat(p1);
        game.getPhaseHandler().setCombat(combat);
        combat.addAttacker(bearA, p2);
        combat.addAttacker(attackerB, p2);
        combat.addBlocker(bearA, runeclaw);
        combat.addBlocker(bearA, p2bears);
        combat.setBlocked(bearA, true);
        game.updateCombatForView();

        // Fired triggers land in the engine's simultaneous-entry holding
        // list (MagicStack.addSimultaneousStackEntry), NOT on the main
        // stack: hasSimultaneousStackEntries() is the synchronous,
        // read-only fired-vs-lost observable. The list starts empty;
        // nothing else in this setup enqueues simultaneous entries.
        boolean simBefore = game.getStack().hasSimultaneousStackEntries();
        int stackBeforeFinalize = game.getStack().size();

        String finalizeMode;
        if (pipelineTail) {
            // Exact skipped declare-blockers tail in pipeline order
            // (PhaseHandler.declareBlockersTurnBasedAction tail end).
            combat.orderBlockersForDamageAssignment();
            combat.orderAttackersForDamageAssignment();
            combat.removeAbsentCombatants();
            combat.fireTriggersForUnblockedAttackers(game);
            finalizeMode = "PIPELINE_TAIL";
        } else if (flagMirror) {
            // WS51_MIRROR_UNDER_TEST: exact provisional overlay formula.
            for (AttackingBand band : combat.getAttackingBands()) {
                band.setBlocked(!combat.getBlockers(band).isEmpty());
            }
            finalizeMode = "FLAGMIRROR";
        } else if (nativeFinalize) {
            combat.fireTriggersForUnblockedAttackers(game);
            finalizeMode = "NATIVE";
        } else {
            finalizeMode = "NONE";
        }

        StringBuilder flags = new StringBuilder();
        flags.append("A:").append(combat.getBandOfAttacker(bearA) == null
                ? "noband" : String.valueOf(combat.getBandOfAttacker(bearA).isBlocked()));
        flags.append(",B:").append(combat.getBandOfAttacker(attackerB) == null
                ? "noband" : String.valueOf(combat.getBandOfAttacker(attackerB).isBlocked()));
        boolean simAfter = game.getStack().hasSimultaneousStackEntries();
        int stackAfterFinalize = game.getStack().size();

        String outcome;
        String detail = "null";
        String top = "null";
        String ledger = "none";
        try {
            combat.assignCombatDamage(false);
            outcome = "RETURNED";
            combat.dealAssignedDamage();
            ledger = "bearA_taken=" + bearA.getDamage()
                    + ":runeclaw_taken=" + runeclaw.getDamage()
                    + ":p2bears_taken=" + p2bears.getDamage()
                    + ":attackerB_taken=" + attackerB.getDamage()
                    + ":p2_life=" + p2.getLife()
                    + ":p1_life=" + p1.getLife();
        } catch (NullPointerException npe) {
            outcome = "NULL_POINTER";
            detail = String.valueOf(npe.getMessage());
            StackTraceElement[] st = npe.getStackTrace();
            if (st.length > 0) top = st[0].toString();
        } catch (Ws51StubReached stub) {
            outcome = "CONTROLLER_BOUNDARY";
            detail = String.valueOf(stub.getMessage());
            StackTraceElement[] st = stub.getStackTrace();
            if (st.length > 1) top = st[1].toString();
        } catch (Throwable t) {
            outcome = "OTHER:" + t.getClass().getName();
            detail = String.valueOf(t.getMessage());
            StackTraceElement[] st = t.getStackTrace();
            if (st.length > 0) top = st[0].toString();
        }
        int stackAfterAssign = game.getStack().size();
        List<Integer> injected = List.of(idA, idB, idR, idP2B);
        List<Integer> observed = new ArrayList<>(observedDamageSourceIds);
        List<Integer> observedRecipients = new ArrayList<>(observedDamageRecipientIds);
        // Gate-4 binding proof for the F variant: the native pipeline built
        // its division view from exactly the injected native objects (the
        // blocked attacker as source, the two injected blockers as the
        // recipient set).
        boolean identityMatch = pipelineTail && chooserCalls == 1
                && observed.size() == 1 && observed.get(0) == idA
                && observedRecipients.size() == 2
                && observedRecipients.contains(idR) && observedRecipients.contains(idP2B);
        System.out.println("{\"ws51_variant\":" + esc(variant)
                + ",\"finalize_mode\":" + esc(finalizeMode)
                + ",\"trigger_bearer\":" + triggerBearer
                + ",\"injected_ids\":" + esc(injected.toString())
                + ",\"band_flags\":" + esc(flags.toString())
                + ",\"sim_before_finalize\":" + simBefore
                + ",\"sim_after_finalize\":" + simAfter
                + ",\"stack_after_finalize\":" + stackAfterFinalize
                + ",\"chooser_calls\":" + chooserCalls
                + ",\"observed_damage_source_ids\":" + esc(observed.toString())
                + ",\"observed_damage_recipient_ids\":" + esc(observedRecipients.toString())
                + ",\"identity_match\":" + identityMatch
                + ",\"ledger\":" + esc(ledger)
                + ",\"stack_after_assign\":" + stackAfterAssign
                + ",\"outcome\":" + esc(outcome)
                + ",\"detail\":" + esc(detail)
                + ",\"top_frame\":" + esc(top) + "}");
    }
}
