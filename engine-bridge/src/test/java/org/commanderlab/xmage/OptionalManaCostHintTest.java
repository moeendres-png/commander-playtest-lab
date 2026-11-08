package org.commanderlab.xmage;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import mage.abilities.Ability;
import mage.abilities.SpellAbility;
import mage.abilities.costs.Cost;
import mage.abilities.costs.common.PayLifeCost;
import mage.abilities.costs.mana.ManaCostsImpl;
import mage.abilities.effects.OneShotEffect;
import mage.abilities.effects.common.DoIfCostPaid;
import mage.cards.CardImpl;
import mage.cards.decks.Deck;
import mage.constants.MultiplayerAttackOption;
import mage.constants.Outcome;
import mage.constants.RangeOfInfluence;
import mage.game.CommanderFreeForAll;
import mage.game.Game;
import mage.game.mulligan.MulliganType;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.jupiter.api.Assertions.*;

class OptionalManaCostHintTest {
    static final class Card extends CardImpl {
        Card(UUID owner) { super(owner, "Test Source"); }
        Card(Card card) { super(card); }
        @Override public Card copy() { return new Card(this); }
    }
    static final class DerivedCost extends DoIfCostPaid {
        DerivedCost(Cost cost) { super(null, cost, "Custom question?"); }
    }
    static final class Nested extends OneShotEffect {
        private final DoIfCostPaid inner;
        Nested(DoIfCostPaid inner) { super(Outcome.Benefit); this.inner = inner; }
        @Override public boolean apply(Game game, Ability source) { return inner.apply(game, source); }
        @Override public Nested copy() { return new Nested(inner); }
    }
    private static DoIfCostPaid effect(Cost cost) {
        return new DoIfCostPaid(null, cost, "Create a token that's a copy of that creature?");
    }
    private static JsonObject booleanOption(JsonObject pending, boolean value) {
        JsonObject match = null;
        for (var entry : pending.getAsJsonArray("legal_options")) {
            JsonObject option = entry.getAsJsonObject();
            if (option.getAsJsonObject("metadata").get("value").getAsBoolean() == value) {
                assertNull(match, "Boolean option must be unique");
                match = option;
            }
        }
        assertNotNull(match, "Requested Boolean value must be offered");
        return match;
    }
    private static List<JsonObject> capture(DoIfCostPaid effect, boolean multiple,
                                             boolean direct, boolean nested) throws Exception {
        XmageFullGameDecisionController controller = new XmageFullGameDecisionController();
        XmageFullGamePlayer player = new XmageFullGamePlayer("hint", RangeOfInfluence.ALL, controller);
        CommanderFreeForAll game = new CommanderFreeForAll(MultiplayerAttackOption.MULTIPLE,
                RangeOfInfluence.ALL, MulliganType.LONDON.getMulligan(1), 40, 7);
        game.setRulesSeed(4242L);
        game.addPlayer(player, new Deck());
        Card card = new Card(player.getId());
        game.loadCards(Set.of(card), player.getId());
        SpellAbility source = new SpellAbility(new ManaCostsImpl<>("{0}"), "Test Source");
        source.setControllerId(player.getId());
        source.setSourceId(card.getId());
        source.addEffect(effect);
        if (multiple) source.addEffect(effect(new ManaCostsImpl<>("{1}")));
        AtomicReference<Throwable> failure = new AtomicReference<>();
        Thread thread = new Thread(() -> {
            try {
                if (direct) player.chooseUse(Outcome.Benefit, "Unrelated?", source, game);
                else effect.apply(game, source);
            } catch (Throwable ex) { failure.set(ex); }
        });
        thread.setDaemon(true);
        thread.start();
        List<JsonObject> seen = new ArrayList<>();
        String prior = "";
        long deadline = System.nanoTime() + 10_000_000_000L;
        while (thread.isAlive() && System.nanoTime() < deadline) {
            JsonObject pending = controller.pendingDecision();
            if (pending == null || prior.equals(pending.get("decision_id").getAsString())) {
                Thread.sleep(5);
                continue;
            }
            prior = pending.get("decision_id").getAsString();
            seen.add(pending.deepCopy());
            JsonObject response = new JsonObject();
            response.addProperty("decision_id", prior);
            response.addProperty("actor_id", pending.get("actor_id").getAsString());
            JsonArray selected = new JsonArray();
            selected.add(booleanOption(pending, nested && seen.size() == 1)
                    .get("option_id").getAsString());
            response.add("selected_option_ids", selected);
            response.add("ordering", new JsonArray());
            controller.submit(response);
        }
        thread.join(1000);
        assertFalse(thread.isAlive(), "native callback did not finish");
        assertNull(failure.get());
        assertEquals(nested ? 2 : 1, seen.size());
        return seen;
    }
    private static void noHint(JsonObject pending) {
        JsonObject context = pending.getAsJsonObject("context");
        assertFalse(context.has("optional_mana_cost"));
        assertFalse(context.has("optional_mana_cost_scope"));
    }
    @Test void nativeCallbackIncludesCostAndKeepsBothOptions() throws Exception {
        JsonObject pending = capture(effect(new ManaCostsImpl<>("{G}{U}")), false, false, false).get(0);
        JsonObject context = pending.getAsJsonObject("context");
        JsonArray options = pending.getAsJsonArray("legal_options");
        assertEquals(2, options.size());
        assertNotEquals(booleanOption(pending, true).get("option_id"),
                booleanOption(pending, false).get("option_id"));
        assertEquals("{G}{U}", context.get("optional_mana_cost").getAsString());
        assertEquals("effect_resolution", context.get("optional_mana_cost_scope").getAsString());
    }
    @Test void unrelatedBooleanDoesNotInheritHint() throws Exception {
        noHint(capture(effect(new ManaCostsImpl<>("{G}{U}")), false, true, false).get(0));
    }
    @Test void multipleEffectsAreAmbiguous() throws Exception {
        noHint(capture(effect(new ManaCostsImpl<>("{G}{U}")), true, false, false).get(0));
    }
    @Test void subclassAndNonManaAndVariableCostsAreExcluded() throws Exception {
        noHint(capture(new DerivedCost(new ManaCostsImpl<>("{G}{U}")), false, false, false).get(0));
        noHint(capture(effect(new PayLifeCost(0)), false, false, false).get(0));
        noHint(capture(effect(new ManaCostsImpl<>("{X}")), false, false, false).get(0));
    }
    @Test void nestedCostDoesNotBorrowOuterCost() throws Exception {
        DoIfCostPaid inner = effect(new ManaCostsImpl<>("{G}{U}"));
        DoIfCostPaid outer = new DoIfCostPaid(new Nested(inner), new ManaCostsImpl<>("{0}"), "Outer?");
        List<JsonObject> frames = capture(outer, false, false, true);
        noHint(frames.get(1));
    }
    @Test void fixtureChoosesTheSameBooleanWhenOptionsAreReordered() throws Exception {
        JsonObject pending = capture(effect(new ManaCostsImpl<>("{G}{U}")), false, false, false).get(0);
        JsonObject yes = booleanOption(pending, true);
        JsonObject no = booleanOption(pending, false);
        JsonArray reversed = new JsonArray();
        reversed.add(no);
        reversed.add(yes);
        pending.add("legal_options", reversed);
        assertEquals(yes, booleanOption(pending, true));
        assertEquals(no, booleanOption(pending, false));
    }
}
