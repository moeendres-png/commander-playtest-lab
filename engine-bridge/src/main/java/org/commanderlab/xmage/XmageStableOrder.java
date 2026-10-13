package org.commanderlab.xmage;

import mage.abilities.Ability;
import mage.cards.Card;
import mage.constants.Zone;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.game.stack.StackObject;
import mage.players.Player;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.UUID;

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
        return Comparator.comparing((UUID id) -> objectKey(id, game)).thenComparing(UUID::toString);
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

    private static String padded(int value) {
        return String.format("%08d", value + 10_000_000);
    }

    /** Abilities: the source object's stable key, then rule text; ids only break ties. */
    static Comparator<Ability> abilities(Game game) {
        return Comparator.comparing((Ability ability) -> (ability.getSourceId() == null ? ""
                : objectKey(ability.getSourceId(), game)) + "#" + ability.getRule() + "#"
                + ability.getSourceId() + ":" + ability.getOriginalId());
    }
}
