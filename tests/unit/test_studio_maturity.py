"""Maturity R0-R3 of simulated findings in the deck builder (Q1-c, #1666).

New file because ``maturity.py`` is a new module; the route and the page are pinned here too
(the route through the experiment lab of ``test_studio_experiments``).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from commander_lab.engine.rules.full_game_comparison import PairedVariantResult, _apply_holm
from commander_lab.studio import maturity as m
from commander_lab.studio import number_contract as nc
from commander_lab.studio.store import StudioStore
from tests.unit import test_studio_experiments as tx
from tests.unit.test_studio_experiments import lab  # noqa: F401  (the experiment lab fixture)

STATIC = Path(m.__file__).resolve().parent / "static"
JAR = "j" * 64
FP = "f" * 64
CUR = m.Current(
    main_revision_id="rev-main", predecessor_revision_id="rev-prev", bridge_jar_sha256=JAR
)
ALL_R2 = m.Checks(positive_control=True, negative_control=True, card_competence=True)
ALL_R3 = replace(ALL_R2, pilot_audit=True)


def _pairs(
    wins: int, losses: int = 0, ties: int = 0, first_seed: int = 500
) -> list[dict[str, object]]:
    """One pair per seed: the effective p-value is then the sign test, 2 * 0.5**n for n wins."""
    diffs = [1.0] * wins + [-1.0] * losses + [0.0] * ties
    return [{"seed": first_seed + i, "difference": d} for i, d in enumerate(diffs)]


def _finding(
    sid: str,
    *,
    purpose: str | None = "confirmation",
    wins: int = 6,
    losses: int = 0,
    ties: int = 0,
    first_seed: int = 500,
    base: str = "rev-main",
    variant: str = "rev-var",
    table_hash: str = "t1",
    detectable: float | None = 20.0,
    alpha: float | None = 0.05,
    counts: bool = True,
    plan_ok: bool = True,
    sealed: bool | None = True,
    jars: list[str] | None = None,
    fingerprint: str | None = FP,
    fingerprint_now: str | None = FP,
    difference_pp: float | None = None,
    stop_reason: str = "BUDGET_EXHAUSTED",
    extra_seeds: list[int] | None = None,
    plan_range: list[int] | None = None,
) -> m.Finding:
    pairs = _pairs(wins, losses, ties, first_seed)
    n = len(pairs)
    seeds = [int(str(p["seed"])) for p in pairs]
    diff = 100.0 * (wins - losses) / n if n else None
    experiment = (
        None
        if purpose is None
        else {
            "experiment_id": f"exp-{sid}",
            "purpose": purpose,
            "table_hash": table_hash,
            "seeds": [first_seed, first_seed + n - 1] if plan_range is None else plan_range,
            "pilot_fingerprint": fingerprint,
        }
    )
    entry = {
        "series_id": sid,
        "base_ref": base,
        "variant_ref": variant,
        "counts_as_result": counts,
        "pairs_completed": n if counts else None,
        "pairs_planned": n,
        "difference_pp": diff if difference_pp is None else difference_pp,
        "bridge_jar_sha256s": [JAR] if jars is None else jars,
        "covered_by_sealed_epoch": sealed,
        "experiment": experiment,
    }
    result = {
        "pairs": pairs,
        "seeds": seeds + (extra_seeds or []),
        "pairs_censored": 0,
        "decision_alpha": alpha,
        "detectable_difference_pp": detectable,
        "stop_reason": stop_reason,
    }
    return m.Finding(sid, entry, result, plan_ok, fingerprint_now)


def _assess(*findings: m.Finding, **kw: object) -> dict[str, dict[str, object]]:
    kw.setdefault("explorations", [(100, 199)])
    kw.setdefault("hashes", {"rev-main": "h-main", "rev-prev": "h-prev", "rev-old": "h-old"})
    kw.setdefault("current", CUR)
    out = m.assess(list(findings), **kw)  # type: ignore[arg-type]
    befunde = out["befunde"]
    assert isinstance(befunde, dict)
    return befunde


# -- R0 -> R1 -> R2 -> R3, one condition at a time ------------------------------------------


def test_no_badge_without_a_counted_evaluable_result() -> None:
    got = _assess(
        _finding("none", counts=False),
        _finding("noy", wins=0, ties=6, detectable=None),
        _finding("noalpha", alpha=None),
    )
    for sid in ("none", "noy", "noalpha"):
        assert got[sid]["stufe"] is None, sid
        assert got[sid]["stufe_text"] == "kein Reifegrad (Beleg fehlt)"
        assert got[sid]["empfehlungsfaehig"] is False
    assert got["noy"]["urteil"] == m.NOT_EVALUABLE


def test_r0_exploration_control_and_legacy_never_reach_r1() -> None:
    got = _assess(
        _finding("explo", purpose="exploration"),
        _finding("ctrl", purpose="control"),
        _finding("legacy", purpose=None),
        _finding("broken", plan_ok=False),
    )
    for sid in ("explo", "ctrl", "legacy", "broken"):
        assert got[sid]["stufe"] == m.R0, sid
    assert got["ctrl"]["stufe_text"] == "R0 (Kontrolle, keine Bestätigung)"
    assert "Alt-Serie ohne Plan: höchstens R0" in got["legacy"]["hinweise"]  # type: ignore[operator]


def test_r1_needs_fresh_seeds_rechecked_when_read() -> None:
    fresh = _assess(_finding("c"))
    assert fresh["c"]["stufe"] == m.R1
    # an exploration created later on the same seeds takes R1 away (read-time check)
    stale = _assess(_finding("c"), explorations=[(100, 199), (503, 503)])
    assert stale["c"]["stufe"] == m.R0
    unmet = [c["name"] for c in stale["c"]["bedingungen"] if not c["erfuellt"]]  # type: ignore[attr-defined]
    assert "frische Seeds (disjunkt von jeder Erkundung des Decks)" in unmet


@pytest.mark.parametrize("missing", ["positive_control", "negative_control", "card_competence"])
def test_r2_needs_both_controls_and_card_competence(missing: str) -> None:
    assert _assess(_finding("c"), checks={"c": ALL_R2})["c"]["stufe"] == m.R2
    partial = replace(ALL_R2, **{missing: False})
    assert _assess(_finding("c"), checks={"c": partial})["c"]["stufe"] == m.R1


def test_r2_never_without_r1() -> None:
    got = _assess(_finding("e", purpose="exploration"), checks={"e": ALL_R3})
    assert got["e"]["stufe"] == m.R0


def test_r3_needs_pilot_audit_and_a_covered_bridge() -> None:
    assert _assess(_finding("c"), checks={"c": ALL_R3})["c"]["stufe"] == m.R3
    assert _assess(_finding("c"), checks={"c": ALL_R2})["c"]["stufe"] == m.R2
    unsealed = _finding("c", sealed=False)
    assert _assess(unsealed, checks={"c": ALL_R3})["c"]["stufe"] == m.R2
    owner = replace(ALL_R3, owner_accepts_bridge=True)
    assert _assess(unsealed, checks={"c": owner})["c"]["stufe"] == m.R3


def test_production_passes_no_checks_so_r2_is_unreachable() -> None:
    assert m.Checks() == m.NO_CHECKS
    out = m.assess([_finding("c")], explorations=[], hashes={}, current=CUR)
    assert out["befunde"]["c"]["stufe"] == m.R1  # type: ignore[index]
    assert m.GAPS in out["luecken"]  # type: ignore[operator]


# -- Holm: the engine lane's values ----------------------------------------------------------


def _engine_entry(name: str, p: float) -> PairedVariantResult:
    return PairedVariantResult(
        variant_deck_id=name,
        baseline_deck_id="base",
        pairs_completed=6,
        pairs_censored=0,
        variant_win_share=None,
        baseline_win_share=None,
        win_share_difference=1.0,
        variant_only_wins=6,
        baseline_only_wins=0,
        sign_test_p_value=p,
        verdict="VARIANT_BETTER",
        effective_p_value=p,
    )


def test_studio_holm_gives_the_values_of_full_game_comparison() -> None:
    family = [_engine_entry("a", 0.03), _engine_entry("b", 0.04), _engine_entry("c", 0.001)]
    engine = _apply_holm(family, [0.03, 0.04, 0.001], 0.05)
    studio = m.holm(family, 0.05)
    assert [e.holm_adjusted_p_value for e in studio] == [e.holm_adjusted_p_value for e in engine]
    assert [e.verdict for e in studio] == [e.verdict for e in engine]
    assert [round(e.holm_adjusted_p_value or 0, 6) for e in studio] == [0.06, 0.06, 0.003]
    assert [e.holm_withheld_verdict for e in studio] == ["VARIANT_BETTER", "VARIANT_BETTER", None]


def test_holm_in_assess_matches_the_engine_lane_on_the_same_pairs() -> None:
    a, b = _finding("a"), _finding("b", variant="rev-var2", first_seed=600)
    got = _assess(a, b)
    bases = [m.verdict_basis(f.series_id, f.result) for f in (a, b)]
    engine = _apply_holm([x for x in bases if x], [x.effective_p_value for x in bases if x], 0.05)
    assert [got[s]["holm_p"] for s in ("a", "b")] == [e.holm_adjusted_p_value for e in engine]
    assert got["a"]["effektives_p"] == pytest.approx(2 * 0.5**6)


def test_a_later_confirmation_of_the_same_family_withholds_the_verdict() -> None:
    alone = _assess(_finding("a"))
    assert alone["a"]["urteil"] == m.BETTER and alone["a"]["stufe"] == m.R1
    both = _assess(_finding("a"), _finding("b", variant="rev-var2", first_seed=600))
    assert both["a"]["urteil"] == m.NO_DIFFERENCE  # 2 * 0.03125 = 0.0625 >= 0.05
    assert "Ergebnis durch Holm zurückgehalten" in both["a"]["hinweise"]  # type: ignore[operator]
    assert any("Holm-Familie: 2" in h for h in both["a"]["hinweise"])  # type: ignore[union-attr]
    # another table is another family: never pooled
    apart = _assess(
        _finding("a"), _finding("b", variant="rev-var2", first_seed=600, table_hash="t2")
    )
    assert apart["a"]["urteil"] == m.BETTER


@pytest.mark.parametrize(
    "sibling",
    [
        {"counts": False},
        {"stop_reason": "CENSORING_LIMIT"},
        {"plan_ok": False},
        {"alpha": None},
    ],
    ids=["cancelled", "censored", "plan_broken", "no_level"],
)
def test_the_family_hangs_on_the_plan_an_unusable_sibling_never_gives_credit(
    sibling: dict[str, object],
) -> None:
    alone = _assess(_finding("a"))
    assert alone["a"]["stufe"] == m.R1 and alone["a"]["urteil"] == m.BETTER
    b = _finding("b", variant="rev-var2", first_seed=600, **sibling)  # type: ignore[arg-type]
    got = _assess(_finding("a"), b)
    assert got["a"]["holm_p"] == pytest.approx(2 * 2 * 0.5**6)  # placeholder p = 1
    assert got["a"]["urteil"] != m.BETTER
    assert any("Holm-Familie: 2" in h for h in got["a"]["hinweise"])  # type: ignore[union-attr]
    assert got["b"]["holm_p"] is None  # the placeholder shows nothing of its own


def test_without_table_hash_no_holm_and_no_r1() -> None:
    got = _assess(_finding("c", table_hash=None))  # type: ignore[arg-type]
    assert got["c"]["stufe"] == m.R0 and got["c"]["holm_p"] is None


def test_the_family_level_is_the_smallest_alpha() -> None:
    # a alone: p = 2 * 0.5**8 = 0.0078; with b (p = 1) Holm gives 0.0156: kept at 0.05, not at 0.01
    a = _finding("a", wins=8, alpha=0.05)
    b = _finding("b", variant="rev-var2", first_seed=600, wins=1, losses=1, ties=4, alpha=0.01)
    got = _assess(a, b)
    assert got["a"]["niveau"] == 0.01
    assert got["a"]["holm_p"] == pytest.approx(2 * 2 * 0.5**8)
    assert got["a"]["urteil"] == m.NO_DIFFERENCE


def test_seeds_of_a_legacy_series_or_a_played_overlap_block_r1() -> None:
    legacy = _finding("legacy", purpose=None, variant="rev-old-var")
    assert _assess(_finding("c"))["c"]["stufe"] == m.R1
    assert _assess(_finding("c"), legacy)["c"]["stufe"] == m.R0  # same seeds 500..505
    played = _finding("c", extra_seeds=[150])  # plan range fresh, a played seed is not
    assert _assess(played)["c"]["stufe"] == m.R0


def test_unrecorded_proofs_are_unknown_not_failed() -> None:
    def states(checks: m.Checks) -> dict[str, object]:
        got = _assess(_finding("c"), checks={"c": checks})
        return {c["name"]: c["zustand"] for c in got["c"]["bedingungen"]}  # type: ignore[attr-defined]

    unknown = states(m.NO_CHECKS)
    assert unknown["Positivkontrolle bestanden"] == "nicht erfasst (UNKNOWN)"
    assert unknown["Pilot-Audit für diesen Fingerabdruck"] == "nicht erfasst (UNKNOWN)"
    failed = states(replace(ALL_R2, negative_control=False))
    assert failed["Negativkontrolle bestanden"] == "durchgefallen"
    assert failed["Positivkontrolle bestanden"] == "bestanden"


def test_after_holm_the_text_claims_no_uncorrected_sensitivity() -> None:
    both = _assess(_finding("a"), _finding("b", variant="rev-var2", first_seed=600))
    assert both["a"]["urteil"] == m.NO_DIFFERENCE
    assert "nach Holm" in str(both["a"]["urteil_text"])
    assert "ab 20.0 pp" not in str(both["a"]["urteil_text"]) and both["a"]["y_pp"] is None


# -- verdict in four steps ---------------------------------------------------------------------


def test_verdict_in_four_steps() -> None:
    # one table each: five confirmations of one table would be one Holm family
    got = _assess(
        _finding("better", table_hash="a"),
        _finding("worse", wins=0, losses=6, table_hash="b"),
        _finding("none", wins=1, losses=1, ties=4, detectable=12.5, table_hash="c"),
        _finding("unknown_y", wins=1, losses=1, ties=4, detectable=None, table_hash="d"),
        _finding("contradiction", difference_pp=-3.0, table_hash="e"),
    )
    assert got["better"]["urteil"] == m.BETTER
    assert got["worse"]["urteil"] == m.WORSE
    assert got["none"]["urteil_text"] == (
        "kein nachweisbarer Unterschied ab 12.5 pp (y = nachweisbar mit 80 % Power)"
    )
    assert got["better"]["belegt"] is True and got["none"]["belegt"] is False
    assert got["unknown_y"]["urteil"] == m.NOT_EVALUABLE  # never "ab 0 pp"
    assert got["contradiction"]["urteil"] == m.NOT_EVALUABLE
    assert {str(v["urteil"]) for v in got.values()} <= set(m.VERDICTS)


# -- state relation and "empfehlungsfähig" ----------------------------------------------------


def test_a_finding_of_another_state_is_never_shown_as_current() -> None:
    got = _assess(
        _finding("cur", base="rev-main"),
        _finding("adopted", base="rev-prev", variant="rev-main", first_seed=600),
        _finding("prev", base="rev-prev", variant="rev-x", first_seed=700, table_hash="t2"),
        _finding("old", base="rev-old", variant="rev-y", first_seed=800, table_hash="t3"),
        checks={s: ALL_R3 for s in ("cur", "adopted", "prev", "old")},
    )
    assert got["cur"]["stand"]["bezug"] == m.CURRENT  # type: ignore[index]
    assert got["adopted"]["stand"]["bezug"] == m.CURRENT  # type: ignore[index]
    assert got["prev"]["stand"]["bezug"] == m.PREDECESSOR  # type: ignore[index]
    old = got["old"]["stand"]
    assert old == {  # the state is named with its own hash, never the current one
        "bezug": m.OTHER,
        "text": "Befund zu einem anderen Stand (nicht der aktuelle)",
        "revision_id": "rev-old",
        "deck_hash": "h-old",
    }
    assert got["old"]["empfehlungsfaehig"] is False
    assert got["prev"]["empfehlungsfaehig"] is True


def test_empfehlungsfaehig_needs_r2_current_fingerprint_and_jar() -> None:
    def ok(finding: m.Finding, checks: m.Checks = ALL_R2, current: m.Current = CUR) -> bool:
        got = _assess(finding, checks={finding.series_id: checks}, current=current)
        return bool(got[finding.series_id]["empfehlungsfaehig"])

    assert ok(_finding("c"))
    assert not ok(_finding("c"), checks=m.NO_CHECKS)  # R1 only
    assert not ok(_finding("c", fingerprint_now="0" * 64))
    assert not ok(_finding("c", fingerprint=None))
    assert not ok(_finding("c", jars=["0" * 64]))
    assert not ok(_finding("c", jars=[]))
    assert not ok(_finding("c"), current=replace(CUR, bridge_jar_sha256=None))


def test_tam_gets_no_simulation_badge() -> None:
    out = m.assess(
        [_finding("c")], explorations=[], hashes={}, current=CUR, tam=True, checks={"c": ALL_R3}
    )
    befund = out["befunde"]["c"]  # type: ignore[index]
    assert befund["stufe"] is None and befund["empfehlungsfaehig"] is False
    assert out["tam_sperre"] == m.TAM_LOCK
    assert m.TAM_LOCK in befund["empfehlungsfaehig_gruende"]
    # no result text either: only the lock, no "belegt", no p-value, no y
    assert befund["urteil"] == m.NOT_EVALUABLE and befund["belegt"] is False
    assert befund["urteil_text"] == f"kein Ergebnis gezeigt ({m.TAM_LOCK})"
    assert befund["effektives_p"] is None and befund["holm_p"] is None and befund["y_pp"] is None


# -- review round 2 (#1717): direction, plan range, boundary, hint below R1, truncated scan -----


def _shared_wins(sid: str, purpose: str = "confirmation") -> m.Finding:
    """20 pairs where B shares a win (credit 1/4: +0.25) and 6 pairs A wins alone (-1)."""
    pairs = [{"seed": 500 + i, "difference": 0.25} for i in range(20)]
    pairs += [{"seed": 520 + i, "difference": -1.0} for i in range(6)]
    base = _finding(sid, purpose=purpose, wins=26)
    mean_pp = 100.0 * (20 * 0.25 - 6) / 26
    entry = {**base.entry, "difference_pp": mean_pp}
    result = {**base.result, "pairs": pairs, "seeds": [500 + i for i in range(26)]}
    return replace(base, entry=entry, result=result)


@pytest.mark.parametrize("purpose", ["confirmation", "exploration"])
def test_shared_wins_mean_and_sign_test_disagree_is_not_evaluable(purpose: str) -> None:
    from commander_lab.engine.rules.full_game_comparison import sign_test_p_value

    finding = _shared_wins("c", purpose)
    # the sign test leans to B (20 : 6, p = 0.009355 by hand), the mean to A (-3.85 pp)
    assert sign_test_p_value(20, 6) == pytest.approx(0.009355, abs=1e-6)
    assert finding.entry["difference_pp"] == pytest.approx(-3.846, abs=1e-3)
    assert m.directions_conflict(finding.result) is True
    assert m.verdict_basis("c", finding.result) is None  # no direction: no verdict basis
    got = _assess(finding)["c"]
    assert got["urteil"] == m.NOT_EVALUABLE and got["belegt"] is False
    assert got["urteil_text"] == (
        "nicht auswertbar (Mittelwert und Vorzeichentest zeigen in verschiedene Richtungen)"
    )
    assert "belegt" not in str(got["urteil_text"]) and got["stufe"] is None
    # whole credits keep the engine lane's direction: 6 : 0 is the sign test's way
    plain = m.verdict_basis("p", _finding("p").result)
    assert plain is not None and plain.verdict == "VARIANT_BETTER"


def test_a_plan_range_overlapping_an_exploration_is_not_fresh() -> None:
    # played seeds 500..505 miss the exploration 550..560, the planned range 500..600 does not
    clean = _finding("c", plan_range=[500, 600])
    assert _assess(clean)["c"]["stufe"] == m.R1
    got = _assess(clean, explorations=[(100, 199), (550, 560)])["c"]
    assert got["stufe"] == m.R0
    fresh = next(c for c in got["bedingungen"] if c["stufe"] == m.R1 and "frische" in c["name"])  # type: ignore[attr-defined]
    assert fresh["erfuellt"] is False


def test_a_plan_range_touching_an_exploration_at_one_seed_is_not_fresh() -> None:
    # the planned range 500..600 contains the exploration's first seed 600; the played seeds
    # 500..505 do not, so only the closed range check sees it (#1666, lead review of #1717)
    touching = _finding("t", plan_range=[500, 600])
    got = _assess(touching, explorations=[(600, 650)])["t"]
    assert got["stufe"] == m.R0
    fresh = next(c for c in got["bedingungen"] if c["stufe"] == m.R1 and "frische" in c["name"])  # type: ignore[attr-defined]
    assert fresh["erfuellt"] is False
    # one seed further out is disjoint again
    assert _assess(touching, explorations=[(601, 650)])["t"]["stufe"] == m.R1


def test_decided_only_strictly_below_the_level() -> None:
    basis = m.verdict_basis("c", _finding("c").result)  # 6 : 0, p = 2 * 0.5**6 = 0.03125
    assert basis is not None and basis.effective_p_value == pytest.approx(0.03125)
    assert m.decide(basis, 0.03125).verdict == "NO_CLEAR_DIFFERENCE"  # p == alpha: not decided
    assert m.decide(basis, 0.03126).verdict == "VARIANT_BETTER"


def test_below_r1_a_decided_step_is_a_hint_never_belegt() -> None:
    got = _assess(
        _finding("explo", purpose="exploration"),
        _finding("legacy", purpose=None, wins=0, losses=6, first_seed=600, variant="rev-old"),
    )
    assert got["explo"]["stufe"] == m.R0 and got["legacy"]["stufe"] == m.R0
    assert got["explo"]["urteil_text"] == "Hinweis besser (Erkundung, unbestätigt; B gegenüber A)"
    assert got["legacy"]["urteil_text"] == (
        "Hinweis schlechter (Erkundung, unbestätigt; B gegenüber A)"
    )
    for sid in ("explo", "legacy"):
        assert "belegt" not in str(got[sid]["urteil_text"]) and got[sid]["belegt"] is False


def test_a_truncated_scan_makes_fresh_seeds_unknown_not_met() -> None:
    reason = "3 ältere Ergebnisdateien nicht geprüft"
    got = _assess(_finding("c"), seeds_incomplete=reason)["c"]
    assert got["stufe"] == m.R0
    fresh = next(c for c in got["bedingungen"] if "frische" in str(c["name"]))  # type: ignore[attr-defined]
    assert fresh["erfuellt"] is False and fresh["zustand"] == "unbekannt (UNKNOWN)"
    assert fresh["grund"] == f"{reason}: deren Seeds sind unbekannt"


def test_a_member_undecided_at_the_family_level_is_not_withheld_by_holm() -> None:
    # a: 6 : 0, p = 0.03125 < its own 0.05 but not below the family level 0.01: undecided there,
    # so Holm withholds nothing (deciding it at its own level would claim a withheld verdict)
    a = _finding("a", alpha=0.05)
    b = _finding("b", variant="rev-var2", first_seed=600, wins=1, losses=1, ties=4, alpha=0.01)
    got = _assess(a, b)["a"]
    assert got["niveau"] == 0.01 and got["urteil"] == m.NO_DIFFERENCE
    assert "Ergebnis durch Holm zurückgehalten" not in got["hinweise"]  # type: ignore[operator]
    # y (20 pp) holds at the own alpha 0.05 only: at 0.01 the sensitivity is unknown, and the
    # visible note says the verdict decided at 0.05 is withheld at the family level
    assert got["y_pp"] is None
    assert got["urteil_text"] == (
        "kein nachweisbarer Unterschied auf Familienniveau "
        "(Empfindlichkeit auf diesem Niveau unbekannt)"
    )
    assert "ab 20.0 pp" not in str(got["urteil_text"])
    assert (
        "Ergebnis auf dem kleineren Familienniveau zurückgehalten "
        "(auf dem eigenen Niveau der Serie entschieden)"
    ) in got["hinweise"]  # type: ignore[operator]
    # the member at the family level keeps its own y: its level is the family level
    assert _assess(a, b)["b"]["y_pp"] == 20.0


def test_mean_exactly_zero_with_a_leaning_sign_test_is_not_evaluable() -> None:
    # 24 pairs B shares a win (+0.25), 6 pairs A wins alone (-1): mean 0, sign test 24 : 6
    pairs = [{"seed": 500 + i, "difference": 0.25} for i in range(24)]
    pairs += [{"seed": 524 + i, "difference": -1.0} for i in range(6)]
    base = _finding("c", wins=30)
    finding = replace(
        base,
        entry={**base.entry, "difference_pp": 0.0},
        result={**base.result, "pairs": pairs, "seeds": [500 + i for i in range(30)]},
    )
    assert sum(float(str(p["difference"])) for p in pairs) == 0.0
    assert m.directions_conflict(finding.result) is True
    got = _assess(finding)["c"]
    assert got["urteil"] == m.NOT_EVALUABLE and got["belegt"] is False
    assert "verschiedene Richtungen" in str(got["urteil_text"])


# -- the route: production wiring, no mixing, no store write ----------------------------------


def test_route_gives_r0_and_r1_and_only_simulated_figures(
    monkeypatch: pytest.MonkeyPatch,
    lab: dict[str, object],  # noqa: F811
) -> None:
    monkeypatch.setenv("COMMANDER_LAB_CACHE_CHECK", "1")
    revs = lab["revs"]
    assert isinstance(revs, dict)
    tx._start(lab, tx._plan(revs, purpose="exploration", first_seed=100))
    tx._start(
        lab,
        tx._plan(
            revs,
            purpose="confirmation",
            first_seed=900,
            variants=[{"revision_id": revs["variant2"]}],
        ),
    )
    body = tx._history(lab)
    reife = body["reifegrad"]
    assert reife["data_class"] == "SIMULATED_RESULT"
    befunde = reife["befunde"]
    by_purpose = {
        str(item["experiment"]["purpose"]): befunde[item["series_id"]] for item in body["series"]
    }
    explo, conf = by_purpose["exploration"], by_purpose["confirmation"]
    # The lab's player lets the variant win every game: zero spread over one seed is no verdict
    # basis, so neither series gets a level (fail-closed), although the confirmation has fresh
    # seeds and its Holm step.
    for befund in (explo, conf):
        assert befund["stufe"] is None and befund["urteil"] == m.NOT_EVALUABLE
        assert befund["empfehlungsfaehig"] is False
        assert befund["n"] == 4 and befund["N"] == 4
    met = {c["name"]: c["erfuellt"] for c in conf["bedingungen"]}
    assert met["Bestätigung mit intaktem Plan"] is True
    assert met["frische Seeds (disjunkt von jeder Erkundung des Decks)"] is True
    assert met["Holm angewandt"] is True
    assert met["Positivkontrolle bestanden"] is False  # production records no controls
    explo_met = {c["name"]: c["erfuellt"] for c in explo["bedingungen"]}
    assert explo_met["Bestätigung mit intaktem Plan"] is False
    # re-checked when read: an exploration indexed after the confirmation on its seeds
    store = StudioStore.open(Path(str(lab["folder"])))
    try:
        with store.connection:
            store.connection.execute(
                "INSERT INTO experiment(experiment_id, deck_id, question, purpose, "
                "base_revision_id, first_seed, last_seed, created_at) VALUES "
                "('exp-late', 'chulane-b2', 'spät', 'exploration', ?, 900, 900, '2026-11-20')",
                (revs["base"],),
            )
    finally:
        store.close()
    again = tx._history(lab)
    conf_again = next(
        again["reifegrad"]["befunde"][item["series_id"]]
        for item in again["series"]
        if item["experiment"] and item["experiment"]["purpose"] == "confirmation"
    )
    late = {c["name"]: c["erfuellt"] for c in conf_again["bedingungen"]}
    assert late["frische Seeds (disjunkt von jeder Erkundung des Decks)"] is False
    assert conf_again["stufe"] not in (m.R1, m.R2, m.R3)
    # never mixed: every figure of the answer is one simulated class, no sum of classes
    assert body["zahlen"], "the series carry their SIMULIERT figure"
    for zahl in body["zahlen"]:
        assert nc.check(zahl) == []
        assert zahl["klasse"] == nc.SIMULIERT and zahl["data_class"] == "SIMULATED_RESULT"
    text = json.dumps(reife, ensure_ascii=False).casefold()
    for word in ("summe", "gesamt", "total", "edhrec", "playgroup", "turnier", "gezählt"):
        assert word not in text, word
    # a bounded folder scan leaves seeds of older series unknown: fresh seeds UNKNOWN, no R1
    from commander_lab.studio import deck_series

    played = sorted(Path(str(lab["folder"])).rglob("paired-*.paired.json"))
    assert played, "the lab stores its series files"
    (played[0].parent / "paired-0-unindexed.paired.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(deck_series, "SCAN_LIMIT", 0)  # the unindexed file stays unscanned
    bounded = tx._history(lab)
    assert bounded["scan_truncated"] > 0
    for befund in bounded["reifegrad"]["befunde"].values():
        fresh = next(c for c in befund["bedingungen"] if "frische" in c["name"])
        assert fresh["zustand"] == "unbekannt (UNKNOWN)" and fresh["erfuellt"] is False
        assert "ältere Ergebnisdateien nicht geprüft" in fresh["grund"]


def test_route_takes_no_checks_from_the_request() -> None:
    import inspect

    from commander_lab.studio import web

    source = inspect.getsource(web)
    route = source[source.index('@app.get("/api/decks/{deck_id}/series")') :]
    route = route[: route.index("@app.", 10)]
    assert "def deck_paired_series(deck_id: str)" in route
    assert "checks" not in route and "Checks(" not in route
    assert "cache.write" not in route  # reads only


# -- the page ----------------------------------------------------------------------------------


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed: deckseries.js evidence row NOT_RUN, not a pass")
    return node


_JS = r"""
const vm = require("vm");
const fs = require("fs");
function h(tag, attrs, ...kids) { return { tag, attrs: attrs || {}, kids: kids.flat(9).filter((k) => k !== null && k !== undefined && k !== false) }; }
const text = (n) => typeof n === "string" ? n : n.kids.map(text).join("");
const pills = (n) => typeof n === "string" ? [] : [...(n.attrs.class === "pill good" ? [text(n)] : []), ...n.kids.flatMap(pills)];
globalThis.StudioUI = { num: (v) => String(v) };
vm.runInThisContext(fs.readFileSync(__SERIES__, "utf8"));
const base = { stufe: null, stufe_text: "kein Reifegrad (Beleg fehlt)", urteil_text: "nicht auswertbar (keine Auswertungsbasis)",
  n: 4, N: 4, bezug: "Paare (abgeschlossen / geplant)", stand: { bezug: "anderer_stand", text: "Befund zu einem anderen Stand (nicht der aktuelle)" },
  empfehlungsfaehig: false, empfehlungsfaehig_gruende: ["Reifegrad unter R2"], hinweise: [] };
const none = deckSeriesEvidence(h, base);
const missing = deckSeriesEvidence(h, undefined);
const r1 = deckSeriesEvidence(h, { ...base, stufe: "R1", stufe_text: "R1 bestätigt (frische Seeds, Holm)", urteil_text: "belegt besser (B gegenüber A)",
  stand: { bezug: "aktuell", text: "Befund zum aktuellen Stand" } });
const r0 = deckSeriesEvidence(h, { ...base, stufe: "R0", stufe_text: "R0 Erkundung" });
const r0cls = (function find(n) { if (typeof n === "string") return null; if (text(n) === "R0 Erkundung" && n.tag === "span") return n.attrs.class; for (const k of n.kids) { const c = find(k); if (c) return c; } return null; })(r0);
const r2 = deckSeriesEvidence(h, { ...base, stufe: "R2", stufe_text: "R2 bestätigt mit Kontrollen", empfehlungsfaehig: true, empfehlungsfaehig_gruende: [],
  stand: { bezug: "aktuell", text: "Befund zum aktuellen Stand" } });
process.stdout.write(JSON.stringify({ none: [text(none), pills(none)], missing: [text(missing), pills(missing)],
  r1: [text(r1), pills(r1)], r2: [text(r2), pills(r2)], r0: [text(r0), pills(r0), r0cls] }));
"""


def test_evidence_row_shows_no_badge_without_proof_and_names_other_states() -> None:
    node = _node()
    script = _JS.replace("__SERIES__", json.dumps(str(STATIC / "deckseries.js")))
    done = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, timeout=30, check=True
    )
    r = json.loads(done.stdout)
    assert r["none"][1] == [] and r["missing"][1] == []  # no badge without a level
    assert "Befund zu einem anderen Stand (nicht der aktuelle)" in r["none"][0]
    assert "nicht empfehlungsfähig: Reifegrad unter R2" in r["none"][0]
    assert r["r1"][1] == ["R1 bestätigt (frische Seeds, Holm)"]
    assert "n/N 4 / 4 Paare (abgeschlossen / geplant)" in r["r1"][0]
    assert r["r2"][1] == ["R2 bestätigt mit Kontrollen", "empfehlungsfähig"]
    assert r["r0"][1] == [] and r["r0"][2] == "pill"  # R0 exploration: neutral, never green


def test_evidence_row_static_guards() -> None:
    js = (STATIC / "deckseries.js").read_text(encoding="utf-8")
    row = js[js.index("function deckSeriesEvidence") : js.index("function deckSeriesRefLabel")]
    for forbidden in ("innerHTML", "outerHTML", "style:", "eval(", "EDHREC", "Playgroup", "+="):
        assert forbidden not in row, forbidden
    # the badge and the flag come only from the answer, never from a local rule
    assert re.search(r"befund\.stufe \?", row) and "befund.empfehlungsfaehig" in row
    assert "R2" not in row and "R3" not in row
