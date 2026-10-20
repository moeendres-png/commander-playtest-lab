package org.commanderlab.xmage;

import mage.constants.CommanderCardType;
import mage.counters.Counter;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.game.stack.StackObject;
import mage.players.Player;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * Digest of the engine-held facts a cast or an activation changes while it is
 * being proposed: whose turn and step it is, each player's life, mana pool,
 * hand, graveyard, library size, lands played and commander zones, the exile
 * zone, every permanent's controller, tapped state, damage and counters, and
 * the stack.
 *
 * <p>It exists to prove one thing: that the engine's own rewind (CR 727,
 * "Handling Illegal Actions"; {@code PlayerImpl.cast} and {@code playAbility}
 * restore their bookmark whenever {@code activate} returns false) put the game
 * back exactly where it was before the action was proposed. Two digests taken
 * before and after a failed action are equal only when nothing in this list
 * changed. It does not recompute legality and never decides anything for the
 * player: it reads facts the engine already holds.
 *
 * <p>The digest is a one-way SHA-256 over object ids and counts. It stays in
 * the bridge process and is never written to a frame, an event log or an
 * error, so it adds no hidden information to any output.
 *
 * <p>Coverage is the list above and nothing else. A change outside it (a
 * watcher counter, a replacement-effect flag) is not seen, which is why
 * this is evidence for "the engine rewound" and is only ever combined with
 * a predicate that names WHICH step the engine could not complete (an
 * unfillable cost or ability target), never a proof by itself that a failed
 * action was harmless or that the engine is healthy.
 */
final class XmageStateFingerprint {

    private XmageStateFingerprint() {
    }

    /**
     * As {@link #of}, or {@code null} when the digest cannot be taken. A
     * failure here must never end a game that would otherwise go on: a {@code
     * null} start state makes every predicate that needs the rewind proof
     * answer false, i.e. the failure it was asked about stays a failure.
     */
    static String ofOrNull(Game game) {
        try {
            return of(game);
        } catch (RuntimeException unreadable) {
            return null;
        }
    }

    static String of(Game game) {
        StringBuilder out = new StringBuilder(4096);
        out.append("turn=").append(game.getTurnNum())
                .append(";phase=").append(game.getTurnPhaseType())
                .append(";step=").append(game.getStep() == null ? null : game.getStep().getType())
                .append(";active=").append(game.getActivePlayerId())
                .append(";priority=").append(game.getPriorityPlayerId())
                .append('\n');
        List<UUID> playerIds = new ArrayList<>(game.getPlayers().keySet());
        playerIds.sort(Comparator.naturalOrder());
        for (UUID playerId : playerIds) {
            Player player = game.getPlayer(playerId);
            if (player == null) {
                continue;
            }
            out.append("player=").append(playerId)
                    .append(";inGame=").append(player.isInGame())
                    .append(";life=").append(player.getLife())
                    .append(";lands=").append(player.getLandsPlayed())
                    .append(";counters=").append(player.getCountersAsCopy().getTotalCount())
                    .append(";pool=").append(player.getManaPool().getMana())
                    .append('+').append(player.getManaPool().getConditionalMana().size())
                    .append(";library=").append(player.getLibrary().size())
                    .append(";hand=").append(ids(player.getHand()))
                    .append(";graveyard=").append(ids(player.getGraveyard()))
                    .append(";commanders=");
            for (UUID commander : sorted(
                    game.getCommandersIds(player, CommanderCardType.ANY, true))) {
                out.append(commander).append('@').append(game.getState().getZone(commander)).append(',');
            }
            out.append('\n');
        }
        out.append("exile=");
        for (UUID id : sorted(game.getExile().getAllCards(game).stream()
                .map(card -> card.getId()).collect(Collectors.toList()))) {
            out.append(id).append(',');
        }
        out.append('\n');
        List<Permanent> permanents = new ArrayList<>(game.getBattlefield().getAllActivePermanents());
        permanents.sort(Comparator.comparing(Permanent::getId));
        for (Permanent permanent : permanents) {
            out.append("perm=").append(permanent.getId())
                    .append(";controller=").append(permanent.getControllerId())
                    .append(";tapped=").append(permanent.isTapped())
                    .append(";damage=").append(permanent.getDamage())
                    .append(";phasedIn=").append(permanent.isPhasedIn())
                    .append(";transformed=").append(permanent.isTransformed())
                    .append(";attachedTo=").append(permanent.getAttachedTo())
                    .append(";counters=").append(counters(permanent, game))
                    .append('\n');
        }
        out.append("stack=");
        for (StackObject stackObject : game.getStack()) {
            out.append(stackObject.getId()).append(',');
        }
        return sha256(out.toString());
    }

    private static String ids(Collection<UUID> cards) {
        StringBuilder out = new StringBuilder();
        for (UUID id : sorted(cards)) {
            out.append(id).append(',');
        }
        return out.toString();
    }

    private static List<UUID> sorted(Collection<UUID> ids) {
        List<UUID> copy = new ArrayList<>(ids);
        copy.sort(Comparator.naturalOrder());
        return copy;
    }

    private static String counters(Permanent permanent, Game game) {
        Map<String, Integer> byName = new TreeMap<>();
        for (Counter counter : permanent.getCounters(game).values()) {
            byName.put(counter.getName(), counter.getCount());
        }
        return byName.toString();
    }

    private static String sha256(String text) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(text.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder(digest.length * 2);
            for (byte b : digest) {
                hex.append(String.format("%02x", b));
            }
            return hex.toString();
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("SHA-256 is required of every JVM", impossible);
        }
    }
}
