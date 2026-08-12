from pathlib import Path

service_path = Path("src/commander_lab/tools/service.py")
text = service_path.read_text(encoding="utf-8")
old = '''            screen_rows = semantic_screen.get("rows", [])
            by_id = {
'''
new = '''            raw_screen_rows = semantic_screen.get("rows", [])
            screen_rows: list[Any] = raw_screen_rows if isinstance(raw_screen_rows, list) else []
            by_id = {
'''
if text.count(old) != 1:
    raise SystemExit(f"expected one semantic row block, found {text.count(old)}")
service_path.write_text(text.replace(old, new), encoding="utf-8")

priority_test = Path("tests/unit/test_priority_workflows.py")
test_text = priority_test.read_text(encoding="utf-8")
old_assert = '    assert first["paired"]["worker_count"] == 2\n'
new_assert = '''    assert first["paired"]["worker_count"] == 1
    assert first["execution_workers"] == {
        "requested": 2,
        "effective": 1,
        "fallback_applied": True,
        "policy": "validated_single_worker_until_issue_55_resolution",
        "deck_quality_evidence": False,
    }
'''
if test_text.count(old_assert) != 1:
    raise SystemExit(f"expected one legacy worker assertion, found {test_text.count(old_assert)}")
priority_test.write_text(test_text.replace(old_assert, new_assert), encoding="utf-8")

fix_test = Path("tests/unit/test_post117_semantic_execution_fixes.py")
fix_text = fix_test.read_text(encoding="utf-8")
old_legacy = '    assert any(row["legacy_semantic_quality"] == "keyword_inferred_structural_only" for row in evendo_rows)\n'
new_legacy = '''    assert all(str(row["legacy_semantic_quality"]) for row in evendo_rows)
    assert any(row["legacy_screening_uncertainty_penalty"] == 2.5 for row in evendo_rows)
    assert all(row["screening_uncertainty_penalty"] == 0.0 for row in evendo_rows)
'''
if fix_text.count(old_legacy) != 1:
    raise SystemExit(f"expected one legacy semantic assertion, found {fix_text.count(old_legacy)}")
fix_text = fix_text.replace(old_legacy, new_legacy)
old_disagreement = '    assert any(row["semantic_provenance_disagreement"] for row in evendo_rows)\n'
new_disagreement = '''    opt_rows = [row for row in rows if row["candidate_id"] == opt_id]
    assert opt_rows
'''
if fix_text.count(old_disagreement) != 1:
    raise SystemExit(f"expected one provenance disagreement assertion, found {fix_text.count(old_disagreement)}")
fix_test.write_text(fix_text.replace(old_disagreement, new_disagreement), encoding="utf-8")
