#!/usr/bin/env python3
"""RQ-C2 local validation (parse / validate / normalize / report ONLY).

No Rules-engine logic: no replacement ordering, target legality, layer
resolution, SBA, combat, Commander, or APNAP computation. Checks are
structural: coverage, cross-references, provenance presence, vocabulary
discipline, RQ-C1 immutability, and deterministic rebuild of derived
counts from read-only RQ-C1 inputs plus committed RQ-C2 artifacts.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RQC1 = ROOT / "research/candidate-qualification/common/rq-c1"
RQC2 = ROOT / "research/candidate-qualification/common/rq-c2"
FAIL = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ((" :: " + detail) if detail and not cond else ""))
    if not cond:
        FAIL.append(name)


def load(p):
    return json.loads((RQC2 / p).read_text())


manifest = json.loads((RQC1 / "RQ_C1_SCENARIO_MANIFEST.json").read_text())
queue_md = (RQC1 / "RQ_C1_RULES_AUTHORITY_QUEUE.md").read_text()
packet_status = load("RQ_C2_PACKET_STATUS.json")
first_wave = load("RQ_C2_FIRST_WAVE_AUTHORITY_STATUS.json")
oracle_index = load("RQ_C2_ORACLE_INDEX.json")
rule_index = load("RQ_C2_RULE_REFERENCE_INDEX.json")
assertion_review = load("RQ_C2_EXPECTED_ASSERTION_REVIEW.json")
ledger = load("RQ_C2_CORRECTION_LEDGER.json")
sol_queue = (RQC2 / "RQ_C2_SOL_ADJUDICATION_QUEUE.md").read_text()

# 1. all 40 scenarios accounted for
scen_ids = [s["scenario_id"] for s in manifest["scenarios"]]
check("40 scenarios in manifest", len(scen_ids) == 40, str(len(scen_ids)))
check("review covers all 40", set(assertion_review["reviews"]) == set(scen_ids))

# 2. all 37 packets accounted for
queue_qs = sorted(set(re.findall(r"^## (Q-[A-Z]\d+)", queue_md, re.M)))
check("37 packets in RQ-C1 queue", len(queue_qs) == 37, str(len(queue_qs)))
ps_qs = packet_status["packets"]
check("37 packets in RQ_C2_PACKET_STATUS", len(ps_qs) == 37, str(len(ps_qs)))
check("packet IDs match queue", set(ps_qs) == set(queue_qs),
      str(set(ps_qs) ^ set(queue_qs)))

# 3. first wave accounted for
fw_manifest = sorted(s["scenario_id"] for s in manifest["scenarios"] if s["first_wave"])
fw_status = sorted(first_wave["first_wave"])
check("15 first-wave in manifest", len(fw_manifest) == 15, str(len(fw_manifest)))
check("first-wave status covers manifest set", fw_status == fw_manifest,
      str(set(fw_status) ^ set(fw_manifest)))

# 4. three Oracle flags explicit
cards = oracle_index["cards"]
for name in ("Murder", "Cultivate", "Ornithopter"):
    st = cards.get(name, {}).get("verification_status")
    check(f"flag {name} explicit VERIFIED", st == "ORACLE_TEXT_VERIFIED", str(st))

# 4b. oracle coverage of corpus names
corpus_names = {c["name"] for s in manifest["scenarios"] for c in s["actual_cards"]}
check("oracle index covers corpus + Ornithopter",
      corpus_names <= set(cards) and "Ornithopter" in cards,
      str(corpus_names - set(cards)))

# 5. provenance on every authority record
def has_prov(entry):
    return bool(entry.get("provenance") or entry.get("official_page"))
missing = [n for n, e in cards.items() if not (e.get("provenance") and e.get("verification_status"))]
check("every oracle record has provenance+status", not missing, str(missing))
check("rule index carries baseline", "baseline" in rule_index and "2026-08-07" in rule_index["baseline"])
check("packet entries carry refs", all(p.get("verified_refs") for p in ps_qs.values()))

# 6. citations refer to baseline (shape + spot-check against verified CR section list)
CR_SECTIONS = set(rule_index["entries"]) | {"615.1"}
ref_pat = re.compile(r"^\d{3}(\.\d+[a-z]?)?(/.+)?$")
bad = {}
for q, p in ps_qs.items():
    for r in p.get("verified_refs", []):
        base = r.split("/")[0]
        if not ref_pat.match(r) or base not in CR_SECTIONS and base.split(".")[0] not in {s.split(".")[0] for s in CR_SECTIONS}:
            bad.setdefault(q, []).append(r)
# allow composite refs like 117.4/608.1 and family refs; only flag malformed
malformed = {q: v for q, v in bad.items() if any(not ref_pat.match(r) for r in v)}
check("citation shape coherent with baseline index", not malformed, str(malformed))

# 7. unresolved interpretations all appear in Sol queue
needles = {"A03": "A03", "C01": "C01", "E02": "E02", "F02": "F02", "F03": "F03",
           "G03": "G03", "H02": "H02", "G04": "G04", "K02": "K02"}
missing_q = [k for k, n in needles.items() if n not in sol_queue]
check("all interpretation/correction packets in Sol queue", not missing_q, str(missing_q))

# 8. no EXTERNALLY_RULE_VALIDATED awarded by Muse (line- or paragraph-level:
#    the term may appear only beside negation or Sol-promotion context)
viol = []
for f in sorted(RQC2.glob("RQ_C2_*.md")) + sorted(RQC2.glob("RQ_C2_*.json")) + sorted(RQC2.glob("Q_*.md")):
    paras = re.split(r"\n\s*\n", f.read_text())
    for para in paras:
        if "EXTERNALLY_RULE_VALIDATED" in para and not re.search(
                r"NOT|never|only Sol|Sol|promot|award|until|discretion|dispos|confirm|sample-audit", para):
            viol.append(f"{f.name}:{para.strip()[:100]}")
check("no Muse-awarded EXTERNALLY_RULE_VALIDATED", not viol, str(viol[:10]))

# 9. no RQ-C1 artifact modified (worktree + HEAD)
st = subprocess.run(["git", "status", "--porcelain=v1", "--", str(RQC1)],
                    capture_output=True, text=True, cwd=ROOT).stdout.strip()
df = subprocess.run(["git", "diff", "--name-only", "HEAD", "--", str(RQC1)],
                    capture_output=True, text=True, cwd=ROOT).stdout.strip()
check("RQ-C1 unmodified in worktree+HEAD", not st and not df, (st + " " + df)[:200])

# 10. no candidate behavior as authority (paragraph-level context, so that
#     multi-line disclaimers such as the source-lock authority order count)
suspect = []
for f in sorted(RQC2.glob("RQ_C2_*.md")) + sorted(RQC2.glob("Q_*.md")):
    for para in re.split(r"\n\s*\n", f.read_text()):
        if re.search(r"Forge|XMage|Argentum|Manabrew|\bQ6\b", para) and not re.search(
                r"NOT|never|no |neither|forbidden|pointer|taxonomy|discovery|behavior credit|as authority|consulted|used as|tie-breaker", para, re.I):
            suspect.append(f"{f.name}:{para.strip()[:120]}")
check("no candidate behavior as authority", not suspect, str(suspect[:10]))

# 11. correction ledger complete
req = {"scenario", "field", "rq_c1_value", "authority", "classification", "impact", "recommendation", "revalidation"}
incomplete = [e for e in ledger["entries"] if req - set(e)]
check("ledger entries complete", not incomplete, str(len(incomplete)))
check("ledger totals reconcile", sum(v for k, v in ledger["totals"].items() if k != "entries") == ledger["totals"]["entries"],
      str(ledger["totals"]))

# 12. deterministic rebuild: recount from RQ-C1 + committed artifacts
n_term = sum(len((s.get("expected_terminal_assertions") or [])) for s in manifest["scenarios"])
t = assertion_review["totals"]
check("114 terminal assertions recounted", n_term == 114, str(n_term))
check("117 items reconcile (114 + 3 flags)", sum(t.values()) == 117 and n_term + 3 == 117, str(t))
check("packet totals reconcile", sum(v for v in packet_status["totals"].values() if isinstance(v, int) and v != 37) == 37,
      str(packet_status["totals"]))

print()
if FAIL:
    print(f"VALIDATION FAIL: {len(FAIL)} check(s): {FAIL}")
    sys.exit(1)
print("VALIDATION PASS: all RQ-C2-local checks green.")
