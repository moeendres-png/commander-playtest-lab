package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.MageObject;
import mage.cards.Card;
import mage.constants.WatcherScope;
import mage.constants.Zone;
import mage.game.Game;
import mage.game.events.DamagedEvent;
import mage.game.events.GameEvent;
import mage.game.events.ZoneChangeEvent;
import mage.game.permanent.Permanent;
import mage.watchers.Watcher;

import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * The public semantic event tape of one restored game.
 *
 * <p>A native XMage watcher: it observes the engine's own {@link GameEvent}s and
 * records the publicly observable facts of a bounded set of event types. Its
 * list is part of the game state, so an engine rollback (for example an
 * aborted cast) rolls the tape back with it. It records native ids only; the
 * lane translates them to seats and semantic ids when the tape is read.</p>
 *
 * <p>Hidden information never enters the tape: a zone change whose origin and
 * destination are both hidden (a draw, a card put into a library) records
 * only its owner and zones, never the card's identity. A card moved from a
 * hidden zone into exile is named only once it is known to have stayed face up
 * there (see {@link #settle}). Every other recorded object is public at the
 * time of the event.</p>
 */
final class XmagePublicEventWatcher extends Watcher {

    private static final Set<GameEvent.EventType> RECORDED = EnumSet.of(
            GameEvent.EventType.ZONE_CHANGE,
            GameEvent.EventType.SPELL_CAST,
            GameEvent.EventType.COUNTERED,
            GameEvent.EventType.COPIED_STACKOBJECT,
            GameEvent.EventType.TRIGGERED_ABILITY,
            GameEvent.EventType.DAMAGED_PLAYER,
            GameEvent.EventType.DAMAGED_PERMANENT,
            GameEvent.EventType.PREVENTED_DAMAGE,
            GameEvent.EventType.GAINED_LIFE,
            GameEvent.EventType.LOST_LIFE,
            GameEvent.EventType.LOST,
            GameEvent.EventType.WINS,
            GameEvent.EventType.DRAW_PLAYER,
            GameEvent.EventType.ATTACKER_DECLARED,
            GameEvent.EventType.BLOCKER_DECLARED,
            GameEvent.EventType.CREATED_TOKEN,
            GameEvent.EventType.COUNTER_ADDED,
            GameEvent.EventType.DESTROYED_PERMANENT,
            GameEvent.EventType.SACRIFICED_PERMANENT,
            GameEvent.EventType.GAINED_CONTROL,
            GameEvent.EventType.COIN_FLIPPED,
            GameEvent.EventType.EXTRA_TURN,
            GameEvent.EventType.BEGIN_TURN,
            GameEvent.EventType.LIBRARY_SHUFFLED
    );

    private static final Set<Zone> PUBLIC_ZONES = EnumSet.of(
            Zone.BATTLEFIELD, Zone.GRAVEYARD, Zone.EXILED, Zone.STACK, Zone.COMMAND);

    private List<String> events = new ArrayList<>();

    /**
     * Zone changes from a hidden zone into exile whose card identity is not yet
     * decided, as {@code "index|cardId|zoneChangeCounter"}.
     *
     * <p>XMage effects that exile a card face down (Gonti, Lord of Luxury; Kheru
     * Mind-Eater; Bane Alley Broker) move the card and turn it face down only
     * after the move, so at the instant of the event the card still reads face
     * up. A card exiled face down is shown to nobody but the players an effect
     * lets look at it (CR 406.3), so such a move stays unnamed until the card
     * is known to have stayed face up in that exile. Strings keep the list
     * copyable with the rest of the game state.</p>
     */
    private List<String> pendingExile = new ArrayList<>();

    XmagePublicEventWatcher() {
        super(WatcherScope.GAME);
    }

    @Override
    public void watch(GameEvent event, Game game) {
        if (!RECORDED.contains(event.getType())) {
            return;
        }
        JsonObject record = new JsonObject();
        record.addProperty("type", event.getType().name());
        record.addProperty("turn", game.getTurnNum());
        record.addProperty("step", game.getTurnStepType() == null ? null : game.getTurnStepType().name());
        put(record, "player", event.getPlayerId());
        put(record, "target", event.getTargetId());
        put(record, "source", event.getSourceId());
        record.addProperty("amount", event.getAmount());
        record.addProperty("flag", event.getFlag());
        if (event.getData() != null && !event.getData().isEmpty()) {
            record.addProperty("data", event.getData());
        }
        boolean publicIdentity = true;
        boolean pending = false;
        if (event instanceof ZoneChangeEvent zoneChange) {
            record.addProperty("from", zoneChange.getFromZone().name());
            record.addProperty("to", zoneChange.getToZone().name());
            boolean faceDown = zoneChange.getTarget() != null && zoneChange.getTarget().isFaceDown(game);
            publicIdentity = !faceDown
                    && (PUBLIC_ZONES.contains(zoneChange.getFromZone())
                    || PUBLIC_ZONES.contains(zoneChange.getToZone()));
            // A card leaving a hidden zone for exile may be turned face down by
            // the moving effect right after this event: its identity is decided
            // once that effect has finished (settle).
            if (publicIdentity && zoneChange.getToZone() == Zone.EXILED
                    && !PUBLIC_ZONES.contains(zoneChange.getFromZone())) {
                publicIdentity = false;
                pending = true;
            }
        }
        if (event instanceof DamagedEvent damaged) {
            record.addProperty("combat", damaged.isCombatDamage());
        }
        record.addProperty("public_identity", publicIdentity);
        boolean sourceIsTarget = event.getSourceId() != null && event.getSourceId().equals(event.getTargetId());
        if (event instanceof ZoneChangeEvent) {
            // The moved card is named only with a public identity. The effect's
            // source is another object, named whenever it is public itself; a
            // card that moves itself shares the moved card's identity.
            record.addProperty("target_hidden", !publicIdentity);
            record.addProperty("source_hidden",
                    sourceIsTarget ? !publicIdentity : hiddenObject(event.getSourceId(), game));
        } else {
            // Any other event may name an object whose identity is hidden right
            // now (a face-down permanent, a card in a hidden zone): it is named
            // by neither its card name nor the semantic object it was requested as.
            record.addProperty("target_hidden", hiddenObject(event.getTargetId(), game));
            record.addProperty("source_hidden", hiddenObject(event.getSourceId(), game));
        }
        if (publicIdentity) {
            // A zone change was public before or after the move; any other event
            // names only objects that are in a public zone now.
            boolean requirePublicZone = !(event instanceof ZoneChangeEvent);
            putName(record, "target_name", event.getTargetId(), game, requirePublicZone);
            putName(record, "source_name", event.getSourceId(), game, true);
        } else if (event instanceof ZoneChangeEvent && !sourceIsTarget) {
            putName(record, "source_name", event.getSourceId(), game, true);
        }
        events.add(record.toString());
        if (pending) {
            Card card = game.getCard(event.getTargetId());
            pendingExile.add((events.size() - 1) + "|" + event.getTargetId() + "|"
                    + (card == null ? -1 : card.getZoneChangeCounter(game)));
        }
    }

    /**
     * Decides the identity of every pending move into exile from the current
     * state.
     *
     * <p>The lane calls this when the tape is read, which happens between
     * engine decisions, after the effect that made the move has finished. A
     * card that stayed face up in that exile is public and is named. A card that
     * is face down there, or that has left that exile since, stays unnamed:
     * nothing shows it was ever public.</p>
     */
    void settle(Game game) {
        for (String entry : pendingExile) {
            String[] parts = entry.split("\\|");
            int index = Integer.parseInt(parts[0]);
            UUID cardId = UUID.fromString(parts[1]);
            int zoneChangeCounter = Integer.parseInt(parts[2]);
            Card card = game.getCard(cardId);
            if (card == null || card.isFaceDown(game)
                    || game.getState().getZone(cardId) != Zone.EXILED
                    || card.getZoneChangeCounter(game) != zoneChangeCounter) {
                continue;
            }
            JsonObject record = JsonParser.parseString(events.get(index)).getAsJsonObject();
            record.addProperty("public_identity", true);
            record.addProperty("target_hidden", false);
            putName(record, "target_name", cardId, game, false);
            if (record.has("source") && cardId.toString().equals(record.get("source").getAsString())) {
                record.addProperty("source_hidden", false);
                putName(record, "source_name", cardId, game, true);
            }
            events.set(index, record.toString());
        }
        pendingExile.clear();
    }

    int size() {
        return events.size();
    }

    /** The recorded events after {@code afterOffset} (a 0-based count), in engine order. */
    List<JsonObject> eventsAfter(int afterOffset) {
        List<JsonObject> selected = new ArrayList<>();
        for (int index = Math.max(0, afterOffset); index < events.size(); index++) {
            JsonObject event = JsonParser.parseString(events.get(index)).getAsJsonObject();
            event.addProperty("sequence", index + 1);
            selected.add(event);
        }
        return selected;
    }

    private static void put(JsonObject record, String key, java.util.UUID id) {
        if (id != null) {
            record.addProperty(key, id.toString());
        }
    }

    private static boolean hiddenObject(java.util.UUID id, Game game) {
        if (id == null || game.getPlayer(id) != null) {
            return false;
        }
        Permanent permanent = game.getPermanentOrLKIBattlefield(id);
        if (permanent != null && permanent.isFaceDown(game)) {
            return true;
        }
        Zone zone = game.getState().getZone(id);
        if (faceDownInExile(id, zone, game)) {
            return true;
        }
        return zone != null && !PUBLIC_ZONES.contains(zone);
    }

    /** Exile is a public zone, but a card exiled face down is not public (CR 406.3). */
    private static boolean faceDownInExile(java.util.UUID id, Zone zone, Game game) {
        if (zone != Zone.EXILED) {
            return false;
        }
        Card card = game.getCard(id);
        return card != null && card.isFaceDown(game);
    }

    private static void putName(
            JsonObject record, String key, java.util.UUID id, Game game, boolean requirePublicZone) {
        if (id == null || game.getPlayer(id) != null) {
            return;
        }
        Zone zone = game.getState().getZone(id);
        if (requirePublicZone && zone != null && !PUBLIC_ZONES.contains(zone)) {
            return;
        }
        if (faceDownInExile(id, zone, game)) {
            return;
        }
        MageObject object = game.getObject(id);
        if (object == null) {
            Permanent permanent = game.getPermanentOrLKIBattlefield(id);
            object = permanent;
        }
        if (object != null && !(object instanceof Permanent permanent && permanent.isFaceDown(game))) {
            record.addProperty(key, object.getName());
        }
    }
}
