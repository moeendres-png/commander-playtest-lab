from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.models import (
    CompareMulliganPoliciesInput,
    EvaluateOpeningHandInput,
    MulliganContext,
    MulliganGamePlan,
    MulliganPolicyName,
    RunMulliganLabInput,
)
from commander_lab.mulligan import MulliganLab, MulliganLabError
from commander_lab.tools.service import CommanderToolService


def context(deck, *, ensemble=None, seed=7):
    return MulliganContext(
        deck_id=deck.deck_id,
        deck_hash=deck.deck_hash,
        opponent_ensemble_id=ensemble,
        seat_position=1,
        starting_player=False,
        pod_size=4,
        pilot_profile_id="test-pilot",
        pilot_version="1",
        game_plan=MulliganGamePlan.BALANCED,
        seed=seed,
    )


def names(deck, wanted):
    pool = {}
    for card in deck.cards:
        if card.oracle_name not in deck.commander_names:
            pool.setdefault(card.oracle_name, []).append(card)
    result=[]
    used={}
    for name in wanted:
        i=used.get(name,0)
        result.append(pool[name][i]); used[name]=i+1
    return tuple(result)


def test_london_mulligan_uses_free_first_multiplayer_and_commanders_stay_out(repo_root: Path) -> None:
    lab=MulliganLab(repo_root); deck=lab.deck("korvold/current")
    assert all(card.oracle_name not in deck.commander_names for card in lab._library(deck))
    bad=names(deck,("Forest","Swamp","Mountain","Massacre Wurm","The Gitrog Monster","Mazirek, Kraul Death Priest","Szarel, Genesis Shepherd"))
    good=names(deck,("Forest","Forest","Swamp","Sol Ring","Zuran Orb","Deadly Dispute","Mirkwood Bats"))
    result=lab.london_mulligan_from_draws(deck,(bad,good),MulliganPolicyName.PRIMER_POLICY,context(deck))
    assert result.mulligans_taken == 1
    assert result.effective_bottom_count == 0
    assert result.free_multiplayer_mulligan_used is True
    assert len(result.kept_cards) == 7


def test_korvold_and_rogshai_golden_hands(repo_root: Path) -> None:
    lab=MulliganLab(repo_root)
    k=lab.deck("korvold/current")
    good=lab.evaluate(k,names(k,("Forest","Forest","Swamp","Sol Ring","Zuran Orb","Deadly Dispute","Mirkwood Bats")),MulliganPolicyName.PRIMER_POLICY,context(k))
    bad=lab.evaluate(k,names(k,("Forest","Swamp","Mountain","Splendid Reclamation","Ramunap Excavator","The Gitrog Monster","Massacre Wurm")),MulliganPolicyName.PRIMER_POLICY,context(k))
    assert good.keep is True
    assert bad.keep is False
    r=lab.deck("rogshai/current")
    rg=lab.evaluate(r,names(r,("Island","Plains","Sol Ring","Consider","Counterspell","Slip Out the Back","Combat Research")),MulliganPolicyName.PRIMER_POLICY,context(r))
    rb=lab.evaluate(r,names(r,("Plains","Mountain","Blackblade Reforged","Duelist's Heritage","Jeska, Thrice Reborn","Kediss, Emberclaw Familiar","Farewell")),MulliganPolicyName.PRIMER_POLICY,context(r))
    assert rg.keep is True
    assert rb.keep is False


def test_common_random_numbers_are_reproducible(repo_root: Path) -> None:
    lab=MulliganLab(repo_root); deck=lab.deck("rogshai/current")
    a=tuple(lab.iter_draw_sequences(deck,samples=3,seed=99))
    b=tuple(lab.iter_draw_sequences(deck,samples=3,seed=99))
    assert [[c.oracle_name for c in h] for h in a[0]] == [[c.oracle_name for c in h] for h in b[0]]


def test_hypergeometric_land_baseline_is_valid(repo_root: Path) -> None:
    lab=MulliganLab(repo_root); deck=lab.deck("korvold/current")
    lands=next(row for row in lab.baselines(deck) if row.category=="lands")
    assert 0 < lands.probability_at_least[2] < 1
    assert lands.probability_at_least[1] >= lands.probability_at_least[2]


def test_context_deck_hash_mismatch_rejected(repo_root: Path) -> None:
    lab=MulliganLab(repo_root); deck=lab.deck("korvold/current")
    bad=context(deck).model_copy(update={"deck_hash":"0"*64})
    with pytest.raises(MulliganLabError):
        lab.run(bad,(MulliganPolicyName.CONSERVATIVE,),samples=2)


def test_tool_surface_runs_and_generates_non_absolute_rule(repo_root: Path, tmp_path: Path) -> None:
    service=CommanderToolService(repo_root)
    eval_response=service.evaluate_opening_hand(EvaluateOpeningHandInput(
        deck_id="rogshai/current",
        card_names=("Island","Plains","Sol Ring","Consider","Counterspell","Slip Out the Back","Combat Research"),
        policy="primer_policy",
    ))
    assert eval_response.status.value == "completed"
    result=service.run_mulligan_lab(RunMulliganLabInput(
        deck_id="korvold/current",
        policies=("conservative","primer_policy"),
        samples=30,
        followup_samples=10,
        output_name="unit-mulligan.json",
    ))
    assert result.status.value == "completed"
    assert result.result["generated_rules"][0]["absolute_rule"] is False
    assert result.result["full_matchup_performance_separate"] is True


def test_large_materialization_is_forbidden_but_streaming_supported(repo_root: Path) -> None:
    lab=MulliganLab(repo_root); deck=lab.deck("korvold/current")
    with pytest.raises(MulliganLabError):
        lab.sample_draw_sequences(deck,samples=100001,seed=1)
    iterator=lab.iter_draw_sequences(deck,samples=100001,seed=1)
    assert len(next(iterator)) == 7
