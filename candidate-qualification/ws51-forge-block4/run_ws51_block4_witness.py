#!/usr/bin/env python3
"""WS51 BLOCK-4 witness driver (qualification-only, grants no credit).

Hand-built native combat equivalent of the WS05-MP-BLOCK-4 restore shape
(2 attackers, 1 P2 blocker, devModeSet declare_blockers, updateCombatForView
— the exact Ws40SuccessorState.applyCombat sequence, rebuilt by hand without
any restore machinery). Compiles ws51_block4_witness_template.java against
pinned Forge classes into scratch space (never into any artifact) and runs:

  A LOAD_UNREPAIRED ...... loader-exact, no finalization
  B LOAD_FLAGMIRROR ....... A + exact provisional overlay formula
  C LOAD_NATIVE_FINALIZE . A + Combat.fireTriggersForUnblockedAttackers
  D LOAD_FLAGMIRROR_TRIGGER (B shape, unblocked attacker = Abyssal
                             Nightstalker, mandatory AttackerUnblocked)
  E LOAD_NATIVE_TRIGGER ... (C shape with Nightstalker)
  F LOAD_PIPELINE_TAIL .... A + exact skipped declare-blockers tail
                             (orderBlockers, orderAttackers, removeAbsent,
                             fireTriggers) in pipeline order

Adjudication (all must hold, else UNKNOWN — no claim):
  A == NPE "AttackingBand.isBlocked() is null" at Combat:873
  B == RETURNED AND chooser never consulted AND ledger bearA_taken == 0
       AND runeclaw_taken == 0 AND p2_life == 18 (only the unblocked
       attacker hits) AND sim stays false
  C == RETURNED AND flags == B AND same silent ledger AND sim false
  D == RETURNED AND sim_before/after both false (trigger lost)
  E == RETURNED AND sim_before false AND sim_after true (native fires)
  F == RETURNED AND chooser consulted once for the bearA division over
       exactly the two injected blockers AND identity_match AND ledger
       bearA_taken == 4 AND runeclaw_taken == 2 AND p2_life == 18
  => RESTORE_DECISION_GAP_PROVEN.

Usage:
  run_ws51_block4_witness.py --forge /tmp/opencode/ws51-forge-pin \
      --classpath-file <file> --out <result.json> [--workdir <dir>]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

FORGE_COMMIT = "66caae16015bd403bc0a52fa6689afb5508f74d0"
FORGE_TREE = "40fc8f29ce4de31a964972461db2b48b4221e07f"
HERE = Path(__file__).resolve().parent
# Exact provisional formula shipped in the WS48 overlay; the witness must test
# precisely this computation, not a paraphrase.
MIRROR_FORMULA = "band.setBlocked(!combat.getBlockers(band).isEmpty());"


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
            raise SystemExit(f"WS51_ABSTRACT_PARSE_SUSPECT:{decl[:120]}")
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
    ap.add_argument("--workdir", type=Path, default=Path("/tmp/ws51/witness"))
    a = ap.parse_args()

    head = subprocess.check_output(
        ["git", "-C", str(a.forge), "rev-parse", "HEAD"], text=True).strip()
    tree = subprocess.check_output(
        ["git", "-C", str(a.forge), "rev-parse", "HEAD^{tree}"], text=True).strip()
    if head != FORGE_COMMIT or tree != FORGE_TREE:
        raise SystemExit(f"WS51_FORGE_LOCK_MISMATCH head={head} tree={tree}")

    # Formula parity: the witness must exercise the exact shipped computation.
    overlay = (HERE.parent / "ws48-forge-v1.0.5"
               / "ws48_behavior_provider_overlay.py").read_text(encoding="utf-8")
    tpl_raw = (HERE / "ws51_block4_witness_template.java").read_text(encoding="utf-8")
    if MIRROR_FORMULA not in overlay:
        raise SystemExit("WS51_MIRROR_FORMULA_MISSING_FROM_OVERLAY")
    if MIRROR_FORMULA not in tpl_raw:
        raise SystemExit("WS51_MIRROR_FORMULA_MISSING_FROM_WITNESS")
    if "WS51_MIRROR_UNDER_TEST" not in tpl_raw:
        raise SystemExit("WS51_MIRROR_LABEL_MISSING")

    pc = (a.forge / "forge-game/src/main/java/forge/game/player/PlayerController.java"
          ).read_text(encoding="utf-8")
    methods = abstract_methods(pc)
    if not methods:
        raise SystemExit("WS51_NO_ABSTRACT_METHODS")
    stubs = []
    for prefix, name, params, throws in methods:
        if name == "chooseCombatDamage":
            continue  # observation-only override lives in the template
        clause = f" {throws}" if throws else ""
        stubs.append(
            f"        @Override\n        public {prefix} {name}({params}){clause} {{\n"
            f'            throw new Ws51StubReached("{name}");\n        }}')
    stub_block = "\n\n".join(stubs)

    pc_imports = sorted(set(
        line.strip() for line in pc.splitlines()
        if line.startswith("import ")))
    tpl = tpl_raw
    if "__STUB_METHODS__" not in tpl:
        raise SystemExit("WS51_TEMPLATE_PLACEHOLDER_MISSING")

    work = a.workdir
    srcdir = work / "src/forge/game/player"
    clsdir = work / "classes"
    srcdir.mkdir(parents=True, exist_ok=True)
    clsdir.mkdir(parents=True, exist_ok=True)
    gen = tpl.replace("__STUB_METHODS__", stub_block)
    have = set(l.strip() for l in gen.splitlines() if l.startswith("import "))
    extra = [l for l in pc_imports if l not in have]
    gen = gen.replace("import forge.CardStorageReader;",
                      "\n".join(extra + ["import forge.CardStorageReader;"]),
                      1)
    (srcdir / "Ws51Block4Witness.java").write_text(gen, encoding="utf-8")

    cp = a.classpath_file.read_text(encoding="utf-8").strip()
    javac = subprocess.run(
        ["javac", "-cp", cp, "-d", str(clsdir),
         str(srcdir / "Ws51Block4Witness.java")],
        capture_output=True, text=True)
    if javac.returncode != 0:
        raise SystemExit(f"WS51_JAVAC_FAIL:\n{javac.stderr[-3000:]}")
    code_lines = [l for l in gen.splitlines()
                  if not l.strip().startswith(("//", "*", "/*"))]
    code_only = "\n".join(code_lines)
    if re.search(r"\bWs40SuccessorState\b|\bapplyNativeState\b|\bGameState\b"
                 r"|RESTORE_SNAPSHOT", code_only):
        raise SystemExit("WS51_REPRO_CONTAMINATED_BY_RESTORE")

    lang_dir = a.forge / "forge-gui/res/languages"
    rows = []
    for variant in ("A", "B", "C", "D", "E", "F"):
        r = subprocess.run(
            ["java", "-cp", f"{clsdir}:{cp}",
             "forge.game.player.Ws51Block4Witness", variant, str(lang_dir)],
            capture_output=True, text=True, timeout=300)
        line = (r.stdout.strip().splitlines() or [""])[-1]
        try:
            row = json.loads(line)
        except Exception:
            row = {"ws51_variant": variant, "outcome": "DRIVER_PARSE_FAIL",
                   "rc": r.returncode, "stdout_tail": r.stdout[-2000:],
                   "stderr_tail": r.stderr[-2000:]}
        row["rc"] = r.returncode
        row["stderr_tail"] = r.stderr[-1500:]
        rows.append(row)
        print(f"WS51 variant {row.get('ws51_variant')} -> {row.get('outcome')} "
              f"top={row.get('top_frame')} sim={row.get('sim_before_finalize')}"
              f"->{row.get('sim_after_finalize')} identity={row.get('identity_match')} "
              f"ledger={row.get('ledger')}", flush=True)

    by = {r["ws51_variant"]: r for r in rows}

    def is_npe873(r):
        return ("NULL_POINTER" in str(r.get("outcome"))
                and "AttackingBand.isBlocked()" in str(r.get("detail"))
                and "Combat.assignAttackersDamage(Combat.java:873)"
                in str(r.get("top_frame", "")))

    def ledger(r):
        out = {}
        for part in str(r.get("ledger", "")).split(":"):
            if "=" in part:
                k, v = part.split("=", 1)
                try:
                    out[k] = int(v)
                except ValueError:
                    out[k] = v
        return out

    checks = {}
    checks["A_reproduces_873_npe"] = is_npe873(by["A"])
    lb = ledger(by["B"])
    checks["B_silent_damage_loss"] = (
        by["B"].get("outcome") == "RETURNED"
        and by["B"].get("chooser_calls") == 0
        and by["B"].get("band_flags") == "A:true,B:false"
        and by["B"].get("sim_before_finalize") is False
        and by["B"].get("sim_after_finalize") is False
        and lb.get("bearA_taken") == 0
        and lb.get("runeclaw_taken") == 0
        and lb.get("p2bears_taken") == 0
        and lb.get("attackerB_taken") == 0
        and lb.get("p2_life") == 18
        and lb.get("p1_life") == 20)
    lc = ledger(by["C"])
    checks["C_parity_silent_loss"] = (
        by["C"].get("outcome") == "RETURNED"
        and by["C"].get("chooser_calls") == 0
        and by["C"].get("band_flags") == by["B"].get("band_flags")
        and lc.get("bearA_taken") == 0
        and lc.get("runeclaw_taken") == 0
        and lc.get("p2_life") == 18
        and by["C"].get("sim_after_finalize") is False)
    checks["D_trigger_silently_lost"] = (
        by["D"].get("outcome") == "RETURNED"
        and by["D"].get("trigger_bearer") is True
        and by["D"].get("sim_before_finalize") is False
        and by["D"].get("sim_after_finalize") is False)
    checks["E_native_fires_trigger"] = (
        by["E"].get("outcome") == "RETURNED"
        and by["E"].get("trigger_bearer") is True
        and by["E"].get("sim_before_finalize") is False
        and by["E"].get("sim_after_finalize") is True)
    lf = ledger(by["F"])
    checks["F_native_assigns_blocked_damage"] = (
        by["F"].get("outcome") == "RETURNED"
        and by["F"].get("identity_match") is True
        and by["F"].get("chooser_calls") == 1
        and lf.get("bearA_taken") == 4
        and lf.get("runeclaw_taken") == 2
        and lf.get("p2bears_taken") == 0
        and lf.get("p2_life") == 18
        and lf.get("p1_life") == 20)
    checks["B_flags_match_native_formula"] = (
        by["B"].get("band_flags") == by["C"].get("band_flags")
        == "A:true,B:false")

    if all(checks.values()):
        verdict = "RESTORE_DECISION_GAP_PROVEN"
    else:
        verdict = "UNKNOWN"
    result = {
        "schema_version": "commander-lab.ws51-block4-witness/1.0.0",
        "evidence_class": "HAND_BUILT_NATIVE_REPRO",
        "grants_behavior_credit": False,
        "forge": {"commit": head, "tree": tree, "version": "2.0.15-SNAPSHOT"},
        "mirror_formula_parity": True,
        "abstract_stub_count": len(methods),
        "rng_seed": 510051,
        "rows": rows,
        "checks": checks,
        "verdict": verdict,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"WS51_WITNESS={verdict}")
    return 0 if verdict != "UNKNOWN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
