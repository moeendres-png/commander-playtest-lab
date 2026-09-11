// R1d BLOCK-4 discriminator (WS48-owned, qualification-only, GPL-side test).
//
// Hand-built native combat equivalent WITHOUT the WS48 state-restore
// mechanism: no Ws40SuccessorState, no applyCombat, no snapshots, no
// provider protocol. Uses ONLY pinned Forge engine classes (Combat,
// AttackingBand, Game/Match/Player/Card) plus a mechanical stub controller.
//
// Variant A (restore-equivalent): new Combat + addAttacker only, mirroring
// exactly what the loader path builds for an unblocked attacker (the loader
// calls setBlocked only for B-row blocked attackers; unblocked bands keep
// the null flag because the loader bypasses the declare-blockers pipeline).
// Variant B (native-equivalent): additionally runs
// Combat.fireTriggersForUnblockedAttackers(game), the finalization that
// PhaseHandler:746 executes in every real game after declare blockers.
//
// Both variants call Combat.assignCombatDamage(false) and report the exact
// terminal class. Criterion:
//   A throws NPE "AttackingBand.isBlocked() is null" at Combat:873 AND
//   B does NOT (proceeds past damage assignment to the stub controller
//   boundary)  =>  STATE_RESTORE_OR_ADAPTER_DEFECT
//   B throws the same 873-NPE  =>  ENGINE_DEFECT_CONFIRMED_CANDIDATE
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
import forge.game.combat.Combat;
import forge.game.player.IGameEntitiesFactory;
import forge.item.PaperCard;
import forge.util.FileSection;
import forge.util.Lang;
import forge.util.Localizer;
import forge.util.MyRandom;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Random;

public final class R1dCombatDiscriminator {
    static final class R1dStubReached extends RuntimeException {
        R1dStubReached(String method) { super("R1D_STUB_BOUNDARY:" + method); }
    }

    static final class R1dLobby extends LobbyPlayer implements IGameEntitiesFactory {
        R1dLobby(String name) { super(name); }

        @Override
        public void hear(LobbyPlayer from, String message) { }

        @Override
        public Player createIngamePlayer(Game game, int id) {
            Player p = new Player(getName(), game, id);
            p.dangerouslySetController(new R1dStubController(game, p, this));
            return p;
        }

        @Override
        public PlayerController createMindSlaveController(Player master, Player slave) {
            throw new R1dStubReached("createMindSlaveController");
        }
    }

    public static final class R1dStubController extends PlayerController {
        public R1dStubController(Game game0, Player p, LobbyPlayer lp) {
            super(game0, p, lp);
        }

__STUB_METHODS__
    }

    static void initForge(Path languagesDirectory) throws Exception {
        MyRandom.setRandom(new Random(230023L));
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
        Path emptyCustomEditions = Files.createTempDirectory("r1d-forge-custom-editions-");
        CardStorageReader reader = new CardStorageReader(
                res.resolve("cardsfolder").toString(), null, true);
        StaticData data = new StaticData(reader, null,
                res.resolve("editions").toString(), emptyCustomEditions.toString(),
                res.resolve("blockdata").toString(), "latest", true, true);
        data.setFilteredHandsEnabled(false);
    }

    static String esc(String s) {
        if (s == null) return "null";
        return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"")
                .replace("\n", "\\n") + "\"";
    }

    public static void main(String[] args) throws Exception {
        String variant = args.length > 0 ? args[0] : "A";
        Path langDir = Path.of(args.length > 1 ? args[1]
                : System.getenv("COMMANDER_LAB_FORGE_LANG_DIR"));
        initForge(langDir);

        GameRules rules = new GameRules(GameType.Constructed);
        java.util.List<RegisteredPlayer> registrations = new java.util.ArrayList<>();
        PaperCard mountain = new PaperCard(
                new CardStorageReader(langDir.toAbsolutePath().normalize()
                        .getParent().getParent().getParent()
                        .resolve("forge-gui/res/cardsfolder").toString(), null, true)
                        .attemptToLoadCard("Mountain"),
                "10E", forge.card.CardRarity.BasicLand);
        for (int i = 1; i <= 2; i++) {
            Deck deck = new Deck("R1D-SEAT-" + i);
            deck.getMain().add(mountain, 40);
            deck.getOrCreate(DeckSection.Sideboard).add(mountain, 15);
            RegisteredPlayer rp = new RegisteredPlayer(deck);
            rp.setPlayer(new R1dLobby("r1d-seat-" + i));
            registrations.add(rp);
        }
        Match match = new Match(rules, registrations, "R1D discriminator");
        Game game = match.createGame();
        Player p1 = game.getPlayers().get(0);
        Player p2 = game.getPlayers().get(1);

        PaperCard bearPc = StaticData.instance().getCommonCards().getCard("Grizzly Bears");
        if (bearPc == null) {
            // Identical to the production card-registration mechanism
            // (Ws40SuccessorState.registerCardRules): lazy per-card load plus
            // explicit index registration, because the bootstrap reader is
            // lazy and the StaticData index starts empty headlessly.
            CardStorageReader cardReader = new CardStorageReader(
                    langDir.toAbsolutePath().normalize()
                            .getParent().getParent().getParent()
                            .resolve("forge-gui/res/cardsfolder").toString(),
                    null, true);
            CardRules bearRules = cardReader.attemptToLoadCard("Grizzly Bears");
            if (bearRules == null) throw new IllegalStateException("R1D_BEAR_RULES_MISSING");
            bearPc = new PaperCard(bearRules, "M11", forge.card.CardRarity.Common);
            StaticData.instance().getCommonCards().addCard(bearPc);
        }
        Card bear = Card.fromPaperCard(bearPc, p1);
        p1.getZone(forge.game.zone.ZoneType.Hand).add(bear);
        game.getAction().moveToPlay(bear, null, null);
        bear.setSickness(false);
        bear.setTapped(false);

        // Mirror the production restore placement (WS05-MP-BLOCK-4:
        // combat/declare_blockers): the game is positioned mid-combat phase
        // BEFORE combat is hand-built, exactly as applyNativeState does
        // (devModeSet, then applyCombat). new Combat() requires a non-null
        // phase via initConstraints, just like the loader path.
        game.getPhaseHandler().devModeSet(
                forge.game.phase.PhaseType.COMBAT_DECLARE_BLOCKERS, p1, 1);
        Combat combat = new Combat(p1);
        game.getPhaseHandler().setCombat(combat);
        combat.addAttacker(bear, p2);
        boolean finalized = false;
        if ("B".equals(variant)) {
            combat.fireTriggersForUnblockedAttackers(game);
            finalized = true;
        }

        String outcome;
        String detail = "null";
        String top = "null";
        try {
            combat.assignCombatDamage(false);
            outcome = "RETURNED";
        } catch (NullPointerException npe) {
            outcome = "NULL_POINTER";
            detail = String.valueOf(npe.getMessage());
            StackTraceElement[] st = npe.getStackTrace();
            if (st.length > 0) top = st[0].toString();
        } catch (R1dStubReached stub) {
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
        System.out.println("{\"r1d_variant\":" + esc(variant)
                + ",\"finalized_natively\":" + finalized
                + ",\"outcome\":" + esc(outcome)
                + ",\"detail\":" + esc(detail)
                + ",\"top_frame\":" + esc(top) + "}");
    }
}
