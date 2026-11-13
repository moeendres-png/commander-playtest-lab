package org.commanderlab.xmage;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import mage.cards.Card;
import mage.game.GameCommanderImpl;
import mage.players.Player;
import org.junit.jupiter.api.Test;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Bridge-lean #1264 step 2 (NEUTRAL): one view build per decision. The view
 * references a decision carries, and the public view they hash, equal what the
 * two independent builds produced before, for the anchor seat (derived from a
 * copy of the actor view) and for every other seat (built as before). The public
 * view stays free of every private field.
 */
class XmageFullGameViewBindingTest {

    private static final Set<String> PRIVATE_PLAYER_KEYS = Set.of(
            "hand", "mana_pool", "land_plays_remaining", "granted_library",
            "is_actor", "private_state_visible");

    @Test
    void decisionReferencesEqualIndependentBuildsAndPublicViewHoldsNoPrivateField() throws Exception {
        XmageDeckImporter importer = new XmageDeckImporter();
        List<String> handles = XmageFullGameHiddenInformationTest.importCopies(
                importer, XmageFullGameHiddenInformationTest.loadRogShaiRuntimeDeck(), 4);
        XmageFullGameSession session = new XmageFullGameSession(
                "lean-1264-view-binding", handles, 0, 40, 10704L, importer);
        session.start();
        GameCommanderImpl game = XmageFullGameHiddenInformationTest.field(
                session, "game", GameCommanderImpl.class);

        Set<String> seatsSeen = new HashSet<>();
        int anchorDecisions = 0;
        for (int step = 0; step < 90; step++) {
            JsonObject payload = session.pendingDecisionPayload();
            if (payload.get("decision").isJsonNull()) {
                break;
            }
            JsonObject pending = payload.getAsJsonObject("decision");
            Player anchor = XmageFullGameStateRedactor.publicViewAnchor(game);
            Player actor = game.getPlayer(java.util.UUID.fromString(pending.get("actor_id").getAsString()));
            seatsSeen.add(Integer.toString(pending.get("seat").getAsInt()));
            if (anchor.getId().equals(actor.getId())) {
                anchorDecisions++;
            }

            // The engine is parked: the state is the one the references were bound on.
            JsonObject independentActor = XmageFullGameStateRedactor.actorView(game, actor);
            JsonObject independentPublic = XmageFullGameStateRedactor.publicView(game);
            assertEquals("actor-view:" + XmageAuditEventLog.stateHash(independentActor),
                    pending.get("private_actor_state_reference").getAsString(), "step " + step);
            assertEquals("public-view:" + XmageAuditEventLog.stateHash(independentPublic),
                    pending.get("public_state_reference").getAsString(), "step " + step);
            assertEquals(independentActor.toString(), pending.get("pilot_state").toString(), "step " + step);

            // Derived-from-copy public view: same JSON, and the actor view is not consumed.
            JsonObject anchorView = XmageFullGameStateRedactor.actorView(game, anchor);
            String anchorViewBefore = anchorView.toString();
            JsonObject derived = XmageFullGameStateRedactor.publicViewFromAnchorView(
                    game, anchor, anchorView.deepCopy());
            assertEquals(independentPublic.toString(), derived.toString(), "step " + step);
            assertEquals(anchorViewBefore, anchorView.toString());

            assertPublicViewHasNoPrivateField(game, independentPublic);
            XmageFullGameHiddenInformationTest.answerNeutrally(session, pending);
        }
        assertTrue(seatsSeen.size() >= 2, "decisions of several seats must be covered, saw " + seatsSeen);
        assertTrue(anchorDecisions >= 1, "the anchor-seat derivation path must be covered");
    }

    private static void assertPublicViewHasNoPrivateField(GameCommanderImpl game, JsonObject view) {
        assertFalse(view.has("actor_id"));
        assertFalse(view.has("seat"));
        assertFalse(view.has("looked_at"));
        for (JsonElement element : view.getAsJsonArray("players")) {
            JsonObject player = element.getAsJsonObject();
            for (String key : PRIVATE_PLAYER_KEYS) {
                assertFalse(player.has(key), "public view carries " + key);
            }
            for (JsonElement permanent : player.getAsJsonArray("battlefield")) {
                assertFalse(permanent.getAsJsonObject().has("private_identity"));
            }
            for (JsonElement exiled : player.getAsJsonArray("exile")) {
                assertFalse(exiled.getAsJsonObject().has("face_down"));
            }
        }
        String serialized = view.toString();
        for (Player player : game.getPlayers().values()) {
            // No principal's real id and no hand or library card identity anywhere in the view.
            assertFalse(serialized.contains(player.getId().toString()), "raw principal id in public view");
            for (Card card : player.getHand().getCards(game)) {
                assertFalse(serialized.contains(card.getId().toString()), "hand card id in public view");
            }
            for (Card card : player.getLibrary().getCards(game)) {
                assertFalse(serialized.contains(card.getId().toString()), "library card id in public view");
            }
        }
    }
}
