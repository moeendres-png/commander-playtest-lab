package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import mage.MageObject;
import mage.cards.Card;
import mage.constants.WatcherScope;
import mage.game.Game;
import mage.game.events.DamagedPlayerEvent;
import mage.game.events.GameEvent;
import mage.game.events.ZoneChangeEvent;
import mage.game.permanent.Permanent;
import mage.players.Player;
import mage.watchers.Watcher;

import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * WS60 test-side inert observation taper.
 *
 * <p>Records engine-native game events for qualification evidence. The taper
 * creates no Rules semantics: it is a {@link Watcher} subclass unknown to all
 * card implementations (no card queries it), it never modifies game state, it
 * never throws (all extraction is defensive), and {@link #copy()} returns an
 * inert instance so simulation copies never append to a live tape.</p>
 *
 * <p>Entries whose firing game instance is not the registered live game are
 * ignored, so playable-calculation simulations cannot pollute the tape.</p>
 */
final class Ws60EventTape extends Watcher {

    private static final Set<GameEvent.EventType> SUBSCRIBED = EnumSet.of(
            GameEvent.EventType.DIE_ROLLED,
            GameEvent.EventType.DICE_ROLLED,
            GameEvent.EventType.TRIGGERED_ABILITY,
            GameEvent.EventType.DAMAGED_PLAYER,
            GameEvent.EventType.COUNTERED,
            GameEvent.EventType.ZONE_CHANGE
    );

    private final List<JsonObject> entries = new ArrayList<>();
    private Game liveGame;
    private long sequence;

    Ws60EventTape() {
        super(WatcherScope.GAME);
    }

    void arm(Game game) {
        if (game == null) {
            throw new IllegalArgumentException("live game is required");
        }
        this.liveGame = game;
    }

    @Override
    public void watch(GameEvent event, Game game) {
        try {
            record(event, game);
        } catch (RuntimeException ignored) {
            // Observation must never perturb the Rules Core.
        }
    }

    private synchronized void record(GameEvent event, Game game) {
        if (event == null || game == null || liveGame == null) {
            return;
        }
        if (game != liveGame) {
            return;
        }
        if (!SUBSCRIBED.contains(event.getType())) {
            return;
        }
        JsonObject entry = new JsonObject();
        entry.addProperty("seq", ++sequence);
        entry.addProperty("type", event.getType().name());
        try {
            entry.addProperty("turn", game.getState().getTurnNum());
        } catch (RuntimeException ignored) {
            entry.addProperty("turn", -1);
        }
        putName(entry, "player", nameOf(game, event.getPlayerId()));
        putName(entry, "source", nameOf(game, event.getSourceId()));
        putName(entry, "target", nameOf(game, event.getTargetId()));
        String amount = eventAmount(event);
        if (amount != null) {
            entry.addProperty("amount", amount);
        }
        String zoneInfo = zoneInfo(event);
        if (zoneInfo != null) {
            entry.addProperty("zones", zoneInfo);
        }
        entries.add(entry);
    }

    private static void putName(JsonObject entry, String key, String name) {
        if (name != null && !name.isBlank()) {
            entry.addProperty(key + "_name", name);
        }
    }

    private static String nameOf(Game game, UUID id) {
        if (id == null) {
            return null;
        }
        try {
            Player player = game.getPlayer(id);
            if (player != null) {
                return "player:" + player.getName();
            }
            Permanent permanent = game.getPermanent(id);
            if (permanent != null) {
                return "permanent:" + permanent.getName();
            }
            Card card = game.getCard(id);
            if (card != null) {
                return "card:" + card.getName();
            }
            MageObject object = game.getObject(id);
            if (object != null) {
                return "object:" + object.getName();
            }
        } catch (RuntimeException ignored) {
            return null;
        }
        return null;
    }

    private static String eventAmount(GameEvent event) {
        try {
            if (event instanceof DamagedPlayerEvent damaged) {
                return damaged.getAmount() + (damaged.isCombatDamage() ? " combat" : " noncombat");
            }
            return "amount=" + event.getAmount();
        } catch (RuntimeException ignored) {
            return null;
        }
    }

    private static String zoneInfo(GameEvent event) {
        try {
            if (!(event instanceof ZoneChangeEvent zoneChange)) {
                return null;
            }
            String from = zoneChange.getFromZone() == null ? "?" : zoneChange.getFromZone().name();
            String to = zoneChange.getToZone() == null ? "?" : zoneChange.getToZone().name();
            return from + "->" + to;
        } catch (RuntimeException ignored) {
            return null;
        }
    }

    synchronized List<JsonObject> entries() {
        List<JsonObject> copy = new ArrayList<>(entries.size());
        for (JsonObject entry : entries) {
            copy.add(entry.deepCopy());
        }
        return copy;
    }

    synchronized int size() {
        return entries.size();
    }

    /**
     * Exports the tape. Names were resolved eagerly at event time (twin
     * stable); this copy is a straight snapshot for evidence.
     */
    synchronized JsonArray export() {
        JsonArray out = new JsonArray();
        for (JsonObject entry : entries) {
            out.add(entry.deepCopy());
        }
        return out;
    }

    @Override
    public Ws60EventTape copy() {
        // Inert: simulation copies must never append to any live tape.
        return new Ws60EventTape();
    }
}
