from pathlib import Path

path = Path("src/commander_lab/tools/service.py")
text = path.read_text(encoding="utf-8")
old = '''            screen_rows = semantic_screen.get("rows", [])
            by_id = {
'''
new = '''            raw_screen_rows = semantic_screen.get("rows", [])
            screen_rows: list[Any] = raw_screen_rows if isinstance(raw_screen_rows, list) else []
            by_id = {
'''
if text.count(old) != 1:
    raise SystemExit(f"expected one semantic row block, found {text.count(old)}")
path.write_text(text.replace(old, new), encoding="utf-8")
