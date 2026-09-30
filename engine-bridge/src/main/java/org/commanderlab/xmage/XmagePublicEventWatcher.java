package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import mage.MageObject;
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
 * only its owner and zones, never the card's identity. Every other recorded
 * object is public at the time of the event.</p>
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
        if (event instanceof ZoneChangeEvent zoneChange) {
            record.addProperty("from", zoneChange.getFromZone().name());
            record.addProperty("to", zoneChange.getToZone().name());
            boolean faceDown = zoneChange.getTarget() != null && zoneChange.getTarget().isFaceDown(game);
            publicIdentity = !faceDown
                    && (PUBLIC_ZONES.contains(zoneChange.getFromZone())
                    || PUBLIC_ZONES.contains(zoneChange.getToZone()));
        }
        if (event instanceof DamagedEvent damaged) {
            record.addProperty("combat", damaged.isCombatDamage());
        }
        record.addProperty("public_identity", publicIdentity);
        if (publicIdentity) {
            // A zone change was public before or after the move; any other event
            // names only objects that are in a public zone now.
            boolean requirePublicZone = !(event instanceof ZoneChangeEvent);
            putName(record, "target_name", event.getTargetId(), game, requirePublicZone);
            putName(record, "source_name", event.getSourceId(), game, true);
        }
        events.add(record.toString());
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

    private static void putName(
            JsonObject record, String key, java.util.UUID id, Game game, boolean requirePublicZone) {
        if (id == null || game.getPlayer(id) != null) {
            return;
        }
        Zone zone = game.getState().getZone(id);
        if (requirePublicZone && zone != null && !PUBLIC_ZONES.contains(zone)) {
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
