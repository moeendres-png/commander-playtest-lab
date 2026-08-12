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
