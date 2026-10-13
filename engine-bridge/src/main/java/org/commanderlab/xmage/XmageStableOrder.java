package org.commanderlab.xmage;

import mage.abilities.Ability;
import mage.cards.Card;
import mage.constants.Zone;
import mage.counters.Counter;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.game.stack.StackObject;
import mage.players.Player;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import java.util.regex.Pattern;

/**
 * Twin-stable ordering shared by the XMage lanes (WS92-D5, F-36): decision frames are
 * sequenced by Rules-visible content, never by native UUIDs, which are random per game.
 */
final class XmageStableOrder {

    private XmageStableOrder() {
    }

    /**
     * F-36 (WS92-D5 extended to every object a decision offers): targets, cards to choose,
     * defenders and attackers are ordered by Rules-visible, twin-stable content, never by
     * native UUIDs (random per game). A library card's position is part of its identity
     * for the player searching it: with UUID order, "the first Plains" of a search was a
     * different card in each replay, and the following shuffle then diverged the game.
     * Only objects indistinguishable by that content fall back to the UUID.
     */
    static Comparator<UUID> objects(Game game) {
        return Comparator.comparing((UUID id) -> objectKey(id, game))
                .thenComparing(id -> contentKey(id, game))
                .thenComparing(UUID::toString);
    }

    static String objectKey(UUID id, Game game) {
        Player player = game.getPlayer(id);
        if (player != null) {
            return "0|" + player.getName();
        }
        Permanent permanent = game.getPermanent(id);
        if (permanent != null) {
            Player controller = game.getPlayer(permanent.getControllerId());
            return "1|" + permanent.getName() + "|" + (controller == null ? "" : controller.getName())
                    + "|" + padded(permanent.getZoneChangeCounter(game))
                    + "|" + padded(permanent.getPower().getValue()) + "|" + padded(permanent.getToughness().getValue())
                    + "|" + (permanent.isTapped() ? 1 : 0) + "|" + padded(permanent.getDamage());
        }
        int stackPosition = 0;
        for (StackObject stackObject : game.getStack()) {
            if (stackObject.getId().equals(id) || stackObject.getSourceId().equals(id)) {
                return "2|" + padded(stackPosition) + "|" + stackObject.getName();
            }
            stackPosition++;
        }
        Card card = game.getCard(id);
        if (card != null) {
            Zone zone = game.getState().getZone(id);
            Player owner = game.getPlayer(card.getOwnerId());
            int position = -1;
            if (owner != null && zone == Zone.LIBRARY) {
                position = owner.getLibrary().getCardList().indexOf(id);
            } else if (owner != null && zone == Zone.GRAVEYARD) {
                position = new ArrayList<>(owner.getGraveyard()).indexOf(id);
            } else if (owner != null && zone == Zone.HAND) {
                position = new ArrayList<>(owner.getHand()).indexOf(id);
            }
            return "3|" + zone + "|" + (owner == null ? "" : owner.getName()) + "|" + padded(position)
                    + "|" + card.getName() + "|" + padded(card.getZoneChangeCounter(game));
        }
        return "9|";
    }

    /**
     * #735: what still tells apart two permanents that {@link #objectKey} cannot (same name,
     * controller, zone-change counter, P/T, tapped state and damage; typically tokens): their
     * timestamp order, counters, rule texts and battlefield order. Without it such permanents
     * fell back to the native UUID, so "the first Spirit Token" was a different token in each
     * replay. It is compared only after the existing key (and, for abilities, after the rule
     * text), so it orders only ties that were random before. Non-permanents get "".
     */
    static String contentKey(UUID id, Game game) {
        Permanent permanent = game.getPermanent(id);
        return permanent == null ? "" : permanentContent(permanent, game);
    }

    static String permanentContent(Permanent permanent, Game game) {
        List<String> counters = new ArrayList<>();
        for (Counter counter : permanent.getCounters(game).values()) {
            counters.add(counter.getName() + "=" + counter.getCount());
        }
        Collections.sort(counters);
        List<String> rules = new ArrayList<>();
        for (String rule : permanent.getRules(game)) {
            // Hints may name objects by getIdName ("Name [1a2]"): native-id fragments.
            rules.add(ID_TAG.matcher(rule).replaceAll(""));
        }
        Collections.sort(rules);
        int position = new ArrayList<>(game.getBattlefield().getAllPermanents()).indexOf(permanent);
        return padded(permanent.getCreateOrder()) + "|" + String.join(",", counters)
                + "|" + String.join("\n", rules) + "|" + padded(position);
    }

    private static final Pattern ID_TAG = Pattern.compile("\\s*\\[[0-9a-f]{3}\\]");

    private static String padded(int value) {
        return String.format("%08d", value + 10_000_000);
    }

    /** Abilities: the source object's stable key, then rule text; ids only break ties. */
    static Comparator<Ability> abilities(Game game) {
        return Comparator.comparing((Ability ability) -> (ability.getSourceId() == null ? ""
                : objectKey(ability.getSourceId(), game)) + "#" + ability.getRule() + "#"
                + (ability.getSourceId() == null ? "" : contentKey(ability.getSourceId(), game)) + "#"
                + ability.getSourceId() + ":" + ability.getOriginalId());
    }
}
