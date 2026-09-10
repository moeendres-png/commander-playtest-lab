#!/usr/bin/env python3
"""D1 General-N Forge Commander discriminator driver (research-only, no credit).

For each N in 2..6, builds the hand-built native Commander game probe from
general_n_discriminator_template.java (stub controller methods generated
mechanically from the pinned PlayerController.java abstract surface),
compiles against pinned Forge 66caae16 classes into scratch space (never
into any provider artifact), runs the scenario battery, and adjudicates
per-N gate rows.

Usage:
  run_general_n_discriminator.py --forge /tmp/ws48/forge-build \
      --classpath-file /tmp/ws48/r1d-full-cp.txt --out <result.json> \
      [--workdir <dir>] [--seed <int>]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

FORGE_COMMIT = "66caae16015bd403bc0a52fa6689afb5508f74d0"
FORGE_TREE = "40fc8f29ce4de31a964972461db2b48b4221e07f"
HERE = Path(__file__).resolve().parent
NS = (2, 3, 4, 5, 6)

# check -> gate mapping for the deliverable classification
CHECK_TO_GATE = {
    "CONSTRUCTS": "CONSTRUCTS",
    "TURN_RING": "TURN_RING",
    "PRIORITY_RING": "PRIORITY_RING",
    "PRIORITY_AFTER_ELIMINATION": "PRIORITY_RING",
    "OPPONENTS": "PRIORITY_RING",  # opponents feed priority/turn scoping; reported under ring
    "COMMANDER_INIT": "COMMANDER_INIT",
    "COMBAT_MULTI_DEFENDER": "COMBAT_MULTI_DEFENDER",
    "ELIMINATION": "ELIMINATION",
    "EXTRA_TURN": "TURN_RING",
    "HIDDEN_INFO": "HIDDEN_INFO",
    "DETERMINISM": "DETERMINISM",
}


def abstract_methods(source: str) -> list[tuple[str, str, str, str]]:
    no_strings = re.sub(r'"(?:\\.|[^"\\])*"', '""', source)
    no_comments = re.sub(r"/\*.*?\*/", " ", no_strings, flags=re.DOTALL)
    no_comments = re.sub(r"//[^\n]*", " ", no_comments)
    out = []
    for m in re.finditer(r"public\s+abstract\s+(.*?);", no_comments, re.DOTALL):
        decl = re.sub(r"\s+", " ", m.group(1)).strip()
        if decl.startswith(("class ", "interface ", "@interface ", "enum ")):
            continue
        if "=" in decl or "(" not in decl:
            raise SystemExit(f"GNN_ABSTRACT_PARSE_SUSPECT:{decl[:120]}")
        paren = decl.index("(")
        head, rest = decl[:paren], decl[paren + 1:]
        if not rest.endswith(")"):
            depth = 0
            idx = None
            for i, ch in enumerate(rest):
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    if depth == 0:
                        idx = i
                        break
                    depth -= 1
            params, throws = rest[:idx], rest[idx + 1:].strip()
        else:
            params, throws = rest[:-1], ""
        name = head.rsplit(None, 1)[-1]
        prefix = head[: -len(name)].strip()
        out.append((prefix, name, params.strip(), throws))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--forge", type=Path, required=True)
    ap.add_argument("--classpath-file", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workdir", type=Path, default=Path("/tmp/ws48/general-n"))
    ap.add_argument("--seed", type=int, default=424242)
    a = ap.parse_args()

    head = subprocess.check_output(
        ["git", "-C", str(a.forge), "rev-parse", "HEAD"], text=True).strip()
    tree = subprocess.check_output(
        ["git", "-C", str(a.forge), "rev-parse", "HEAD^{tree}"], text=True).strip()
    if head != FORGE_COMMIT or tree != FORGE_TREE:
        raise SystemExit(f"GNN_FORGE_LOCK_MISMATCH head={head} tree={tree}")

    pc = (a.forge / "forge-game/src/main/java/forge/game/player/PlayerController.java"
          ).read_text(encoding="utf-8")
    methods = abstract_methods(pc)
    if not methods:
        raise SystemExit("GNN_NO_ABSTRACT_METHODS")
    stubs = []
    for prefix, name, params, throws in methods:
        clause = f" {throws}" if throws else ""
        stubs.append(
            f"        @Override\n        public {prefix} {name}({params}){clause} {{\n"
            f'            throw new StubReached("{name}");\n        }}')
    stub_block = "\n\n".join(stubs)

    pc_imports = sorted(set(
        line.strip() for line in pc.splitlines()
        if line.startswith("import ")))
    tpl = (HERE / "general_n_discriminator_template.java").read_text(encoding="utf-8")
    if "__STUB_METHODS__" not in tpl:
        raise SystemExit("GNN_TEMPLATE_PLACEHOLDER_MISSING")

    work = a.workdir
    srcdir = work / "src/forge/game/player"
    clsdir = work / "classes"
    srcdir.mkdir(parents=True, exist_ok=True)
    clsdir.mkdir(parents=True, exist_ok=True)
    gen = tpl.replace("__STUB_METHODS__", stub_block)
    have = set(l.strip() for l in gen.splitlines() if l.startswith("import "))
    extra = [l for l in pc_imports if l not in have]
    gen = gen.replace("import forge.CardStorageReader;",
                      "\n".join(extra + ["import forge.CardStorageReader;"]), 1)
    (srcdir / "GeneralNForgeDiscriminator.java").write_text(gen, encoding="utf-8")

    cp = a.classpath_file.read_text(encoding="utf-8").strip()
    javac = subprocess.run(
        ["javac", "-cp", cp, "-d", str(clsdir),
         str(srcdir / "GeneralNForgeDiscriminator.java")],
        capture_output=True, text=True)
    if javac.returncode != 0:
        raise SystemExit(f"GNN_JAVAC_FAIL:\n{javac.stderr[-3000:]}")
    code_lines = [l for l in gen.splitlines()
                  if not l.strip().startswith(("//", "*", "/*"))]
    code_only = "\n".join(code_lines)
    if re.search(r"\bWs40SuccessorState\b|\bapplyNativeState\b|\bGameState\b"
                 r"|RESTORE_SNAPSHOT", code_only):
        raise SystemExit("GNN_REPRO_CONTAMINATED_BY_RESTORE")

    lang_dir = a.forge / "forge-gui/res/languages"
    rows: list[dict] = []
    for n in NS:
        r = subprocess.run(
            ["java", "-cp", f"{clsdir}:{cp}",
             "forge.game.player.GeneralNForgeDiscriminator",
             str(n), str(lang_dir), str(a.seed + n)],
            capture_output=True, text=True, timeout=300)
        lines = [l for l in r.stdout.strip().splitlines() if l.strip().startswith("{")]
        if r.returncode != 0 and not lines:
            rows.append({"n": n, "check": "HARNESS",
                         "outcome": "ERROR",
                         "detail": f"rc={r.returncode} stderr={r.stderr[-1500:]}"})
            print(f"N={n} -> HARNESS ERROR rc={r.returncode}", flush=True)
            continue
        for line in lines:
            try:
                row = json.loads(line)
            except Exception:
                row = {"n": n, "check": "PARSE", "outcome": "ERROR",
                       "detail": line[:500]}
            row["rc"] = r.returncode
            rows.append(row)
        ok = sum(1 for row in rows if row.get("n") == n and row.get("outcome") == "PASS")
        tot = sum(1 for row in rows if row.get("n") == n)
        print(f"N={n} -> {ok}/{tot} PASS", flush=True)

    # adjudicate per-N gates
    gates = ["CONSTRUCTS", "TURN_RING", "PRIORITY_RING", "COMMANDER_INIT",
             "COMBAT_MULTI_DEFENDER", "ELIMINATION", "HIDDEN_INFO", "DETERMINISM"]
    per_n: dict[str, dict[str, str]] = {}
    for n in NS:
        nrows = [r for r in rows if r.get("n") == n]
        by_check: dict[str, list[dict]] = {}
        for r in nrows:
            by_check.setdefault(r.get("check", "?"), []).append(r)
        g: dict[str, str] = {}
        g["CONSTRUCTS"] = _gate(by_check.get("CONSTRUCTS", []))
        g["TURN_RING"] = _gate(by_check.get("TURN_RING", []) + by_check.get("EXTRA_TURN", []))
        g["PRIORITY_RING"] = _gate(by_check.get("PRIORITY_RING", [])
                                   + by_check.get("PRIORITY_AFTER_ELIMINATION", [])
                                   + by_check.get("OPPONENTS", []))
        g["COMMANDER_INIT"] = _gate(by_check.get("COMMANDER_INIT", []))
        g["COMBAT_MULTI_DEFENDER"] = _gate(by_check.get("COMBAT_MULTI_DEFENDER", []))
        g["ELIMINATION"] = _gate(by_check.get("ELIMINATION", []))
        g["HIDDEN_INFO"] = _gate(by_check.get("HIDDEN_INFO", []))
        g["DETERMINISM"] = _gate(by_check.get("DETERMINISM", []))
        per_n[str(n)] = g

    result = {
        "schema_version": "commander-lab.general-n-forge-discriminator/1.0.0",
        "evidence_class": "HAND_BUILT_NATIVE_REPRO",
        "grants_behavior_credit": False,
        "grants_qualification_credit": False,
        "forge": {"commit": head, "tree": tree, "version": "2.0.15-SNAPSHOT"},
        "seed_base": a.seed,
        "abstract_stub_count": len(methods),
        "rows": rows,
        "per_n_gates": per_n,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("GATES=" + json.dumps(per_n, sort_keys=True))
    fails = sum(1 for g in per_n.values() for v in g.values() if v == "FAIL")
    unks = sum(1 for g in per_n.values() for v in g.values() if v == "UNKNOWN")
    return 0 if (fails == 0 and unks == 0) else 2


def _gate(rows: list[dict]) -> str:
    if not rows:
        return "UNKNOWN"
    if any(r.get("outcome") == "FAIL" for r in rows):
        return "FAIL"
    if any(r.get("outcome") == "ERROR" for r in rows):
        return "UNKNOWN"
    if all(r.get("outcome") == "PASS" for r in rows):
        return "PASS"
    return "UNKNOWN"


if __name__ == "__main__":
    raise SystemExit(main())
