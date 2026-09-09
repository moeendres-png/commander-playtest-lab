"""Overlay-mechanics test: generate a provider from a stub controller and apply
the WS-48 behavior surface. Catches anchor/regex drift without needing Forge.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

import ws40_generate_forge_provider as gen  # noqa: E402

STUB = """package forge.game.player;

import forge.game.Game;
import forge.game.GameEntity;
import forge.game.card.Card;
import forge.game.combat.Combat;
import forge.game.cost.CostDecisionMakerBase;
import forge.game.cost.CostPart;
import forge.game.replacement.ReplacementEffect;
import forge.game.spellability.AbilitySub;
import forge.game.spellability.SpellAbility;
import forge.game.zone.ZoneType;
import forge.card.ColorSet;
import forge.card.mana.ManaCost;
import forge.game.card.CardCollection;
import forge.game.card.CardCollectionView;
import forge.game.cost.CostPartMana;
import forge.game.mana.ManaConversionMatrix;
import org.apache.commons.lang3.tuple.ImmutablePair;
import java.util.List;

public abstract class PlayerController {
    public abstract List<SpellAbility> chooseSpellAbilityToPlay();
    public abstract boolean playChosenSpellAbility(SpellAbility sa);
    public abstract SpellAbility getAbilityToPlay(Card hostCard, java.util.List<SpellAbility> abilities, forge.util.ITriggerEvent triggerEvent);
    public abstract boolean chooseTargetsFor(SpellAbility currentAbility);
    public abstract CostDecisionMakerBase getCostDecisionMaker(Player player, SpellAbility ability, boolean effect, String prompt);
    public abstract boolean payManaCost(ManaCost toPay, CostPartMana costPartMana, SpellAbility sa, String prompt, ManaConversionMatrix matrix, boolean effect);
    public abstract List<CostPart> orderCosts(List<CostPart> costs);
    public abstract List<AbilitySub> chooseModeForAbility(SpellAbility sa, List<AbilitySub> possible, int min, int num, boolean allowRepeat);
    public abstract List<SpellAbility> orderSimultaneousSa(List<SpellAbility> activePlayerSAs);
    public abstract Integer announceRequirements(SpellAbility ability, int min, int max, String announce);
    public abstract boolean confirmReplacementEffect(ReplacementEffect replacementEffect, SpellAbility effectSA, GameEntity affected, String question);
    public abstract byte chooseColor(String message, SpellAbility sa, ColorSet colors);
    public abstract ImmutablePair<CardCollection, CardCollection> arrangeForScry(CardCollection topN);
    public abstract boolean chooseCardsPile(SpellAbility sa, CardCollectionView pile1, CardCollectionView pile2, String faceUp);
    public abstract <T extends GameEntity> T chooseSingleEntityForEffect(FCollectionView<T> optionList, DelayedReveal delayedReveal, SpellAbility sa, String title, boolean isOptional, Player relatedPlayer, Map<String, Object> params);
    public abstract void playSpellAbilityNoStack(SpellAbility effectSA, boolean mayChoseNewTargets);
    public abstract void declareAttackers(Player attacker, Combat combat);
    public abstract void declareBlockers(Player defender, Combat combat);
    public abstract boolean mulliganKeepHand(Player player, int cardsToReturn);
}
"""


def _load_overlay():
    spec = importlib.util.spec_from_file_location(
        "ws48_behavior_surface", SCRIPTS / "ws48_v105_behavior_surface.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_forge_src(tmp_path):
    src = tmp_path / "forge-src/forge-game/src/main/java/forge/game/cost"
    src.mkdir(parents=True)
    (src / "ICostVisitor.java").write_text(
        "package forge.game.cost;\n"
        "public interface ICostVisitor<T> {\n"
        "    T visit(CostPartMana cost);\n"
        "    T visit(CostTap cost);\n"
        "    T visit(CostDiscard cost);\n"
        "}\n"
    )
    return tmp_path / "forge-src"


def test_behavior_surface_applies(tmp_path):
    provider = tmp_path / "Ws23ForgeVerticalProvider.java"
    state = tmp_path / "Ws40SuccessorState.java"
    java, _mapping = gen.render(STUB, "TEST_COMMIT", "TEST_TREE")
    # Faithful ws45 lifecycle block (as ws45_apply_generated_overlay produces).
    old_lifecycle = """        try {
            match.startGame(game);
            stopReason = "FORGE_GAME_RETURNED";"""
    new_lifecycle = """        try {
            String ws40EntryMode = System.getenv("COMMANDER_LAB_WS40_ENTRY_MODE");
            String ws40ConstructionOnly = System.getenv("COMMANDER_LAB_WS40_CONSTRUCTION_ONLY");
            Ws45StrictObservation.installRulesRandomnessBeforeGameStart();
            if ("1".equals(ws40ConstructionOnly) && "NATURAL_GAME_START".equals(ws40EntryMode)) {
                Ws45StrictObservation.prepareNatural(game);
                match.startGame(game, () -> Ws45StrictObservation.emitNaturalLifecycle(game, broker));
            } else if ("NATIVE_STATE_LOAD".equals(ws40EntryMode)) {
                match.startGame(game, () -> Ws40SuccessorState.applyNativeState(game, broker));
            } else {
                match.startGame(game);
            }
            stopReason = "FORGE_GAME_RETURNED";"""
    assert java.count(old_lifecycle) == 1
    java = java.replace(old_lifecycle, new_lifecycle, 1)
    provider.write_text(java)
    shutil.copy(REPO / "qualification/providers/forge/gpl/Ws40SuccessorState.java", state)
    overlay = _load_overlay()
    overlay.patch_provider(provider, _fake_forge_src(tmp_path))
    overlay.patch_state(state)
    patched = provider.read_text()
    for marker in (
        "ws48PriorityLabel(actor, sa)",
        "ws48OptionLabel(actor, options.get(i))",
        "UNSUPPORTED_DISCRETIONARY_DECISION",
        "emitBehaviorCheckpoint",
        "Ws48BehaviorEvents(broker)",
        "WS48_SELECTED_ATTACK_ASSIGNMENT",
        "WS48_SELECTED_BLOCK_ASSIGNMENT",
        "SINGLE_NATIVE_SPELL_VARIANT",
        "chooseTargetsFor",
        "Ws48CostDecisionMaker",
        "NATIVE_MANA_ACTIVATED",
        "WS48_COST_PART_UNSUPPORTED:CostDiscard",
        "blocker_declared:",
        "mana_paid:",
        "commander_cast",
        "spell_resolved",
        "WS48_UNSUPPORTED_OP:",
        "X_VALUE:",
        "COLOR_CHOICE:",
        "SCRY_KEEP_TOP:",
        "PILE_1:",
        "TRIGGER_ORDER:",
        "recipient_ref=",
        "next_turn:",
        "ws48PermuteTriggers",
        "ws48PileLabel",
        "ws48DistributionRef",
        "ws48ModeKeyForSub",
        "ws48AbilityKeyForSA",
        "ATTACK_ASSIGNMENT:",
        "BLOCK_ASSIGNMENT:",
        "emitDecisionFrame(kind, actor, labels.size())",
        "ws48BehaviorEnabled()",
        "COMMANDER_LAB_WS48_BEHAVIOR",
    ):
        assert marker in patched, marker
    assert "import forge.ai" not in patched and "import forge.gui" not in patched
    patched_state = state.read_text()
    assert "semanticRefOf" in patched_state
    assert "emitBehaviorCheckpoint" in patched_state
    assert "ws48BeginLoadedCombatStep" in patched_state
    # The generic failClosed stubs must be replaced by native implementations.
    assert 'throw failClosed("declareAttackers");' not in patched
    assert 'throw failClosed("declareBlockers");' not in patched
