from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one repair target in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


service = ROOT / "src/commander_lab/tools/service.py"
replace_once(
    service,
    '    ACTIVE_OWN_DECK_IDS = ("korvold/current", "rogshai/current")\n',
    '    ACTIVE_OWN_DECK_IDS = ("rogshai/current",)\n'
    '    HISTORICAL_OWN_DECK_IDS = ("korvold/current",)\n',
)
replace_once(
    service,
    '                for deck_id in ("korvold/current", "rogshai/current"):\n',
    '                for deck_id in self.ACTIVE_OWN_DECK_IDS:\n',
)

fresh = ROOT / "src/commander_lab/fresh_rebuild.py"
replace_once(
    fresh,
    '    rows = _candidate_rows(project, contract)\n'
    '    reservations = _korvold_nonbasic_reservations(project)\n'
    '    profiles = _explicit_profiles(project)\n',
    '    rows = _candidate_rows(project, contract)\n'
    '    profiles = _explicit_profiles(project)\n'
    '    eligibility_path = (\n'
    '        project / "data/collections/current/J_P5_CURRENT_CANDIDATE_ELIGIBILITY.json"\n'
    '    )\n'
    '    eligibility_payload = json.loads(eligibility_path.read_text(encoding="utf-8"))\n'
    '    eligible_by_deck = eligibility_payload.get("eligible_by_deck", {})\n'
    '    current_eligibility = eligible_by_deck.get(ROGSHAI_DECK_ID)\n'
    '    if not isinstance(current_eligibility, dict):\n'
    '        raise FreshRebuildDataError("current RogShai eligibility projection is missing")\n'
    '    active_scope = json.loads(\n'
    '        (project / "data/collections/current/J_FINAL_ACTIVE_SCOPE.json").read_text(\n'
    '            encoding="utf-8"\n'
    '        )\n'
    '    )\n'
    '    if active_scope.get("active_own_decks") != [ROGSHAI_DECK_ID]:\n'
    '        raise FreshRebuildDataError("fresh rebuild requires RogShai as sole active own deck")\n'
    '    if active_scope.get("historical_allocation_blocks_active_deck") is not False:\n'
    '        raise FreshRebuildDataError("historical allocation still blocks active RogShai")\n'
    '    manifest = json.loads(\n'
    '        (\n'
    '            project\n'
    '            / "data/collections/current/rogshai_feature_projection/manifest.json"\n'
    '        ).read_text(encoding="utf-8")\n'
    '    )\n'
    '    scope_candidate = active_scope.get("sources", {}).get(\n'
    '        "ROGSHAI_CANDIDATE_POOL_CURRENT.jsonl", {}\n'
    '    )\n'
    '    feature_candidate = manifest.get("source_artifacts", {}).get(\n'
    '        "ROGSHAI_CANDIDATE_POOL_CURRENT.jsonl", {}\n'
    '    )\n'
    '    if scope_candidate.get("sha256") != feature_candidate.get("sha256"):\n'
    '        raise FreshRebuildDataError("current candidate-source identities disagree")\n'
    '    if int(manifest.get("canonical_candidate_count", 0)) != int(pool["expected_count"]):\n'
    '        raise FreshRebuildDataError("current candidate count disagrees with MVP coverage contract")\n',
)
replace_once(
    fresh,
    '        quantity = _as_int(row.get("quantity", 0))\n'
    '        available[name] = (\n'
    '            max(50, quantity)\n'
    '            if name in BASIC_LANDS\n'
    '            else max(0, quantity - reservations.get(name, 0))\n'
    '        )\n',
    '        eligibility = current_eligibility.get(name)\n'
    '        if not isinstance(eligibility, dict):\n'
    '            raise FreshRebuildDataError(\n'
    '                f"current RogShai eligibility missing candidate: {name}"\n'
    '            )\n'
    '        if eligibility.get("commander_legal") is not True:\n'
    '            raise FreshRebuildDataError(f"current eligibility marks {name} nonlegal")\n'
    '        quantity = _as_int(eligibility.get("physical_available_quantity", 0))\n'
    '        if quantity <= 0:\n'
    '            raise FreshRebuildDataError(f"current eligibility marks {name} unavailable")\n'
    '        available[name] = max(50, quantity) if name in BASIC_LANDS else quantity\n',
)
replace_once(
    fresh,
    '            "korvold_reservations": sorted(reservations.items()),\n',
    '            "current_rogshai_eligibility": eligibility_payload,\n'
    '            "current_candidate_source_sha256": scope_candidate.get("sha256"),\n',
)

workflow = ROOT / "src/commander_lab/priority_workflows.py"
replace_once(
    workflow,
    'from commander_lab.decision_bundle import DecisionBundle, write_decision_bundle\n',
    'from commander_lab.decision_bundle import DecisionBundle, write_decision_bundle\n'
    'from commander_lab.fresh_rebuild import (\n'
    '    load_fresh_rebuild_runtime,\n'
    '    load_fresh_rogshai_universe,\n'
    ')\n',
)
old_block = '''        baseline = self._deck(deck_id)\n        screened = self.screener.screen_pool(deck_id)\n        rows = screened["rows"]\n        if not isinstance(rows, list):\n            raise RuntimeError("candidate screen rows must be a list")\n        return {\n            "workflow": "build_screen",\n            "evidence_class": "structural_candidate_screening",\n            "deck_id": deck_id,\n            "deck_hash": baseline.deck_hash,\n            "context": self._context_payload(self.context),\n            "eligible_candidate_count": screened["physical_legal_candidate_count"],\n            "candidate_pool_after_default_screen": screened["candidate_pool_after_default_screen"],\n            "bucket_counts": screened["bucket_counts"],\n            "feature_fusion": canonical_feature_fusion_summary(self.root),\n            "challenge_benchmark": self.screener.benchmark_challenge_set(),\n            "mana": asdict(self.mana.analyze_deck(baseline)),\n            "candidates": rows[:limit],\n            "unusual_candidates_remain_explorable": True,\n            "playstyle_is_hard_filter": False,\n            "ranking_claim": (\n                "conservative static structural screen only; no empirical card-power ranking"\n            ),\n        }\n'''
new_block = '''        baseline = self._deck(deck_id)\n        fresh = load_fresh_rogshai_universe(self.root)\n        runtime = load_fresh_rebuild_runtime(self.root)\n        coverage = runtime["candidate_universe"]["coverage_counts"]\n        modeled_by_name = fresh.candidate_by_name()\n        discovery_rows: list[dict[str, Any]] = []\n        for name in sorted(fresh.candidate_names, key=str.casefold):\n            candidate = modeled_by_name.get(name)\n            status = fresh.coverage_status_by_name.get(name, "REVIEW_REQUIRED")\n            discovery_rows.append(\n                {\n                    "candidate_id": candidate.candidate_id if candidate is not None else None,\n                    "oracle_name": name,\n                    "coverage_status": status,\n                    "physical_available_quantity": fresh.available_quantities.get(name, 0),\n                    "model_dependent_evaluation_ready": candidate is not None,\n                    "requires_profile_before_model_dependent_recommendation": candidate is None,\n                    "explorable": True,\n                    "historical_deck_membership_quality_prior": False,\n                    "current_deck_membership_quality_prior": False,\n                }\n            )\n        candidate_recall = len(discovery_rows) / fresh.candidate_count\n        return {\n            "workflow": "build_screen",\n            "evidence_class": "structural_candidate_screening",\n            "deck_id": deck_id,\n            "deck_hash": baseline.deck_hash,\n            "context": self._context_payload(self.context),\n            "eligible_candidate_count": fresh.candidate_count,\n            "legal_physical_candidate_count": fresh.candidate_count,\n            "discoverable_candidate_count": len(discovery_rows),\n            "excluded_candidate_count_by_reason": {},\n            "candidate_recall": candidate_recall,\n            "candidate_pool_after_default_screen": fresh.structurally_scorable_count,\n            "fully_high_confidence_modeled": int(coverage["STRUCTURALLY_MODELED"]),\n            "partially_modeled": int(coverage["PARTIALLY_MODELED"]),\n            "structurally_unmodeled": int(coverage["STRUCTURALLY_UNMODELED"]),\n            "unmodeled_candidate_discoverability": True,\n            "fresh_rebuild_neutrality": {\n                "current_deck_membership_quality_prior": False,\n                "historical_deck_membership_quality_prior": False,\n                "historical_allocation_blocks_active_deck": False,\n            },\n            "feature_fusion": canonical_feature_fusion_summary(self.root),\n            "challenge_benchmark": self.screener.benchmark_challenge_set(),\n            "mana": asdict(self.mana.analyze_deck(baseline)),\n            "candidates": discovery_rows[:limit],\n            "unusual_candidates_remain_explorable": True,\n            "playstyle_is_hard_filter": False,\n            "ranking_claim": (\n                "complete legal/physical Fresh-Rebuild discovery; structural profiling gates "\n                "model-dependent recommendation; no empirical card-power ranking"\n            ),\n        }\n'''
replace_once(workflow, old_block, new_block)

print("J-FINAL scope repair materialized")
