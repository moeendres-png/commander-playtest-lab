from __future__ import annotations

from pathlib import Path

path = Path(__file__).resolve().parents[1] / "src/commander_lab/models/tooling.py"
text = path.read_text(encoding="utf-8")
old = '    deck_ids: tuple[str, ...] = ("korvold/current", "rogshai/current")\n'
new = '    deck_ids: tuple[str, ...] = ("rogshai/current",)\n'
if text.count(new) == 2:
    print("J-FINAL active-scope model defaults already materialized")
elif text.count(old) == 2:
    path.write_text(text.replace(old, new), encoding="utf-8")
    print("J-FINAL active-scope model defaults materialized")
else:
    raise RuntimeError(
        f"expected exactly two active-scope default targets; old={text.count(old)} new={text.count(new)}"
    )
