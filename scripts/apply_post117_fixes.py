from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement, found {count}")
    target.write_text(text.replace(old, new), encoding="utf-8")


replace_once("pyproject.toml", 'version = "1.17.0"', 'version = "1.17.1"')
replace_once(
    "src/commander_lab/__init__.py",
    '__version__ = "1.17.0"',
    '__version__ = "1.17.1"',
)
changelog = Path("CHANGELOG.md")
text = changelog.read_text(encoding="utf-8")
marker = "# Changelog\n\n"
entry = """## 1.17.1 - 2026-08-12

- Routes expensive candidate-swap frontiers through the shipped decision-weighted Semantic Evidence screen; legacy semantic labels remain provenance only and missing/weak semantics are not a negative card score.
- Defers profile-required, decision-material semantic-unknown and conservative static-deprioritization rows before paired simulation while preserving their discoverability and provenance.
- Makes the public paired decision path safe-by-default at one worker after the measured workers=2 regression, while retaining requested/effective worker provenance.
- Adds a bounded per-run execution-time envelope for `deck_decision_run`; execution limits are excluded from semantic run/cache identity and do not become deck-quality evidence.
- Keeps RogShai, inventory, physical allocations, opponent observations and structural engine semantics unchanged.

"""
if "## 1.17.1 - 2026-08-12" not in text:
    if not text.startswith(marker):
        raise SystemExit("CHANGELOG marker not found")
    changelog.write_text(marker + entry + text[len(marker) :], encoding="utf-8")

replace_once(
    "src/commander_lab/models/tooling.py",
    '''class DeckDecisionRunInput(FrozenModel):
    deck_id: str = "rogshai/current"
    remove: str
    add_candidate_id: str
    iterations: int = Field(default=64, ge=1, le=10_000)
    seed: int = Field(default=2026082103, ge=0)
    max_turns: int = Field(default=35, ge=1, le=500)
    workers: int = Field(default=2, ge=1, le=64)
''',
    '''class DeckDecisionRunInput(FrozenModel):
    deck_id: str = "rogshai/current"
    remove: str
    add_candidate_id: str
    iterations: int = Field(default=64, ge=1, le=10_000)
    seed: int = Field(default=2026082103, ge=0)
    max_turns: int = Field(default=35, ge=1, le=500)
    workers: int = Field(default=1, ge=1, le=64)
    max_simulation_seconds: float | None = Field(default=None, gt=0.0, le=600.0)
''',
)

replace_once(
    "src/commander_lab/tools/service.py",
    '''                    inference_penalty = 2.5 if candidate_id.startswith("inventory/") else 0.0
                    delta = raw_delta + compatibility_adjustment - inference_penalty
''',
    '''                    legacy_inference_penalty = (
                        2.5 if candidate_id.startswith("inventory/") else 0.0
                    )
                    # Semantic uncertainty is routed through the decision-weighted Semantic
                    # Evidence gate. A candidate ID/profiling source is provenance, not negative
                    # card evidence and therefore cannot lower the deterministic screen score.
                    inference_penalty = 0.0
                    delta = raw_delta + compatibility_adjustment
''',
)
replace_once(
    "src/commander_lab/tools/service.py",
    '''                            "screening_uncertainty_penalty": inference_penalty,
                            "semantic_quality": (
''',
    '''                            "screening_uncertainty_penalty": inference_penalty,
                            "legacy_screening_uncertainty_penalty": legacy_inference_penalty,
                            "semantic_quality": (
''',
)

old_frontier = '''            rows = []
            for row in screened.result.get("recommendations", []):
                rows.append(
                    {
                        **row,
                        "recommendation_status": "candidate_swap",
                        "validation_level": "structural_only",
                        "candidate_source": "verified local candidate registry",
                        "automatic_application": False,
                    }
                )
            return {
                "deck_id": request.deck_id,
                "deck_hash": self._deck(request.deck_id).deck_hash,
                "method": "whole_deck_role_package_and_profile_screening",
                "candidates": rows,
                "count": len(rows),
                "automatic_application": False,
            }
'''
new_frontier = '''            from commander_lab.candidate_screening import RogShaiCandidateScreener

            semantic_screen = RogShaiCandidateScreener(
                self.root, service=self
            ).screen_pool(request.deck_id)
            screen_rows = semantic_screen.get("rows", [])
            by_id = {
                str(item["candidate_id"]): item
                for item in screen_rows
                if isinstance(item, dict) and item.get("candidate_id")
            }
            by_name = {
                str(item["oracle_name"]): item
                for item in screen_rows
                if isinstance(item, dict) and item.get("oracle_name")
            }
            rows: list[dict[str, Any]] = []
            ready_rows: list[dict[str, Any]] = []
            semantic_deferred: list[dict[str, Any]] = []
            static_deferred: list[dict[str, Any]] = []
            for legacy_row in screened.result.get("recommendations", []):
                row = dict(legacy_row)
                screen_row = by_id.get(str(row.get("candidate_id"))) or by_name.get(
                    str(row.get("add"))
                )
                evidence = (
                    dict(screen_row.get("semantic_evidence", {}))
                    if isinstance(screen_row, dict)
                    and isinstance(screen_row.get("semantic_evidence"), dict)
                    else {}
                )
                bucket = str(screen_row.get("bucket")) if isinstance(screen_row, dict) else "missing"
                model_ready = bool(
                    isinstance(screen_row, dict)
                    and screen_row.get("model_dependent_recommendation_ready") is True
                )
                needs_adjudication = bool(
                    evidence.get("needs_targeted_adjudication") is True or not model_ready
                )
                legacy_quality = str(row.get("semantic_quality", "unknown"))
                evidence_type = str(evidence.get("evidence_type", "UNKNOWN"))
                provenance_disagreement = (
                    legacy_quality == "keyword_inferred_structural_only"
                    and evidence_type not in {"PROJECT_HEURISTIC", "UNKNOWN"}
                )
                if screen_row is None:
                    frontier_status = "deferred_missing_current_semantic_screen"
                    needs_adjudication = True
                elif not model_ready:
                    frontier_status = "deferred_requires_profile"
                elif evidence.get("needs_targeted_adjudication") is True:
                    frontier_status = "deferred_requires_semantic_adjudication"
                elif bucket in {"defer_clear_static_dominance", "defer_low_confidence_default"}:
                    frontier_status = "deferred_static"
                else:
                    frontier_status = "simulation_ready"
                enriched = {
                    **row,
                    "legacy_semantic_quality": legacy_quality,
                    "semantic_authority": "semantic_evidence_summary",
                    "semantic_evidence": evidence,
                    "semantic_screen_bucket": bucket,
                    "semantic_provenance_disagreement": provenance_disagreement,
                    "material_semantic_conflict": bool(
                        evidence.get("needs_targeted_adjudication") is True
                    ),
                    "requires_semantic_adjudication": needs_adjudication,
                    "frontier_status": frontier_status,
                    "recommendation_status": "candidate_swap",
                    "validation_level": "structural_only",
                    "candidate_source": "verified local candidate registry",
                    "automatic_application": False,
                }
                rows.append(enriched)
                if frontier_status == "simulation_ready":
                    ready_rows.append(enriched)
                elif needs_adjudication:
                    semantic_deferred.append(enriched)
                else:
                    static_deferred.append(enriched)
            return {
                "deck_id": request.deck_id,
                "deck_hash": self._deck(request.deck_id).deck_hash,
                "method": "whole_deck_role_package_profile_and_semantic_evidence_screening",
                "candidates": ready_rows,
                "count": len(ready_rows),
                "all_screened_candidates": rows,
                "screened_count": len(rows),
                "deferred_semantic_candidates": semantic_deferred,
                "semantic_deferred_count": len(semantic_deferred),
                "static_deprioritized_candidates": static_deferred,
                "static_deprioritized_count": len(static_deferred),
                "candidate_recall": semantic_screen.get("candidate_recall"),
                "semantic_frontier_gate": {
                    "authority": "semantic_evidence_summary",
                    "legacy_semantic_quality_is_authoritative": False,
                    "unmodeled_is_negative_evidence": False,
                    "noisy_early_simulation_elimination": False,
                },
                "automatic_application": False,
            }
'''
replace_once("src/commander_lab/tools/service.py", old_frontier, new_frontier)

replace_once(
    "src/commander_lab/tools/service.py",
    '''        started = time.monotonic()
        invocation_id = f"{tool_name}-{uuid.uuid4().hex[:12]}"
        scenario = request.model_dump(mode="json") if hasattr(request, "model_dump") else request
        identity_before = self._run_identity(
''',
    '''        started = time.monotonic()
        invocation_id = f"{tool_name}-{uuid.uuid4().hex[:12]}"
        execution_limit = float(self.limits.max_simulation_seconds)
        requested_execution_limit = getattr(request, "max_simulation_seconds", None)
        if tool_name == "deck_decision_run" and requested_execution_limit is not None:
            execution_limit = float(requested_execution_limit)
        scenario = request.model_dump(mode="json") if hasattr(request, "model_dump") else request
        if tool_name == "deck_decision_run" and isinstance(scenario, dict):
            scenario = dict(scenario)
            scenario.pop("max_simulation_seconds", None)
            scenario["workers"] = 1
        identity_before = self._run_identity(
''',
)
replace_once(
    "src/commander_lab/tools/service.py",
    '''            if elapsed > self.limits.max_simulation_seconds:
                raise ToolExecutionError(
                    "tool exceeded simulation budget: "
                    f"{elapsed:.3f}s > {self.limits.max_simulation_seconds:.3f}s"
                )
''',
    '''            if elapsed > execution_limit:
                raise ToolExecutionError(
                    "tool exceeded simulation budget: "
                    f"{elapsed:.3f}s > {execution_limit:.3f}s"
                )
''',
)

replace_once(
    "src/commander_lab/priority_workflows.py",
    '''        if workers < 1:
            raise ValueError("workers must be positive")
        baseline = self._deck(deck_id)
''',
    '''        if workers < 1:
            raise ValueError("workers must be positive")
        requested_workers = workers
        effective_workers = 1
        baseline = self._deck(deck_id)
''',
)
priority = Path("src/commander_lab/priority_workflows.py")
text = priority.read_text(encoding="utf-8")
needle = '                "workers": workers,\n'
if text.count(needle) != 1:
    raise SystemExit(f"priority cache worker occurrence mismatch: {text.count(needle)}")
text = text.replace(needle, '                "workers": effective_workers,\n')
needle2 = "                workers=workers,\n"
if text.count(needle2) < 1:
    raise SystemExit("priority run worker occurrence missing")
text = text.replace(needle2, "                workers=effective_workers,\n", 1)
return_marker = '            "truth_boundary": "model-internal paired structural comparison, not empirical gameplay",\n'
if return_marker not in text:
    raise SystemExit("priority return marker missing")
text = text.replace(
    return_marker,
    '''            "execution_workers": {
                "requested": requested_workers,
                "effective": effective_workers,
                "fallback_applied": requested_workers != effective_workers,
                "policy": "validated_single_worker_until_issue_55_resolution",
                "deck_quality_evidence": False,
            },
'''
    + return_marker,
    1,
)
priority.write_text(text, encoding="utf-8")

replace_once(
    "src/commander_lab/tools/service.py",
    '''            result["workflow_session"] = session.identity()
            return result

        return self._invoke(
            "deck_decision_run",
''',
    '''            result["workflow_session"] = session.identity()
            result["execution_envelope"] = {
                "requested_workers": request.workers,
                "effective_workers": 1,
                "worker_fallback_applied": request.workers != 1,
                "default_max_simulation_seconds": float(self.limits.max_simulation_seconds),
                "requested_max_simulation_seconds": request.max_simulation_seconds,
                "effective_max_simulation_seconds": (
                    float(request.max_simulation_seconds)
                    if request.max_simulation_seconds is not None
                    else float(self.limits.max_simulation_seconds)
                ),
                "classification": "execution_envelope_only_not_deck_quality_evidence",
            }
            return result

        return self._invoke(
            "deck_decision_run",
''',
)

Path("tests/unit/test_post117_semantic_execution_fixes.py").write_text(
    r'''from pathlib import Path

from commander_lab.models.tooling import DeckDecisionRunInput, GenerateCandidateSwapsInput
from commander_lab.tools import CommanderToolService, ToolRegistry


ROOT = Path(__file__).resolve().parents[2]


def _candidate_id(service: CommanderToolService, name: str) -> str:
    return next(
        candidate_id
        for candidate_id, candidate in service.candidates.items()
        if candidate.card.oracle_name == name
    )


def test_semantic_frontier_uses_decision_weighted_evidence_without_inventory_penalty() -> None:
    service = CommanderToolService(ROOT)
    evendo_id = _candidate_id(service, "Evendo Brushrazer")
    opt_id = _candidate_id(service, "Opt")
    response = service.generate_candidate_swaps(
        GenerateCandidateSwapsInput(
            deck_id="rogshai/current",
            candidate_ids=(evendo_id, opt_id),
            max_candidates=50,
        )
    )
    assert response.status.value == "completed"
    result = response.result
    assert result["semantic_frontier_gate"]["authority"] == "semantic_evidence_summary"
    assert result["semantic_frontier_gate"]["legacy_semantic_quality_is_authoritative"] is False
    assert result["semantic_frontier_gate"]["unmodeled_is_negative_evidence"] is False
    rows = result["all_screened_candidates"]
    assert rows
    assert all(row["screening_uncertainty_penalty"] == 0.0 for row in rows)
    evendo_rows = [row for row in rows if row["candidate_id"] == evendo_id]
    assert evendo_rows
    assert any(row["legacy_semantic_quality"] == "keyword_inferred_structural_only" for row in evendo_rows)
    assert any(row["semantic_evidence"].get("evidence_type") != "UNKNOWN" for row in evendo_rows)
    assert any(row["semantic_provenance_disagreement"] for row in evendo_rows)
    assert all(row["semantic_authority"] == "semantic_evidence_summary" for row in rows)
    assert all(not row["requires_semantic_adjudication"] for row in result["candidates"])


def test_public_paired_execution_falls_back_to_one_worker_and_limit_is_identity_neutral() -> None:
    service = CommanderToolService(ROOT)
    registry = ToolRegistry(service, surface="public")
    assert DeckDecisionRunInput(remove="Preordain", add_candidate_id="rogshai/opt-smoke").workers == 1
    common = {
        "deck_id": "rogshai/current",
        "remove": "Preordain",
        "add_candidate_id": "rogshai/opt-smoke",
        "iterations": 2,
        "seed": 2026081203,
        "max_turns": 10,
    }
    one = registry.invoke("deck_decision_run", common | {"workers": 1})
    two = registry.invoke(
        "deck_decision_run",
        common | {"workers": 2, "max_simulation_seconds": 300.0},
    )
    assert one.status.value == "completed"
    assert two.status.value == "completed"
    assert one.result["paired"] == two.result["paired"]
    assert one.metadata.run_identity_hash == two.metadata.run_identity_hash
    assert two.result["execution_workers"] == {
        "requested": 2,
        "effective": 1,
        "fallback_applied": True,
        "policy": "validated_single_worker_until_issue_55_resolution",
        "deck_quality_evidence": False,
    }
    envelope = two.result["execution_envelope"]
    assert envelope["effective_workers"] == 1
    assert envelope["effective_max_simulation_seconds"] == 300.0
    assert envelope["classification"] == "execution_envelope_only_not_deck_quality_evidence"
''',
    encoding="utf-8",
)
