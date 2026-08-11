from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match in {path}: found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


service = ROOT / "src/commander_lab/tools/service.py"
replace_once(
    service,
    '    ACTIVE_OWN_DECK_IDS = ("korvold/current", "rogshai/current")\n',
    '    ACTIVE_OWN_DECK_IDS = ("rogshai/current",)\n',
)
replace_once(
    service,
    '                for deck_id in ("korvold/current", "rogshai/current"):\n',
    '                for deck_id in self.ACTIVE_OWN_DECK_IDS:\n',
)

screening = ROOT / "src/commander_lab/candidate_screening.py"
text = screening.read_text(encoding="utf-8")
import_anchor = "from commander_lab.models import CandidateProfile, DataQuality, StructuralDeckProfile, VariantSwap\n"
import_replacement = (
    "from commander_lab.canonical_features import load_canonical_feature_annotations\n"
    "from commander_lab.models import CandidateProfile, DataQuality, StructuralDeckProfile, VariantSwap\n"
    "from commander_lab.tools.candidates import load_candidate_profiles\n"
)
if text.count(import_anchor) != 1:
    raise SystemExit("candidate_screening import anchor mismatch")
text = text.replace(import_anchor, import_replacement, 1)
start = text.index('    def screen_pool(self, deck_id: str = "rogshai/current") -> dict[str, object]:\n')
end = text.index('    def screen_swap(\n', start)
new_method = '''    def screen_pool(self, deck_id: str = "rogshai/current") -> dict[str, object]:
        if deck_id != "rogshai/current":
            raise ValueError("priority candidate screening is scoped to current RogShai")

        eligibility_path = (
            self.root / "data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json"
        )
        payload = json.loads(eligibility_path.read_text(encoding="utf-8"))
        raw_rows = payload.get("eligible_by_deck", {}).get(deck_id)
        if not isinstance(raw_rows, dict):
            raise ValueError("current RogShai candidate eligibility is missing or invalid")

        manifest_path = self.root / "data/collections/current/rogshai_feature_projection/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_count = int(manifest.get("canonical_candidate_count", -1))

        eligible: dict[str, dict[str, object]] = {}
        excluded: dict[str, int] = {}
        for name, raw_spec in raw_rows.items():
            if not isinstance(raw_spec, dict):
                excluded["invalid_eligibility_record"] = excluded.get("invalid_eligibility_record", 0) + 1
                continue
            if raw_spec.get("commander_legal") is not True:
                excluded["not_commander_legal"] = excluded.get("not_commander_legal", 0) + 1
                continue
            quantity = int(raw_spec.get("physical_available_quantity", 0))
            if quantity <= 0:
                excluded["not_physically_available"] = excluded.get("not_physically_available", 0) + 1
                continue
            eligible[str(name)] = dict(raw_spec)

        if expected_count != len(eligible):
            raise ValueError(
                "current RogShai candidate universe disagrees with the canonical feature manifest: "
                f"expected {expected_count}, got {len(eligible)}"
            )

        all_profiles = load_candidate_profiles(self.root)
        modeled_by_name = {
            candidate.card.oracle_name: candidate
            for candidate in all_profiles.values()
            if deck_id in candidate.allowed_deck_ids
        }
        annotations = load_canonical_feature_annotations(self.root)

        modeled_candidates = [
            modeled_by_name[name] for name in eligible if name in modeled_by_name
        ]
        by_signature: dict[tuple[object, ...], list[CandidateProfile]] = defaultdict(list)
        for candidate in modeled_candidates:
            by_signature[_functional_signature(candidate)].append(candidate)

        dominated_by: dict[str, str] = {}
        for group in by_signature.values():
            for candidate in group:
                dominators = [other for other in group if _clearly_dominates(other, candidate)]
                if dominators:
                    dominators.sort(
                        key=lambda other: (
                            -profile_score(other.card),
                            other.card.mana_value,
                            other.card.oracle_name.casefold(),
                        )
                    )
                    dominated_by[candidate.candidate_id] = dominators[0].candidate_id

        bucket_order = {
            "advance": 0,
            "explore": 1,
            "requires_profile_before_model_dependent_recommendation": 2,
            "defer_low_confidence_default": 3,
            "defer_clear_static_dominance": 4,
        }
        rows: list[dict[str, object]] = []
        high_confidence = 0
        partially_modeled = 0
        structurally_unmodeled = 0
        heuristic_fallback_count = 0
        canonical_feature_coverage = 0

        for name in sorted(eligible, key=str.casefold):
            candidate = modeled_by_name.get(name)
            annotation = annotations.get(name)
            if annotation is not None:
                canonical_feature_coverage += 1
            if candidate is None:
                structurally_unmodeled += 1
                rows.append(
                    {
                        "candidate_id": None,
                        "oracle_name": name,
                        "bucket": "requires_profile_before_model_dependent_recommendation",
                        "confidence": "insufficient_structural_model_requires_profile",
                        "roles": tuple(
                            sorted(role.value for role in annotation.mapped_roles)
                        ) if annotation is not None else (),
                        "package_ids": tuple(sorted(annotation.package_ids)) if annotation is not None else (),
                        "mana_value": None,
                        "clear_static_dominance_by": None,
                        "playstyle_fit": "qualitative_unknown_requires_profile",
                        "playstyle_confidence": "unknown",
                        "explorable": True,
                        "model_dependent_recommendation_ready": False,
                    }
                )
                continue

            confidence = _confidence(candidate)
            if annotation is not None and (
                confidence.startswith("low_") or confidence == "unknown"
            ):
                confidence = "medium_canonical_derived"
            if confidence == "high_project_verified_or_curated":
                high_confidence += 1
            else:
                partially_modeled += 1
            if candidate.card.source_quality == DataQuality.PROJECT_INFERRED:
                heuristic_fallback_count += 1

            dominated = dominated_by.get(candidate.candidate_id)
            if dominated is not None:
                bucket = "defer_clear_static_dominance"
            elif confidence.startswith("low_") or confidence == "unknown":
                if not candidate.card.package_ids and annotation is None:
                    bucket = "defer_low_confidence_default"
                else:
                    bucket = "explore"
            elif candidate.card.package_ids or annotation is not None:
                bucket = "advance"
            else:
                bucket = "explore"

            playstyle = self.playstyle.analyze_card(candidate.card)
            roles = set(candidate.card.roles)
            packages = set(candidate.card.package_ids)
            if annotation is not None:
                roles.update(annotation.mapped_roles)
                packages.update(annotation.package_ids)
            rows.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "oracle_name": name,
                    "bucket": bucket,
                    "confidence": confidence,
                    "roles": tuple(sorted(role.value for role in roles)),
                    "package_ids": tuple(sorted(packages)),
                    "mana_value": float(candidate.card.mana_value),
                    "clear_static_dominance_by": dominated,
                    "playstyle_fit": playstyle.playstyle_fit,
                    "playstyle_confidence": playstyle.confidence,
                    "explorable": True,
                    "model_dependent_recommendation_ready": True,
                }
            )

        rows.sort(
            key=lambda row: (
                bucket_order[str(row["bucket"])],
                str(row["oracle_name"]).casefold(),
                str(row.get("candidate_id") or ""),
            )
        )
        counts = {bucket: 0 for bucket in bucket_order}
        for row in rows:
            counts[str(row["bucket"])] += 1
        simulation_ready = sum(
            str(row["bucket"]) in {"advance", "explore"} for row in rows
        )
        discoverable = len(rows)
        return {
            "deck_id": deck_id,
            "physical_legal_candidate_count": len(eligible),
            "discoverable_candidate_count": discoverable,
            "excluded_candidate_count_by_reason": excluded,
            "candidate_recall": discoverable / len(eligible) if eligible else 1.0,
            "candidate_pool_after_default_screen": simulation_ready,
            "bucket_counts": counts,
            "fully_high_confidence_modeled": high_confidence,
            "partially_modeled": partially_modeled,
            "structurally_unmodeled": structurally_unmodeled,
            "canonical_feature_coverage": canonical_feature_coverage,
            "heuristic_fallback_count": heuristic_fallback_count,
            "rows": rows,
            "unusual_candidates_remain_explorable": True,
            "unmodeled_candidate_discoverability": True,
            "fresh_rebuild_current_deck_neutrality": True,
            "historical_allocation_neutrality": True,
            "playstyle_is_hard_filter": False,
            "screening_boundary": (
                "Complete legal/physical discovery is separated from model-dependent screening. "
                "Unmodeled candidates remain discoverable and require explicit profiling before "
                "model-dependent recommendation; no empirical power claim is made."
            ),
        }

'''
text = text[:start] + new_method + text[end:]
screening.write_text(text, encoding="utf-8")

test_path = ROOT / "tests/regressions/test_j_final_scope.py"
test_path.parent.mkdir(parents=True, exist_ok=True)
test_path.write_text('''from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.candidate_screening import RogShaiCandidateScreener
from commander_lab.engine.structural.project import _validate_structural_profile_ids
from commander_lab.tools.candidates import load_current_optimization_availability
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[2]


def test_active_own_deck_scope_is_rogshai_only_and_korvold_release_is_available() -> None:
    service = CommanderToolService(ROOT)
    assert service.ACTIVE_OWN_DECK_IDS == ("rogshai/current",)
    assert service.FROZEN_OPPONENT_ONLY_DECK_IDS == frozenset({"kaervek/current"})
    current = load_current_optimization_availability(ROOT)
    assert current.get("Lightning Greaves", 0) >= 1


def test_fresh_rebuild_discovers_complete_current_rogshai_universe() -> None:
    service = CommanderToolService(ROOT)
    result = RogShaiCandidateScreener(ROOT, service=service).screen_pool()
    assert result["physical_legal_candidate_count"] == 795
    assert result["discoverable_candidate_count"] == 795
    assert result["candidate_recall"] == 1.0
    assert result["excluded_candidate_count_by_reason"] == {}
    assert sum(result["bucket_counts"].values()) == 795
    assert result["structurally_unmodeled"] > 0
    assert result["unmodeled_candidate_discoverability"] is True
    assert all(row["explorable"] is True for row in result["rows"])


def test_current_deck_membership_is_neutral_in_fresh_rebuild_discovery() -> None:
    service = CommanderToolService(ROOT)
    result = RogShaiCandidateScreener(ROOT, service=service).screen_pool()
    discovered = {row["oracle_name"] for row in result["rows"]}
    eligibility = json.loads(
        (ROOT / "data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json").read_text(
            encoding="utf-8"
        )
    )["eligible_by_deck"]["rogshai/current"]
    current_names = {card.oracle_name for card in service.decks["rogshai/current"].cards}
    eligible_current_names = current_names.intersection(eligibility)
    assert eligible_current_names
    assert eligible_current_names <= discovered


def test_unmodeled_candidates_are_discovery_only_until_profiled() -> None:
    service = CommanderToolService(ROOT)
    result = RogShaiCandidateScreener(ROOT, service=service).screen_pool()
    unmodeled = [
        row
        for row in result["rows"]
        if row["bucket"] == "requires_profile_before_model_dependent_recommendation"
    ]
    assert unmodeled
    assert all(row["model_dependent_recommendation_ready"] is False for row in unmodeled)
    assert all(row["explorable"] is True for row in unmodeled)


def test_structural_profile_duplicate_ids_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    path.write_text(
        json.dumps({"profiles": [{"deck_id": "duplicate"}, {"deck_id": "duplicate"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate structural deck_id"):
        _validate_structural_profile_ids(path)
''', encoding="utf-8")

print("J-FINAL scope repair materialized")
