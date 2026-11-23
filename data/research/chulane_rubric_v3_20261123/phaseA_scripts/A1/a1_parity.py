"""Frage 1: Eingabe-Parität F1 gegen R2.

  PYTHONPATH=<Klon>/src python3 a1_parity.py [--f1-batches <Ordner mit F1_b*.md>]

Rekonstruiert die F1-Chargenprompts mit dem Repo-Generator (make_batches.py --run full) in einen
Arbeitsordner und vergleicht (a) Kartenblöcke byte-genau mit rr_input/rr2_input, (b) den Systemteil
(Guide + Anker) je F1-Charge und je R2-Charge, (c) Rahmen/Anweisung, (d) Ausgabeschema.
Optional: --f1-batches vergleicht die rekonstruierten Prompts mit den Original-Laufdateien.
Schreibt $A1_OUT/parity.json.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a1_common as C

WORK = C.WORK


def sha(s: str | bytes) -> str:
    if isinstance(s, str):
        s = s.encode("utf-8")
    return hashlib.sha256(s).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--f1-batches")
    a = ap.parse_args()
    res: dict = {}
    scripts = C.RUB / "scripts"
    regen = WORK / "f1regen"
    subprocess.run(
        [sys.executable, str(scripts / "make_batches.py"), "--out", str(regen), "--run", "full"],
        check=True,
        capture_output=True,
    )
    sys.path.insert(0, str(scripts))
    import render_prompt as rp

    man = json.loads((regen / "full_manifest.json").read_text())
    f1 = C.load_f1()  # noqa: F841
    # F1-Chargenzuordnung aus den Bewertungen gegen das rekonstruierte Manifest
    by_batch: dict[str, list[str]] = {}
    for r in C.jl(C.RUB / "fullrun_ratings.jsonl"):
        by_batch.setdefault(r["batch"], []).append(r["card"])
    res["f1_batch_order_matches_regen"] = (
        sum(1 for m in man if by_batch.get(m["batch"]) == m["cards"]),
        len(man),
    )
    if a.f1_batches:
        same = sum(
            1
            for m in man
            if (Path(a.f1_batches) / f"{m['batch']}.md").read_bytes()
            == (regen / "full" / f"{m['batch']}.md").read_bytes()
        )
        res["f1_regen_vs_original_files_byte_equal"] = (same, len(man))

    # (a) Kartenblöcke
    facts = {r["name"]: r for r in rp.load_jsonl(C.RUB / "data/facts.jsonl")}
    pats = {r["name"]: r for r in rp.load_jsonl(C.RUB / "data/patterns.jsonl")}
    r2 = C.load_r2()
    retest = C.jl(C.W2 / "rater/rr2_input_8.jsonl")
    eq = 0
    diffs = []
    for oid, r in r2.items():  # noqa: B007
        name = r["card"]
        f1_block = rp.card_block(facts[name], pats.get(name))
        if f1_block == r["card_block"]:
            eq += 1
        else:
            diffs.append(name)
    res["card_block_equal_r2_vs_f1_generator"] = (eq, len(r2), diffs[:10])
    eq8 = sum(
        1 for i in retest if rp.card_block(facts[i["card"]], pats.get(i["card"])) == i["card_block"]
    )
    res["card_block_equal_retest8"] = (eq8, len(retest))
    # Ist der F1-Kartenblock im F1-Prompt genau user_prompt().strip()? (Zeile "Rate this card" davor)
    sample = (regen / "full" / "F1_b000.md").read_text()
    res["f1_prompt_has_rate_this_card_line_per_card"] = sample.count(rp.USER_FIRST_LINE)
    res["r2_input_has_rate_this_card_line"] = sum(
        rp.USER_FIRST_LINE in r["card_block"] for r in r2.values()
    )
    # Kommandantentext im Kartenblock?
    res["chulane_text_in_card_blocks_r2"] = sum(
        "Whenever you cast a creature spell" in r["card_block"] and "Chulane" in r["card"]
        for r in r2.values()
    )

    # (b) Systemteil
    guide = (C.RUB / "GUIDE_v2.md").read_text()
    anch = C.anchors()
    full_sys = rp.system_prompt(guide, anch, None)
    w1_guide = (C.W1 / "rr_guide_v2_1_rendered.md").read_text()

    class LeaveOut:
        def __init__(self, names):
            self.names = set(names)

        def __bool__(self):
            return bool(self.names)

        def __eq__(self, o):
            return o in self.names

    m2 = C.manifest_w2()
    w2 = {}
    for k, pc in m2["meta"]["per_chunk"].items():
        g = (C.W2 / "rater" / f"rr2_guide_{k}.md").read_text()
        rebuilt = rp.system_prompt(
            guide, anch, LeaveOut(pc["anchors_left_out"]) if pc["anchors_left_out"] else None
        )
        d = [
            ln
            for ln in difflib.unified_diff(rebuilt.splitlines(), g.splitlines(), lineterm="", n=0)
            if ln[:1] in "+-" and not ln.startswith(("+++", "---"))
        ]
        w2[k] = {
            "sha256": sha(g),
            "manifest_sha_ok": sha(g) == pc["guide_sha256"],
            "equal_to_repo_generator_with_same_leaveout": g == rebuilt,
            "n_diff_lines_vs_generator": len(d),
            "diff_sample": d[:6],
            "n_diff_lines_vs_full_guide": sum(
                1
                for ln in difflib.unified_diff(
                    full_sys.splitlines(), g.splitlines(), lineterm="", n=0
                )
                if ln[:1] in "+-" and not ln.startswith(("+++", "---"))
            ),
            "left_out": pc["anchors_left_out"],
        }
    res["w2_guides"] = w2
    lo1 = C.manifest_w1()["meta"]["pool"]["anchors_left_out_of_guide_tables"]
    rb1 = rp.system_prompt(guide, anch, LeaveOut(lo1))
    res["w1_guide_equal_to_generator_with_leaveout"] = (w1_guide == rb1, lo1)
    res["w1_guide_diff_vs_generator"] = [
        ln
        for ln in difflib.unified_diff(rb1.splitlines(), w1_guide.splitlines(), lineterm="", n=0)
        if ln[:1] in "+-" and not ln.startswith(("+++", "---"))
    ][:10]

    # F1: welche Karten bewertete F1 mit ihren eigenen Ankerzeilen sichtbar?
    v1_fixed = {
        r["card"]
        for t in (anch["spell"], anch["land"])
        for rows in t.values()
        for r in rows
        if r["kind"] == "v1_fixed"
    }
    all_anchor = {
        r["card"] for t in (anch["spell"], anch["land"]) for rows in t.values() for r in rows
    }
    res["anchor_names_total"] = len(all_anchor)
    res["f1_leaveout_only_v1_fixed"] = sorted(v1_fixed)
    seen_own = []
    for m in man:
        body = (regen / "full" / f"{m['batch']}.md").read_text()
        sysp = body.split("# CARDS TO RATE (BATCH)")[0]
        anc_part = sysp.split("<!-- anchors -->")[1]
        for n in m["cards"]:
            if n in all_anchor and re.search(rf"\b{re.escape(n)} \(", anc_part):
                seen_own.append(n)
    res["f1_rated_with_own_anchor_rows_visible"] = (len(seen_own), sorted(seen_own))
    # R2: in welcher Charge/Welle stand eine Ankerkarte in ihrer eigenen Tabelle?
    r2_seen = []
    for oid, r in r2.items():  # noqa: B007
        if r["card"] not in all_anchor:
            continue
        if r["wave"] == 1:
            g = w1_guide
        else:
            g = (C.W2 / "rater" / f"rr2_guide_{r['chunk'].split(':')[1]}.md").read_text()
        if re.search(rf"\b{re.escape(r['card'])} \(", g.split("<!-- anchors -->")[1]):
            r2_seen.append(r["card"])
    res["r2_rated_with_own_anchor_rows_visible"] = (len(r2_seen), sorted(r2_seen))
    # F1-Systemteil ohne Leave-out gegen Repo-Guide-Render
    nl = [m for m in man if not any(n in v1_fixed for n in m["cards"])][0]  # noqa: RUF015
    body = (regen / "full" / f"{nl['batch']}.md").read_text()
    res["f1_system_part_equals_full_render_for_batch_without_v1_fixed"] = (
        body.split("\n\n# CARDS TO RATE (BATCH)")[0] == full_sys.rstrip("\n")
        or body.startswith(full_sys),
        nl["batch"],
    )

    # (c) Rahmen
    res["f1_frame"] = {
        "cards_per_call": sorted({len(m["cards"]) for m in man}),
        "batch_head_sha": sha(sample.split("# CARDS TO RATE (BATCH)")[1].split("## Card 1")[0]),
        "output": "ONE JSON array per batch file",
    }
    res["r2_frame"] = {
        "cards_per_instance": {k: v["n"] for k, v in m2["meta"]["per_chunk"].items()},
        "w1_cards_per_instance": 100,
        "instructions_sha": sha((C.W2 / "rater/rr2_rater_instructions.md").read_text()),
        "output": "JSONL, append every 10 cards",
    }
    # (d) Schema
    s1 = json.loads((C.RUB / "output_schema.json").read_text())
    s2 = json.loads((C.W2 / "rater/rr2_output_schema.json").read_text())
    res["schema_equal"] = s1 == s2
    res["schema_diff"] = [
        ln
        for ln in difflib.unified_diff(
            json.dumps(s1, indent=1, sort_keys=True).splitlines(),
            json.dumps(s2, indent=1, sort_keys=True).splitlines(),
            lineterm="",
            n=0,
        )
        if ln[:1] in "+-" and not ln.startswith(("+++", "---"))
    ][:30]
    WORK.mkdir(exist_ok=True)
    (WORK / "parity.json").write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(res, indent=1, ensure_ascii=False)[:9000])


if __name__ == "__main__":
    main()
