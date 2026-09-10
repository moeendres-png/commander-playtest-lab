#!/usr/bin/env python3
"""WS48 R1d BLOCK-4 discriminator driver (qualification-only, grants no credit).

Builds the hand-built native combat equivalent from
r1d_discriminator_template.java (stub controller methods are generated
mechanically from the pinned PlayerController.java abstract surface),
compiles it against the pinned Forge 66caae16 classes into scratch space
(never into the provider artifact), runs variant A (loader-equivalent: no
declare-blockers finalization) and variant B (native-equivalent: with
Combat.fireTriggersForUnblockedAttackers, the PhaseHandler:746 step every
real game runs), and adjudicates:

  A == NPE "AttackingBand.isBlocked() is null" at Combat:873
  AND B != that NPE  ->  STATE_RESTORE_OR_ADAPTER_DEFECT
  B == same 873-NPE  ->  ENGINE_DEFECT_CONFIRMED_CANDIDATE
  else               ->  UNKNOWN (no claim)

Usage:
  run_r1d_discriminator.py --forge /tmp/ws48/forge-build \
      --classpath-file <file> --out <result.json> [--workdir <dir>]
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


def abstract_methods(source: str) -> list[tuple[str, str, str, str]]:
    # Strip block/line comments and string literals so javadoc mentions of
    # "public abstract" cannot merge into a following field initializer.
    no_strings = re.sub(r'"(?:\\.|[^"\\])*"', '""', source)
    no_comments = re.sub(r"/\*.*?\*/", " ", no_strings, flags=re.DOTALL)
    no_comments = re.sub(r"//[^\n]*", " ", no_comments)
    out = []
    for m in re.finditer(r"public\s+abstract\s+(.*?);", no_comments, re.DOTALL):
        decl = re.sub(r"\s+", " ", m.group(1)).strip()
        if decl.startswith(("class ", "interface ", "@interface ", "enum ")):
            continue  # the class declaration itself, not a method
        if "=" in decl or "(" not in decl:
            raise SystemExit(f"R1D_ABSTRACT_PARSE_SUSPECT:{decl[:120]}")
        paren = decl.index("(")
        head, rest = decl[:paren], decl[paren + 1:]
        if not rest.endswith(")"):
            # throws clause present: split params from throws
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
    ap.add_argument("--forge", type=Path, required=True,
                    help="Forge source checkout at the pinned commit")
    ap.add_argument("--classpath-file", type=Path, required=True,
                    help="file containing the compile/run classpath")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workdir", type=Path, default=Path("/tmp/ws48/r1d"))
    a = ap.parse_args()

    head = subprocess.check_output(
        ["git", "-C", str(a.forge), "rev-parse", "HEAD"], text=True).strip()
    tree = subprocess.check_output(
        ["git", "-C", str(a.forge), "rev-parse", "HEAD^{tree}"], text=True).strip()
    if head != FORGE_COMMIT or tree != FORGE_TREE:
        raise SystemExit(f"R1D_FORGE_LOCK_MISMATCH head={head} tree={tree}")

    pc = (a.forge / "forge-game/src/main/java/forge/game/player/PlayerController.java"
          ).read_text(encoding="utf-8")
    methods = abstract_methods(pc)
    if not methods:
        raise SystemExit("R1D_NO_ABSTRACT_METHODS")
    stubs = []
    for prefix, name, params, throws in methods:
        clause = f" {throws}" if throws else ""
        stubs.append(
            f"        @Override\n        public {prefix} {name}({params}){clause} {{\n"
            f'            throw new R1dStubReached("{name}");\n        }}')
    stub_block = "\n\n".join(stubs)

    pc_imports = sorted(set(
        line.strip() for line in pc.splitlines()
        if line.startswith("import ")))
    tpl = (HERE / "r1d_discriminator_template.java").read_text(encoding="utf-8")
    if "__STUB_METHODS__" not in tpl:
        raise SystemExit("R1D_TEMPLATE_PLACEHOLDER_MISSING")

    work = a.workdir
    srcdir = work / "src/forge/game/player"
    clsdir = work / "classes"
    srcdir.mkdir(parents=True, exist_ok=True)
    clsdir.mkdir(parents=True, exist_ok=True)
    gen = tpl.replace("__STUB_METHODS__", stub_block)
    # Merge PlayerController imports (dedupe identical lines).
    have = set(l.strip() for l in gen.splitlines() if l.startswith("import "))
    extra = [l for l in pc_imports if l not in have]
    gen = gen.replace("import forge.CardStorageReader;",
                      "\n".join(extra + ["import forge.CardStorageReader;"]),
                      1)
    (srcdir / "R1dCombatDiscriminator.java").write_text(gen, encoding="utf-8")

    cp = a.classpath_file.read_text(encoding="utf-8").strip()
    javac = subprocess.run(
        ["javac", "-cp", cp, "-d", str(clsdir),
         str(srcdir / "R1dCombatDiscriminator.java")],
        capture_output=True, text=True)
    if javac.returncode != 0:
        raise SystemExit(f"R1D_JAVAC_FAIL:\n{javac.stderr[-3000:]}")
    # Fail closed on restore-mechanism creep in the repro itself (code only,
    # not header comments documenting the exclusion).
    code_lines = [l for l in gen.splitlines()
                  if not l.strip().startswith(("//", "*", "/*"))]
    code_only = "\n".join(code_lines)
    if re.search(r"\bWs40SuccessorState\b|\bapplyNativeState\b|\bGameState\b"
                 r"|RESTORE_SNAPSHOT", code_only):
        raise SystemExit("R1D_REPRO_CONTAMINATED_BY_RESTORE")

    lang_dir = a.forge / "forge-gui/res/languages"
    rows = []
    for variant in ("A", "B"):
        r = subprocess.run(
            ["java", "-cp", f"{clsdir}:{cp}",
             "forge.game.player.R1dCombatDiscriminator", variant, str(lang_dir)],
            capture_output=True, text=True, timeout=300)
        line = (r.stdout.strip().splitlines() or [""])[-1]
        try:
            row = json.loads(line)
        except Exception:
            row = {"r1d_variant": variant, "outcome": "DRIVER_PARSE_FAIL",
                   "rc": r.returncode, "stdout_tail": r.stdout[-2000:],
                   "stderr_tail": r.stderr[-2000:]}
        row["rc"] = r.returncode
        row["stderr_tail"] = r.stderr[-1500:]
        rows.append(row)
        print(f"R1D variant {variant} -> {row.get('outcome')} "
              f"top={row.get('top_frame')}", flush=True)

    by = {r["r1d_variant"]: r for r in rows}
    npe873 = ("NULL_POINTER" in str(by["A"].get("outcome"))
              and "AttackingBand.isBlocked()" in str(by["A"].get("detail"))
              and "Combat.assignAttackersDamage(Combat.java:873)"
              in str(by["A"].get("top_frame", "")))
    b_same = ("NULL_POINTER" in str(by["B"].get("outcome"))
              and "Combat.assignAttackersDamage(Combat.java:873)"
              in str(by["B"].get("top_frame", "")))
    if npe873 and not b_same:
        discriminator = "STATE_RESTORE_OR_ADAPTER_DEFECT"
    elif npe873 and b_same:
        discriminator = "ENGINE_DEFECT_CONFIRMED_CANDIDATE"
    else:
        discriminator = "UNKNOWN"
    result = {
        "schema_version": "commander-lab.ws48-r1d-discriminator/1.0.0",
        "evidence_class": "HAND_BUILT_NATIVE_REPRO",
        "grants_behavior_credit": False,
        "forge": {"commit": head, "tree": tree, "version": "2.0.15-SNAPSHOT"},
        "abstract_stub_count": len(methods),
        "rows": rows,
        "variant_a_reproduces_production_873_npe": npe873,
        "variant_b_same_873_npe": b_same,
        "discriminator": discriminator,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"R1D_DISCRIMINATOR={discriminator}")
    return 0 if discriminator != "UNKNOWN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
