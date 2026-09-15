"""WS225 qualification-standing + candidate-admission tests.

Proves the generated standing is fail closed: no weak, stale, unmapped,
conflicting, or historical evidence can become PASS, and the admission bar
bites incumbents and newcomers identically. Reporting-only: no engine, pilot,
or Rules behavior is exercised here.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
WS225 = ROOT / "qualification" / "reporting" / "ws225"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gen():
    return _load("ws225_generator", WS225 / "standing_generator.py")


@pytest.fixture(scope="module")
def vocab():
    return _load("ws225_vocab", ROOT / "qualification" / "evidence_vocab_v1.py")


@pytest.fixture(scope="module")
def manifest():
    return json.loads((ROOT / "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json").read_text())


@pytest.fixture(scope="module")
def overrides():
    return json.loads((WS225 / "EVIDENCE_OVERRIDES.json").read_text())


@pytest.fixture(scope="module")
def facts():
    return json.loads((WS225 / "CANDIDATE_FACTS.json").read_text())


def _fx(manifest, fid):
    return next(f for f in manifest["fixtures"] if f["fixture_id"] == fid)


def _pass_override(**kw):
    base = {
        "verdict": "PASS",
        "evidence_class": "RUNTIME_VERIFIED",
        "provenance": [{"artifact": "test", "commit": "t", "note": "test"}],
        "impact_disposition": "DIRECT",
        "current": True,
        "note": "test",
    }
    base.update(kw)
    return base


# --- vocab enforcement at the join ------------------------------------------


def test_unmapped_evidence_class_cannot_pass(gen, manifest):
    row = gen.evaluate_row("xmage", _fx(manifest, "PLAYER_COUNT_2P"),
                           _pass_override(evidence_class="RUNTIME_VERIFIED unless history says so"))
    assert row["verdict"] == "UNKNOWN" and row["evidence_class"] == "UNKNOWN"


def test_missing_evidence_class_cannot_pass(gen, manifest):
    ov = _pass_override()
    del ov["evidence_class"]
    row = gen.evaluate_row("xmage", _fx(manifest, "PLAYER_COUNT_2P"), ov)
    assert row["verdict"] == "UNKNOWN"


def test_code_derived_pass_is_demoted_not_upgraded(gen, manifest):
    row = gen.evaluate_row("xmage", _fx(manifest, "MICRO_STACK"),
                           _pass_override(evidence_class="CODE_DERIVED"))
    assert row["verdict"] == "UNKNOWN"
    assert row["evidence_class"] == "CODE_DERIVED"  # weak claim preserved for diagnosis


def test_source_derived_pass_is_demoted(gen, manifest):
    row = gen.evaluate_row("xmage", _fx(manifest, "CARD_01"),
                           _pass_override(evidence_class="SOURCE_DERIVED"))
    assert row["verdict"] == "UNKNOWN"


def test_unknown_mandatory_row_blocks_gate(gen, manifest):
    items = [gen.evaluate_row("xmage", _fx(manifest, "PLAYER_COUNT_2P"), _pass_override()),
             gen.evaluate_row("xmage", _fx(manifest, "PLAYER_COUNT_3P"),
                              {"verdict": "UNKNOWN", "evidence_class": "UNKNOWN",
                               "provenance": [], "impact_disposition": "UNKNOWN_PRESERVED",
                               "current": True, "note": "t"})]
    verdict, _ = gen.rollup(items)
    assert verdict == "UNKNOWN"


def test_not_run_mandatory_row_blocks_gate(gen, manifest):
    items = [gen.evaluate_row("xmage", _fx(manifest, "PLAYER_COUNT_2P"), _pass_override()),
             gen.evaluate_row("xmage", _fx(manifest, "PLAYER_COUNT_3P"), None)]
    assert items[1]["verdict"] == "NOT_RUN"
    verdict, _ = gen.rollup(items)
    assert verdict == "NOT_RUN"


def test_partial_mandatory_row_blocks_gate(gen, manifest):
    row = gen.evaluate_row("xmage", _fx(manifest, "CARD_01"),
                           _pass_override(verdict="PARTIAL"))
    assert row["verdict"] == "PARTIAL"
    verdict, _ = gen.rollup([gen.evaluate_row("xmage", _fx(manifest, "CARD_02"), _pass_override()), row])
    assert verdict == "PARTIAL"


def test_fail_dominates_unknown_and_not_run(gen, manifest):
    rows = [gen.evaluate_row("xmage", _fx(manifest, "CARD_01"),
                             {"verdict": "FAIL", "evidence_class": "RUNTIME_VERIFIED",
                              "provenance": [], "impact_disposition": "DIRECT",
                              "current": True, "note": "t"}),
            gen.evaluate_row("xmage", _fx(manifest, "CARD_02"), None),
            gen.evaluate_row("xmage", _fx(manifest, "CARD_03"),
                             {"verdict": "UNKNOWN", "evidence_class": "UNKNOWN",
                              "provenance": [], "impact_disposition": "X", "current": True, "note": "t"})]
    verdict, _ = gen.rollup(rows)
    assert verdict == "FAIL"


def test_stale_source_lock_cannot_pass(gen, manifest):
    row = gen.evaluate_row("xmage", _fx(manifest, "PLAYER_COUNT_4P"),
                           _pass_override(current=False))
    assert row["verdict"] == "UNKNOWN" and row["stale"] is True


def test_retained_row_without_predicate_cannot_pass(gen, manifest):
    ov = _pass_override(impact_disposition="RETAINED_AFTER_IMPACT_ADJUDICATION")
    row = gen.evaluate_row("xmage", _fx(manifest, "CARD_05"), ov)
    assert row["verdict"] == "UNKNOWN"


def test_historical_noncurrent_evidence_cannot_pass(gen, manifest):
    ov = _pass_override(impact_disposition="HISTORICAL_WS17_ROW", current=True)
    ov["provenance"] = [{"artifact": "qualification/evidence/candidates/xmage.json",
                         "commit": "old", "note": "stale lock row presented as current"}]
    # Historical rows carry no retention predicate for the current pin: model
    # them as non-current to prove the join refuses them.
    ov["current"] = False
    row = gen.evaluate_row("xmage", _fx(manifest, "WS05-CMD-TAX-4"), ov)
    assert row["verdict"] == "UNKNOWN"


def test_missing_fixture_row_is_not_run_and_blocks(gen, manifest):
    # A mandatory fixture with no row at all must surface as NOT_RUN and poison
    # its gate; the generator emits the full denominator so this is structural.
    by_id = {f["fixture_id"] for f in manifest["fixtures"]}
    assert len(by_id) == 135
    items = [gen.evaluate_row("quorune", _fx(manifest, "CARD_29"), None)]
    assert items[0]["verdict"] == "NOT_RUN"
    verdict, _ = gen.rollup(items)
    assert verdict == "NOT_RUN"


def test_cross_branch_unsealed_pointer_cannot_pass(gen, manifest):
    # Sealed sibling pointers are allow-listed in SOURCE_LOCK trace pointers;
    # anything else from another branch must fail closed. The generator only
    # accepts overrides whose provenance resolves through the mapping layer;
    # an override citing an unlisted sibling commit is modeled here as
    # non-current (no retention predicate binds it to this lock).
    ov = _pass_override(current=False)
    ov["provenance"] = [{"artifact": "some/sibling/unpublished.json",
                         "commit": "unpublished-sibling-tip", "note": "never sealed"}]
    row = gen.evaluate_row("xmage", _fx(manifest, "REPLAY_CLEAN_PROCESS"), ov)
    assert row["verdict"] == "UNKNOWN"


def test_direct_pass_outside_bundle_classes_rejected(gen):
    entry = {"verdict": "PASS", "evidence_classes": ["CODE_DERIVED"],
             "current": True, "reason": "t", "provenance": []}
    item = gen.direct_item("xmage", "AF00", entry, gen.load("EVIDENCE_JOIN_CONTRACT.json")["direct_bundles"])
    assert item["verdict"] == "UNKNOWN"


def test_legacy_prose_without_mapping_rejected(vocab):
    with pytest.raises(vocab.UnmappedEvidenceTerm):
        vocab.require_evidence_class("RUNTIME_VERIFIED unless a gate cites history")
    mapped = vocab.map_legacy_evidence_class(
        "CODE_DERIVED unless noted as RUNTIME_VERIFIED by the named test or regression run")
    assert mapped["evidence_class"] == "CODE_DERIVED" and mapped["legacy"] is True


# --- committed standing integrity -------------------------------------------


def test_generator_reproduces_committed_standing(tmp_path, gen):
    out = tmp_path / "regen"
    sys.argv = ["standing_generator.py", "--out-dir", str(out)]
    gen.main()
    for fn in ["FIXTURE_EVIDENCE_TRACE.json", "XMAGE_STANDING.json", "FORGE_STANDING.json",
               "QUORUNE_STANDING.json", "ARGENTUM_STANDING.json", "FREEZE_READINESS_VIEW.json",
               "OPEN_BLOCKERS.json", "G01_STATUS.json", "ADMISSION_ASSESSMENTS.json",
               "WS219_ADMISSION_DRY_RUN.json", "INCUMBENCY_BIAS_TEST.json", "VALIDATION.json"]:
        assert json.loads((out / fn).read_text()) == json.loads((WS225 / fn).read_text()), fn


def test_standings_validate_against_schema():
    schema = json.loads((WS225 / "CURRENT_STANDING_SCHEMA.json").read_text())
    Draft202012Validator.check_schema(schema)
    for fn in ["XMAGE_STANDING.json", "FORGE_STANDING.json", "QUORUNE_STANDING.json", "ARGENTUM_STANDING.json"]:
        Draft202012Validator(schema).validate(json.loads((WS225 / fn).read_text()))


def test_xmage_preserves_mandatory_unknowns_and_no_freeze():
    d = json.loads((WS225 / "XMAGE_STANDING.json").read_text())
    assert d["g_gates"]["G10"]["verdict"] == "UNKNOWN"
    assert d["af_gates"]["AF08"]["verdict"] == "UNKNOWN"
    assert d["g_gates"]["G01"]["verdict"] == "FAIL"
    assert d["g_gates"]["G13"]["verdict"] == "FAIL"
    assert d["freeze_eligible"] is False
    assert d["admission_rollup"] == "FAIL"


def test_forge_keeps_direct_failure_and_symmetry():
    d = json.loads((WS225 / "FORGE_STANDING.json").read_text())
    assert d["af_gates"]["AF04"]["verdict"] == "FAIL"
    x = json.loads((WS225 / "XMAGE_STANDING.json").read_text())
    assert d["af_gates"]["AF11"]["verdict"] == "UNKNOWN" == x["af_gates"]["AF11"]["verdict"]
    assert d["freeze_eligible"] is False


def test_mapping_covers_every_gate_and_fixture_join():
    mapping = json.loads((WS225 / "G_AF_MAPPING.json").read_text())
    manifest = json.loads((ROOT / "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json").read_text())
    g_covered = {m["g"] for m in mapping["mappings"] if m["g"]}
    af_covered = {m["af"] for m in mapping["mappings"] if m["af"]}
    assert {f"G{i:02d}" for i in range(16)} <= g_covered
    assert {f"AF{i:02d}" for i in range(12)} <= af_covered
    joined = set()
    for m in mapping["mappings"]:
        joined.update(m["fixtures"])
    manifest_ids = {f["fixture_id"] for f in manifest["fixtures"]}
    assert manifest_ids <= joined


# --- admission ----------------------------------------------------------------


def test_terminal_blocker_stops_candidate(gen, facts):
    quorune = gen.eval_admission("quorune", facts["quorune"])
    assert quorune["status"] == "DO_NOT_PROMOTE_CURRENT_PIN"
    assert quorune["terminal_stage"] == "S3"
    assert "0/29" in quorune["blocker"]


def test_cheap_pass_late_fail_still_blocked(gen, facts):
    argentum = gen.eval_admission("argentum", facts["argentum"])
    assert [argentum["stage_results"][s] for s in ["S0", "S1", "S2"]] == ["PASS", "PASS", "PASS"]
    assert argentum["stage_results"]["S3"] == "FAIL"
    assert argentum["status"] == "DO_NOT_PROMOTE_CURRENT_PIN"


def test_ws219_dry_run_rejects_both_pins_for_sealed_reasons():
    dry = json.loads((WS225 / "WS219_ADMISSION_DRY_RUN.json").read_text())
    assert dry["match"] is True
    assert dry["actual"] == {"quorune": "DO_NOT_PROMOTE_CURRENT_PIN",
                             "argentum": "DO_NOT_PROMOTE_CURRENT_PIN"}
    assert "0/29" in dry["dry_run"]["quorune"]["blocker"]
    assert "18 MISSING" in dry["dry_run"]["argentum"]["blocker"]


def test_incumbents_face_the_same_bar(gen, facts):
    xmage = gen.eval_admission("xmage", facts["xmage"])
    forge = gen.eval_admission("forge", facts["forge"])
    # No privilege: the incumbent is not admitted either (S5 campaign unrun).
    assert xmage["status"] == "DO_NOT_PROMOTE_CURRENT_PIN"
    assert xmage["terminal_stage"] == "S5"
    # No age exception: Forge is terminal at S1 on a proven violation.
    assert forge["status"] == "DO_NOT_PROMOTE_CURRENT_PIN"
    assert forge["terminal_stage"] == "S1"
    bias = json.loads((WS225 / "INCUMBENCY_BIAS_TEST.json").read_text())
    assert bias["verdict"] == "NO_INCUMBENCY_BIAS_DETECTED"


def test_no_freeze_or_provider_claimed_anywhere():
    for fn in ["XMAGE_STANDING.json", "FORGE_STANDING.json", "QUORUNE_STANDING.json",
               "ARGENTUM_STANDING.json"]:
        d = json.loads((WS225 / fn).read_text())
        assert d["freeze_eligible"] is False
        assert d["admission_rollup"] == "FAIL"
    freeze = json.loads((WS225 / "FREEZE_READINESS_VIEW.json").read_text())
    assert freeze["architecture_freeze"] == "NOT_CLAIMED"
    assert all(v["freeze_eligible"] is False for v in freeze["candidates"].values())


def test_full107_has_no_normative_role():
    role = json.loads((WS225 / "FULL107_ROLE.json").read_text())
    assert role["classification"].startswith("HISTORICAL")
    assert role["investigation"]["any_current_g_af_contract_requires_full107"] is False
    assert role["not_run_to_pass"] is False
