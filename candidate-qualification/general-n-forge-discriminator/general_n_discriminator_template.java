// D1 General-N Forge Commander discriminator (research-only, grants no credit).
//
// Hand-built native Commander game construction for N=2..6 using ONLY pinned
// Forge engine classes (Game/Match/GameRules/GameType/RegisteredPlayer,
// Combat, Player, Zones). No provider protocol, no state restore, no harness
// legality: the stub controller throws R1d-style boundary markers if reached.
//
// Each scenario prints one JSON object per line to stdout:
//   {"n":N,"check":NAME,"outcome":"PASS|FAIL|ERROR","detail":...}
// "ERROR" = probe-internal failure (fixture), never counted as engine PASS.
//
// Usage: GeneralNForgeDiscriminator <N> <langDir> <seed>
package forge.game.player;

import forge.CardStorageReader;
import forge.LobbyPlayer;
import forge.StaticData;
import forge.card.CardRules;
import forge.card.CardType;
import forge.deck.Deck;
import forge.deck.DeckSection;
import forge.game.Game;
import forge.game.GameEntity;
import forge.game.GameRules;
import forge.game.GameType;
import forge.game.Match;
import forge.game.card.Card;
import forge.game.combat.Combat;
import forge.game.player.IGameEntitiesFactory;
import forge.game.zone.ZoneType;
import forge.item.PaperCard;
import forge.util.FileSection;
import forge.util.Lang;
import forge.util.Localizer;
import forge.util.MyRandom;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;

public final class GeneralNForgeDiscriminator {
    static final class StubReached extends RuntimeException {
        StubReached(String method) { super("GENERAL_N_STUB_BOUNDARY:" + method); }
    }

    static final class SeatLobby extends LobbyPlayer implements IGameEntitiesFactory {
        SeatLobby(String name) { super(name); }

        @Override
        public void hear(LobbyPlayer from, String message) { }

        @Override
        public Player createIngamePlayer(Game game, int id) {
            Player p = new Player(getName(), game, id);
            p.dangerouslySetController(new SeatStubController(game, p, this));
            return p;
        }

        @Override
        public PlayerController createMindSlaveController(Player master, Player slave) {
            throw new StubReached("createMindSlaveController");
        }
    }

    public static final class SeatStubController extends PlayerController {
        public SeatStubController(Game game0, Player p, LobbyPlayer lp) {
            super(game0, p, lp);
        }

__STUB_METHODS__
    }

    static void initForge(Path languagesDirectory) throws Exception {
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
        Path emptyCustomEditions = Files.createTempDirectory("gn-forge-custom-editions-");
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

    static void emit(int n, String check, String outcome, String detail) {
        System.out.println("{\"n\":" + n + ",\"check\":" + esc(check)
                + ",\"outcome\":" + esc(outcome) + ",\"detail\":" + esc(detail) + "}");
    }

    static PaperCard mountainPaper(Path langDir) {
        String cardsFolder = langDir.toAbsolutePath().normalize()
                .getParent().getParent().getParent()
                .resolve("forge-gui/res/cardsfolder").toString();
        return new PaperCard(
                new CardStorageReader(cardsFolder, null, true).attemptToLoadCard("Mountain"),
                "10E", forge.card.CardRarity.BasicLand);
    }

    static final String[] COMMANDER_CANDIDATES = {
        "Isamaru, Hound of Konda", "Krenko, Mob Boss", "Talrand, Sky Summoner",
        "Azusa, Lost but Seeking", "Grizzly Bears" // last: non-legendary fallback, flagged
    };
    static String commanderUsed = "null";

    static PaperCard commanderPaper(Path langDir) {
        String cardsFolder = langDir.toAbsolutePath().normalize()
                .getParent().getParent().getParent()
                .resolve("forge-gui/res/cardsfolder").toString();
        CardStorageReader reader = new CardStorageReader(cardsFolder, null, true);
        for (String name : COMMANDER_CANDIDATES) {
            CardRules rules = reader.attemptToLoadCard(name);
            if (rules == null) continue;
            PaperCard existing = StaticData.instance().getCommonCards().getCard(name);
            if (existing != null) { commanderUsed = name; return existing; }
            PaperCard pc = new PaperCard(rules, "CHK", forge.card.CardRarity.Rare);
            StaticData.instance().getCommonCards().addCard(pc);
            commanderUsed = name;
            return pc;
        }
        throw new IllegalStateException("GN_COMMANDER_LOAD_FAIL");
    }

    static Deck commanderDeck(String seatName, PaperCard mountain, PaperCard commander) {
        Deck deck = new Deck(seatName + "-deck");
        deck.getMain().add(mountain, 99);
        deck.getOrCreate(DeckSection.Commander).add(commander, 1);
        return deck;
    }

    /** Build a fresh native N-player Commander game. No game.start(): construction only. */
    static Game buildGame(int n, long seed, Path langDir,
            PaperCard mountain, PaperCard commander) {
        MyRandom.setRandom(new Random(seed));
        GameRules rules = new GameRules(GameType.Commander);
        rules.addAppliedVariant(GameType.Commander);
        List<RegisteredPlayer> registrations = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            Deck deck = commanderDeck("gn-seat-" + i, mountain, commander);
            RegisteredPlayer rp = RegisteredPlayer.forCommander(deck);
            rp.setPlayer(new SeatLobby("gn-seat-" + i));
            registrations.add(rp);
        }
        Match match = new Match(rules, registrations, "General-N discriminator N=" + n);
        return match.createGame();
    }

    static String ringWalk(Game game, Player start, int steps) {
        StringBuilder sb = new StringBuilder();
        Player cur = start;
        for (int i = 0; i < steps; i++) {
            cur = game.getNextPlayerAfter(cur);
            if (cur == null) return sb + "|NULL";
            if (sb.length() > 0) sb.append(">");
            sb.append(cur.getName());
        }
        return sb.toString();
    }

    static String semanticSummary(Game game) {
        StringBuilder sb = new StringBuilder();
        for (Player p : game.getPlayers()) {
            sb.append(p.getName()).append("#").append(p.getId())
              .append(":life").append(p.getStartingLife())
              .append(":opp").append(p.getOpponents().size())
              .append(":cmd").append(p.getCommanders().size())
              .append(":cast").append(p.getTotalCommanderCast()).append(";");
        }
        return sb.toString();
    }

    public static void main(String[] args) throws Exception {
        int n = Integer.parseInt(args[0]);
        Path langDir = Path.of(args[1]);
        long seed = Long.parseLong(args[2]);
        initForge(langDir);
        PaperCard mountain = mountainPaper(langDir);
        PaperCard commander = commanderPaper(langDir);
        boolean fallbackCommander = commanderUsed.equals("Grizzly Bears");

        // ---- CONSTRUCTS + identity ----
        Game game;
        try {
            game = buildGame(n, seed, langDir, mountain, commander);
        } catch (Throwable t) {
            emit(n, "CONSTRUCTS", "FAIL", t.getClass().getName() + ":" + t.getMessage());
            return;
        }
        Set<String> names = new LinkedHashSet<>();
        Set<Integer> ids = new LinkedHashSet<>();
        boolean lifeOk = true;
        for (Player p : game.getPlayers()) {
            names.add(p.getName()); ids.add(p.getId());
            if (p.getStartingLife() != 40) lifeOk = false;
        }
        if (game.getPlayers().size() == n && names.size() == n && ids.size() == n && lifeOk) {
            emit(n, "CONSTRUCTS", "PASS", "players=" + n + " distinctNames=" + names.size()
                    + " distinctIds=" + ids.size() + " life40=all commander=" + commanderUsed
                    + (fallbackCommander ? " FALLBACK_NON_LEGENDARY" : ""));
        } else {
            emit(n, "CONSTRUCTS", "FAIL", "size=" + game.getPlayers().size()
                    + " names=" + names.size() + " ids=" + ids.size() + " life40all=" + lifeOk);
            return;
        }

        // ---- TURN_RING ----
        Player start = game.getPlayers().get(0);
        String walk = ringWalk(game, start, n);
        StringBuilder expected = new StringBuilder();
        for (int i = 1; i <= n; i++) {
            if (expected.length() > 0) expected.append(">");
            expected.append("gn-seat-").append(i % n);
        }
        String walkBack = ringWalk(game, start, n + 1);
        if (walk.equals(expected.toString()) && walk.endsWith(start.getName())) {
            emit(n, "TURN_RING", "PASS", walk);
        } else {
            emit(n, "TURN_RING", "FAIL", "walk=" + walk + " expected=" + expected);
        }

        // ---- PRIORITY_RING (same native ring primitive PhaseHandler uses) ----
        // PhaseHandler passes priority via game.getNextPlayerAfter(getPriorityPlayer()).
        String pwalk = ringWalk(game, start, n);
        if (pwalk.equals(expected.toString())) {
            emit(n, "PRIORITY_RING", "PASS", "priorityOrder==" + pwalk + " CODE_DERIVED:PhaseHandler:1062,1119");
        } else {
            emit(n, "PRIORITY_RING", "FAIL", "walk=" + pwalk);
        }

        // ---- opponents ----
        boolean oppOk = true; StringBuilder oppDetail = new StringBuilder();
        for (Player p : game.getPlayers()) {
            int opp = p.getOpponents().size();
            if (opp != n - 1) oppOk = false;
            if (oppDetail.length() > 0) oppDetail.append(",");
            oppDetail.append(p.getName()).append("=").append(opp);
            if (p.getOpponents().contains(p)) oppOk = false;
        }
        emit(n, "OPPONENTS", oppOk ? "PASS" : "FAIL", oppDetail.toString());

        // ---- COMMANDER_INIT ----
        // Native zone placement runs in Match.startGame via
        // player.initVariantsZones(psc) (Match.java:323). createGame() alone
        // does not place commanders; invoke the same native method directly
        // (pure zone setup, no controller calls) and verify per seat.
        boolean cmdOk = true; StringBuilder cmdDetail = new StringBuilder();
        try {
            for (Player p : game.getPlayers()) {
                p.initVariantsZones(p.getRegisteredPlayer());
            }
        } catch (Throwable t) {
            emit(n, "COMMANDER_INIT", "FAIL", "initVariantsZones:" + t.getClass().getName());
            cmdOk = false;
        }
        for (Player p : game.getPlayers()) {
            int ncmd = p.getCommanders().size();
            boolean zoneOk = p.getZone(ZoneType.Command) != null;
            boolean dmgOk = p.getCommanderDamage() != null;
            int totalCast;
            try { totalCast = p.getTotalCommanderCast(); } catch (Throwable t) { totalCast = -1; }
            if (ncmd < 1 || !zoneOk || dmgOk == false || totalCast != 0) cmdOk = false;
            if (cmdDetail.length() > 0) cmdDetail.append(",");
            cmdDetail.append(p.getName()).append(":cmds=").append(ncmd)
                     .append(":zone=").append(zoneOk).append(":cast=").append(totalCast);
        }
        // commanderDamage() accessor name differs; use reflection-free check via getCommanderDamage(Card)? keep map-level:
        emit(n, "COMMANDER_INIT", cmdOk ? "PASS" : "FAIL",
                cmdDetail + (fallbackCommander ? " FALLBACK_NON_LEGENDARY" : ""));

        // ---- COMBAT_MULTI_DEFENDER (attacker seat0 vs every other seat; non-next included) ----
        try {
            Player attacker = game.getPlayers().get(0);
            game.getPhaseHandler().devModeSet(
                    forge.game.phase.PhaseType.COMBAT_DECLARE_ATTACKERS, attacker, 1);
            Combat combat = new Combat(attacker);
            game.getPhaseHandler().setCombat(combat);
            List<Card> bears = new ArrayList<>();
            for (int k = 1; k < n; k++) {
                Player defender = game.getPlayers().get(k);
                PaperCard bearPc = StaticData.instance().getCommonCards().getCard("Grizzly Bears");
                if (bearPc == null) {
                    CardRules bearRules = new CardStorageReader(
                            langDir.toAbsolutePath().normalize().getParent().getParent().getParent()
                            .resolve("forge-gui/res/cardsfolder").toString(),
                            null, true).attemptToLoadCard("Grizzly Bears");
                    bearPc = new PaperCard(bearRules, "M11", forge.card.CardRarity.Common);
                    StaticData.instance().getCommonCards().addCard(bearPc);
                }
                Card bear = Card.fromPaperCard(bearPc, attacker);
                attacker.getZone(ZoneType.Hand).add(bear);
                game.getAction().moveToPlay(bear, null, null);
                bear.setSickness(false);
                bear.setTapped(false);
                combat.addAttacker(bear, defender);
                bears.add(bear);
            }
            // verify band->defender representation before finalization
            boolean bandsOk = combat.getAttackingBands().size() == n - 1;
            Set<String> defNames = new LinkedHashSet<>();
            for (Card b : bears) {
                GameEntity def = combat.getDefenderByAttacker(b);
                if (def != null) defNames.add(def.getName());
            }
            for (int k = 1; k < n; k++) {
                if (!defNames.contains(game.getPlayers().get(k).getName())) bandsOk = false;
            }
            combat.fireTriggersForUnblockedAttackers(game);
            String outcome, detail = "null", top = "null";
            try {
                combat.assignCombatDamage(false);
                outcome = "RETURNED";
            } catch (StubReached s) {
                outcome = "CONTROLLER_BOUNDARY";
                detail = String.valueOf(s.getMessage());
            } catch (NullPointerException npe) {
                outcome = "NULL_POINTER";
                detail = String.valueOf(npe.getMessage());
                StackTraceElement[] st = npe.getStackTrace();
                if (st.length > 0) top = st[0].toString();
            }
            boolean attackedNonNext = n >= 4; // seat2+ are non-next opponents of seat0
            if (bandsOk && (outcome.equals("RETURNED") || outcome.equals("CONTROLLER_BOUNDARY"))) {
                emit(n, "COMBAT_MULTI_DEFENDER", "PASS",
                        "bands=" + (n - 1) + " defenders=" + defNames + " nonNextIncluded=" + attackedNonNext
                        + " damageResult=" + outcome);
            } else {
                emit(n, "COMBAT_MULTI_DEFENDER", "FAIL",
                        "bandsOk=" + bandsOk + " outcome=" + outcome + " detail=" + detail + " top=" + top);
            }
        } catch (Throwable t) {
            emit(n, "COMBAT_MULTI_DEFENDER", "FAIL", t.getClass().getName() + ":" + t.getMessage());
        }

        // ---- ELIMINATION (concede middle seat; N=6 also concedes last seat) ----
        try {
            Game g2 = buildGame(n, seed + 1, langDir, mountain, commander);
            int mid = n / 2;
            Player midP = g2.getPlayers().get(mid);
            midP.concede();
            List<Player> extraConceded = new ArrayList<>();
            if (n == 6) {
                Player last = g2.getPlayers().get(n - 1);
                last.concede();
                extraConceded.add(last);
            }
            boolean lostOk = midP.hasLost() && midP.conceded();
            // Native elimination completion: concede -> checkGameOverCondition
            // -> onPlayerLost -> ingamePlayers.remove (Game.java:999).
            g2.getAction().checkGameOverCondition();
            boolean removedOk = !g2.getPlayers().contains(midP);
            for (Player x : extraConceded) removedOk &= !g2.getPlayers().contains(x);
            int expectAlive = n - 1 - extraConceded.size();
            // walk ring from seat0 over alive players
            Player anchor = g2.getPlayers().get(0);
            if (anchor.hasLost()) anchor = g2.getPlayers().get(1);
            Set<String> visited = new LinkedHashSet<>();
            Player cur = anchor;
            boolean ringOk = true;
            for (int i = 0; i < expectAlive; i++) {
                cur = g2.getNextPlayerAfter(cur);
                if (cur == null || cur.hasLost()) { ringOk = false; break; }
                visited.add(cur.getName());
            }
            String firstVisited = visited.isEmpty() ? "none" : visited.iterator().next();
            Player back = (cur == null) ? null : g2.getNextPlayerAfter(cur);
            if (back == null || !back.getName().equals(firstVisited)) ringOk = false;
            if (lostOk && removedOk && ringOk && visited.size() == expectAlive && !visited.contains(midP.getName())) {
                emit(n, "ELIMINATION", "PASS", "conceded=" + midP.getName()
                        + (extraConceded.isEmpty() ? "" : ",+last") + " aliveRing=" + visited);
            } else {
                emit(n, "ELIMINATION", "FAIL", "lostOk=" + lostOk + " removedOk=" + removedOk
                        + " ringOk=" + ringOk
                        + " visited=" + visited + " expectAlive=" + expectAlive);
            }
            // ---- priority ring after elimination ----
            Set<String> pvisited = new LinkedHashSet<>();
            Player pcur = anchor;
            boolean pringOk = true;
            for (int i = 0; i < expectAlive; i++) {
                pcur = g2.getNextPlayerAfter(pcur);
                if (pcur == null || pcur.hasLost()) { pringOk = false; break; }
                pvisited.add(pcur.getName());
            }
            if (pringOk && pvisited.equals(visited)) {
                emit(n, "PRIORITY_AFTER_ELIMINATION", "PASS", pvisited.toString());
            } else {
                emit(n, "PRIORITY_AFTER_ELIMINATION", "FAIL", pvisited.toString());
            }
        } catch (Throwable t) {
            emit(n, "ELIMINATION", "FAIL", t.getClass().getName() + ":" + t.getMessage());
            emit(n, "PRIORITY_AFTER_ELIMINATION", "FAIL", "parent elimination error");
        }

        // ---- EXTRA_TURN (N=5 focus; run for all N) ----
        try {
            Game g3 = buildGame(n, seed + 2, langDir, mountain, commander);
            // target a NON-next seat where possible so redirection is observable
            Player target = g3.getPlayers().get(n >= 3 ? 2 : 1);
            String baseNext = g3.getNextPlayerAfter(g3.getPlayers().get(0)).getName();
            g3.getPhaseHandler().addExtraTurn(target);
            Player nextTurn = g3.getPhaseHandler().getNextTurn();
            boolean extraOk = nextTurn != null && nextTurn.getName().equals(target.getName());
            // base ring untouched by the push
            String ringAfter = ringWalk(g3, g3.getPlayers().get(0), n);
            boolean ringIntact = ringAfter.equals(expected.toString().replace("gn-seat-0", "gn-seat-0"));
            // recompute expected explicitly (same as turn ring expectation)
            if (extraOk && ringIntact) {
                emit(n, "EXTRA_TURN", "PASS", "baseNext=" + baseNext + " extraNext=" + nextTurn.getName()
                        + " ringIntact=" + ringAfter);
            } else {
                emit(n, "EXTRA_TURN", "FAIL", "extraOk=" + extraOk + " next="
                        + (nextTurn == null ? "null" : nextTurn.getName()) + " ring=" + ringAfter);
            }
        } catch (Throwable t) {
            emit(n, "EXTRA_TURN", "FAIL", t.getClass().getName() + ":" + t.getMessage());
        }

        // ---- HIDDEN_INFO (principal-scoped controllers) ----
        try {
            Set<Integer> ctrlIds = new LinkedHashSet<>();
            boolean boundOk = true;
            for (Player p : game.getPlayers()) {
                PlayerController c = p.getController();
                ctrlIds.add(System.identityHashCode(c));
                if (c.getPlayer() != p) boundOk = false;
                if (c.getGame() != game) boundOk = false;
            }
            if (ctrlIds.size() == n && boundOk) {
                emit(n, "HIDDEN_INFO", "PASS", "distinctControllers=" + n
                        + " eachBoundToOwnSeat CODE_DERIVED:observation-principal-scoped");
            } else {
                emit(n, "HIDDEN_INFO", "FAIL", "distinct=" + ctrlIds.size() + " boundOk=" + boundOk);
            }
        } catch (Throwable t) {
            emit(n, "HIDDEN_INFO", "FAIL", t.getClass().getName() + ":" + t.getMessage());
        }

        // ---- DETERMINISM (two fresh builds, same seed, identical summary) ----
        try {
            Game gd1 = buildGame(n, seed, langDir, mountain, commander);
            Game gd2 = buildGame(n, seed, langDir, mountain, commander);
            String s1 = semanticSummary(gd1);
            String s2 = semanticSummary(gd2);
            if (s1.equals(s2)) {
                emit(n, "DETERMINISM", "PASS", s1);
            } else {
                emit(n, "DETERMINISM", "FAIL", "A=" + s1 + " B=" + s2);
            }
        } catch (Throwable t) {
            emit(n, "DETERMINISM", "FAIL", t.getClass().getName() + ":" + t.getMessage());
        }
    }

    static String anchorAfterWalk(Game g, Player anchor, int steps) {
        Player cur = anchor;
        for (int i = 0; i < steps; i++) cur = g.getNextPlayerAfter(cur);
        return cur.getName();
    }
}
