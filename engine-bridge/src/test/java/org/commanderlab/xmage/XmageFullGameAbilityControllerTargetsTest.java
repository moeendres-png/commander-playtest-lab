package org.commanderlab.xmage;

import mage.cards.Card;
import mage.constants.Zone;
import mage.game.Game;
import mage.target.common.TargetCardInYourGraveyard;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * #736: a real-deck 6P game hung in StackObjectImpl.chooseNewTarget. Bolt
 * Bend's controller re-chose the target of Mistveil Plains ("target card from
 * your graveyard"), the bridge offered the CHOOSER's graveyard, and the engine
 * rejected every pick ("This target is not valid!") and asked again forever.
 * XMage's own HumanPlayer computes the candidates for the ability controller
 * ({@code target.getAffectedAbilityControllerId(getId())}); the bridge must too.
 */
class XmageFullGameAbilityControllerTargetsTest {

    @Test
    void retargetingAnotherPlayersAbilityOffersThatPlayersGraveyard() {
        XmageMultiplayerScenario s = XmageMultiplayerScenario.start("issue736-ability-controller", 2, "P1",
                List.of(XmageMultiplayerScenario.obj("P1", "Iron Myr", 0, Zone.GRAVEYARD),
                        XmageMultiplayerScenario.obj("P2", "Grizzly Bears", 0, Zone.GRAVEYARD)));
        Game game = s.session.restorationGame();
        XmageFullGamePlayer chooser = (XmageFullGamePlayer) s.seats.get("P1");
        UUID abilityController = s.seats.get("P2").getId();

        // StackObjectImpl.chooseNewTarget's own setup when the chooser is not
        // the ability's controller.
        TargetCardInYourGraveyard target = new TargetCardInYourGraveyard();
        target.setTargetController(chooser.getId());
        target.setAbilityController(abilityController);

        assertEquals(Set.of("Grizzly Bears"), names(chooser.offeredTargets(target, null, game, null), game),
                "\"your graveyard\" is the ability controller's (P2), never the chooser's");

        // Control: the chooser's own ability keeps offering the chooser's graveyard.
        TargetCardInYourGraveyard own = new TargetCardInYourGraveyard();
        assertEquals(Set.of("Iron Myr"), names(chooser.offeredTargets(own, null, game, null), game),
                "control: P1's own ability targets P1's graveyard");
    }

    private static Set<String> names(Set<UUID> ids, Game game) {
        return ids.stream().map(game::getCard).map(Card::getName).collect(Collectors.toSet());
    }
}
