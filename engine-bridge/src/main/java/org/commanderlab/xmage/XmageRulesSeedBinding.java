package org.commanderlab.xmage;

import com.google.gson.JsonObject;
import mage.game.Game;

/**
 * Authoritative per-game Rules-RNG binding shared by every XMage lane.
 *
 * <p>The only seed authority is the engine's own per-game Rules stream
 * ({@code game.setRulesSeed(seed)}). {@code game.setRequireExplicitSeed(true)}
 * arms the engine's fail-closed check, so {@code game.init} refuses to run on
 * the non-credited default seed. The binding must be applied after game
 * construction and before {@code game.start}: construction, deck loading and
 * player setup consume no Rules randomness on the pinned engine, while
 * start/init performs the opening shuffles, the choosing-player pick and the
 * opening hands.
 *
 * <p>Seed control is always read back from engine state, never echoed from
 * the request. The seed value itself is orchestration data: it must never be
 * placed in a principal-scoped observation, because the seed plus the engine
 * determines hidden library order.
 */
final class XmageRulesSeedBinding {

    static final String SEED_SCOPE = "authoritative_per_game_rules_rng";
    static final String BINDING_MODEL =
            "EXPLICIT_RULES_SEED: game.setRulesSeed(seed) + "
                    + "game.setRequireExplicitSeed(true) after construction, "
                    + "before game.start/init";

    private XmageRulesSeedBinding() {
    }

    /**
     * Binds {@code seed} to the game's Rules RNG and verifies the engine
     * accepted it. Throws when the engine readback does not hold, so an
     * unbound game can never be reported as controlled.
     */
    static void bind(Game game, long seed) {
        game.setRulesSeed(seed);
        game.setRequireExplicitSeed(true);
        if (!holds(game, seed)) {
            throw new IllegalStateException(
                    "RULES_SEED_BINDING_FAILED: engine readback rules_seed="
                            + game.getRulesSeed()
                            + " explicit="
                            + game.isRulesSeedExplicit()
                            + " for requested seed "
                            + seed
            );
        }
    }

    static boolean holds(Game game, long seed) {
        return game.getRulesSeed() == seed && game.isRulesSeedExplicit();
    }

    /** Orchestration-scoped proof of the live binding. Never an observation. */
    static JsonObject payload(Game game, long explicitSeed) {
        JsonObject binding = new JsonObject();
        binding.addProperty("explicit_seed", explicitSeed);
        binding.addProperty("rules_seed", game.getRulesSeed());
        binding.addProperty("rules_seed_matches", game.getRulesSeed() == explicitSeed);
        binding.addProperty("rules_seed_explicit", game.isRulesSeedExplicit());
        binding.addProperty("require_explicit_seed", true);
        binding.addProperty("rules_random_calls", game.getRulesRandomCalls());
        binding.addProperty("seed_scope", SEED_SCOPE);
        binding.addProperty("binding_model", BINDING_MODEL);
        binding.addProperty("seed_supported", holds(game, explicitSeed));
        return binding;
    }
}
