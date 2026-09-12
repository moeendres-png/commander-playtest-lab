#!/usr/bin/env python3
"""WS72 cross-candidate actual-card availability preflight.

Mechanically derives the required actual-card corpus from exact RQ-C3
authority and checks source presence/registration against the exact
accepted Forge and XMage candidate pins using READ-ONLY git object
operations only. No checkouts, no engine modification, no behavior
execution. Presence grants ZERO behavior credit.

Evidence class for all presence results: CODE_DERIVED (no runtime smoke).

Deterministic: all outputs sorted; dicts dumped with sort_keys.
"""
import json
import os
import re
import subprocess
import sys

# ---------------------------------------------------------------- locks
RQ_C3_PIN = "897d72f0b57bb8febe045870acaa3d2dba4bde56"
FORGE_PIN = "a9a95db6662c2d28814390a9c0c2f986e39aa8b4"
FORGE_TREE = "2c18327f79e330f2ed167067166ffd42d61b0849"
XMAGE_PIN = "7135d5e85ddb4c8aa4b49b4192ca51947c822704"
XMAGE_TREE = "ea193e0d04493d53d962ed13ebd3b5d2f68838c7"
FORGE_REMOTE = "https://github.com/moeendres-png/forge.git"
XMAGE_REMOTE = "https://github.com/moeendres-png/mage.git"

RQC1_IDS = [
    "A01", "A02", "A03", "A04", "B01", "B02", "B03", "B04",
    "C01", "C02", "C03", "C04", "D01", "D02", "D03", "D04",
    "D05", "D06", "E01", "E02", "E03", "F01", "F02", "F03",
    "F04", "G01", "G02", "G03", "G04", "G05", "H01", "H02",
    "I01", "I02", "I03", "J01", "J02", "J03", "K01", "K02",
]

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

FORGE_REPO = None  # resolved at runtime (read-only discovery)
XMAGE_REPO = None


def run_git(args, cwd):
    p = subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                       text=True, timeout=300)
    return p


def git_show_blob(repo, rev_path):
    p = run_git(["show", rev_path], cwd=repo)
    if p.returncode != 0:
        raise RuntimeError(f"git show failed: {rev_path}: {p.stderr.strip()}")
    return p.stdout


def git_grep_files(repo, rev, pattern, paths):
    """Return sorted list of blob paths containing pattern at rev (fixed string)."""
    p = run_git(["grep", "-F", "--name-only", "-e", pattern, rev, "--"] + paths,
                cwd=repo)
    if p.returncode not in (0, 1):
        raise RuntimeError(f"git grep failed: {p.stderr.strip()}")
    return sorted(l.split(":", 1)[1] if l.startswith(rev + ":") else l
                  for l in p.stdout.splitlines() if l.strip())


def git_lstree(repo, rev, path):
    p = run_git(["ls-tree", rev, "--name-only", "--", path], cwd=repo)
    if p.returncode != 0:
        return []
    return sorted(l for l in p.stdout.splitlines() if l.strip())


def discover_engine_repo(candidates, pin, tree, expected_remote, label):
    tried = []
    for cand in candidates:
        if not os.path.isdir(os.path.join(cand, ".git")):
            tried.append({"path": cand, "result": "no-git-dir"})
            continue
        h = run_git(["show", "-s", "--format=%H", pin], cwd=cand)
        if h.returncode != 0:
            tried.append({"path": cand, "result": "object-absent"})
            continue
        if h.stdout.strip() != pin:
            tried.append({"path": cand, "result": "hash-mismatch"})
            continue
        t = run_git(["show", "-s", "--format=%T", pin], cwd=cand)
        if t.returncode != 0 or t.stdout.strip() != tree:
            raise RuntimeError(f"{label}: tree mismatch at {cand}")
        r = run_git(["config", "--get", "remote.origin.url"], cwd=cand)
        remote = r.stdout.strip()
        if remote != expected_remote:
            raise RuntimeError(
                f"{label}: remote identity mismatch at {cand}: {remote!r}")
        return cand, remote, tried
    raise RuntimeError(f"{label}: exact pin {pin} not found in {tried}")


# ------------------------------------------------------------ corpus
ZONE_KEYS = ("battlefield", "hands", "command_zone", "graveyards",
             "exile", "stack")
SKIP_TOKENS = ("HIDDEN",)
PAREN_RE = re.compile(r"\s*\(.*\)\s*$")


def collect_state_cards(state):
    """Collect (raw_name, zone) pairs from neutral_initial_state zones."""
    found = []
    if not isinstance(state, dict):
        return found
    for zone in ZONE_KEYS:
        val = state.get(zone)
        if val is None:
            continue
        if zone == "battlefield" or zone == "stack":
            items = val if isinstance(val, list) else []
            for it in items:
                if isinstance(it, dict) and isinstance(it.get("card"), str):
                    found.append((it["card"], zone))
        elif zone in ("hands", "graveyards", "exile"):
            if isinstance(val, dict):
                for _p, lst in val.items():
                    if isinstance(lst, list):
                        for n in lst:
                            if isinstance(n, str):
                                found.append((n, zone))
                    elif isinstance(lst, str):
                        found.append((lst, zone))
            elif isinstance(val, list):
                for it in val:
                    if isinstance(it, dict) and isinstance(it.get("card"), str):
                        found.append((it["card"], zone))
                    elif isinstance(it, str):
                        found.append((it, zone))
        elif zone == "command_zone":
            if isinstance(val, list):
                for it in val:
                    if isinstance(it, dict) and isinstance(it.get("card"), str):
                        found.append((it["card"], zone))
                    elif isinstance(it, str):
                        found.append((it, zone))
    return found


def normalize_state_name(raw):
    """Strip authority annotations: text before the first ' (' is the printed
    card name (handles trailing and mid-string annotations such as
    'Control Magic (P0) enchanting Bear'). Returns (base, alias_or_None)."""
    s = raw.strip()
    base = s.split(" (", 1)[0].strip()
    if base != s:
        return base, s
    return base, None


PLACEHOLDER_RE = re.compile(r"^(noncreature spell|any .*|.*\(.*\))$", re.I)


def build_corpus(repo):
    rqc3_manifest = json.loads(git_show_blob(
        repo, f"{RQ_C3_PIN}:research/candidate-qualification/common/rq-c3/"
        "RQ_C3_CORRECTED_SCENARIO_MANIFEST.json"))
    overlay = {}
    for s in rqc3_manifest["scenarios"]:
        overlay[s["parent_scenario_id"]] = {
            "rqc3_id": s["rqc3_scenario_id"],
            "first_wave": bool(s.get("first_wave")),
        }
    scenarios = []
    cards = {}  # name -> {oracle_ids:set, scenario_roles:{scen:[roles]}, aliases:set, state_zones:{scen:[zones]}}
    excluded = []  # non-card placeholders, with reasons
    for suf in RQC1_IDS:
        c1id = f"RQ-C1-{suf}"
        c1 = json.loads(git_show_blob(
            repo, f"{RQ_C3_PIN}:research/candidate-qualification/common/rq-c1/"
            f"scenarios/{c1id}.json"))
        ov = overlay.get(c1id)
        if ov is not None:
            scen = json.loads(git_show_blob(
                repo, f"{RQ_C3_PIN}:research/candidate-qualification/common/"
                f"rq-c3/scenarios/{ov['rqc3_id']}.json"))
            scen_id = ov["rqc3_id"]
            fw = ov["first_wave"]
            corrected = True
        else:
            scen = c1
            scen_id = c1id
            fw = bool(c1.get("first_wave"))
            corrected = False
        scen_cards = []
        for ac in scen.get("actual_cards", []):
            name = ac["name"]
            e = cards.setdefault(name, {"oracle_ids": set(), "roles": {},
                                       "aliases": set(), "zones": {}})
            if ac.get("oracle_id"):
                e["oracle_ids"].add(ac["oracle_id"])
            e["roles"].setdefault(scen_id, [])
            if ac.get("role") and ac["role"] not in e["roles"][scen_id]:
                e["roles"][scen_id].append(ac["role"])
            scen_cards.append(name)
        for raw, zone in collect_state_cards(scen.get("neutral_initial_state", {})):
            if any(raw.startswith(t) for t in SKIP_TOKENS):
                continue
            base, alias = normalize_state_name(raw)
            if not base or PLACEHOLDER_RE.match(base):
                excluded.append({"scenario_id": scen_id, "raw": raw,
                                 "zone": zone,
                                 "reason": "non-card placeholder, not a printed card"})
                continue
            e = cards.setdefault(base, {"oracle_ids": set(), "roles": {},
                                       "aliases": set(), "zones": {}})
            if alias:
                e["aliases"].add(alias)
            e["zones"].setdefault(scen_id, [])
            if zone not in e["zones"][scen_id]:
                e["zones"][scen_id].append(zone)
            if base not in scen_cards:
                scen_cards.append(base)
        scenarios.append({
            "scenario_id": scen_id,
            "parent_scenario_id": c1id,
            "rqc3_corrected": corrected,
            "first_wave": fw,
            "title": scen.get("title"),
            "cards": sorted(set(scen_cards)),
        })
    scenarios.sort(key=lambda s: s["scenario_id"])
    corpus_cards = []
    for name in sorted(cards):
        e = cards[name]
        corpus_cards.append({
            "name": name,
            "oracle_ids": sorted(e["oracle_ids"]),
            "scenario_ids": sorted(set(list(e["roles"].keys())
                                       + list(e["zones"].keys()))),
            "roles": {k: sorted(v) for k, v in sorted(e["roles"].items())},
            "state_zones": {k: sorted(v) for k, v in sorted(e["zones"].items())},
            "aliases": sorted(e["aliases"]),
        })
    return scenarios, corpus_cards, sorted(excluded, key=lambda d: (d["scenario_id"], d["raw"]))


# ------------------------------------------------------------ lookups
def forge_snake(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def forge_lookup(card):
    name = card["name"]
    evidence = {"lookup_mechanism": "git grep -F 'Name:<exact>' at pin under forge-gui/res/cardsfolder/ + Name-field verification via git show",
                "commit": FORGE_PIN}
    name_files = git_grep_files(FORGE_REPO, FORGE_PIN, f"Name:{name}",
                                ["forge-gui/res/cardsfolder/"])
    exact = []
    for f in name_files:
        try:
            blob = git_show_blob(FORGE_REPO, f"{FORGE_PIN}:{f}")
        except RuntimeError:
            continue
        m = re.match(r"^Name:(.*)$", blob.splitlines()[0] if blob else "")
        if m and m.group(1).strip() == name:
            exact.append(f)
    snake_probe = f"forge-gui/res/cardsfolder/{forge_snake(name)[:1]}/{forge_snake(name)}.txt"
    snake_exists = bool(git_lstree(FORGE_REPO, FORGE_PIN, snake_probe)) if forge_snake(name) else False
    evidence["name_grep_files"] = name_files
    evidence["exact_name_files"] = exact
    evidence["snake_probe_path"] = snake_probe
    evidence["snake_probe_exists"] = snake_exists
    if len(exact) > 1:
        # check whether duplicates are identical blobs (full-file copies) or distinct
        blobs = set()
        for f in exact:
            blobs.add(git_show_blob(FORGE_REPO, f"{FORGE_PIN}:{f}"))
        if len(blobs) == 1:
            status = "SOURCE_IMPLEMENTATION_FOUND"
            evidence["duplicate_note"] = "multiple identical-blob paths; single implementation copied"
        else:
            status = "AMBIGUOUS"
            evidence["ambiguity"] = "multiple distinct implementations share the exact Name"
    elif len(exact) == 1:
        status = "SOURCE_IMPLEMENTATION_FOUND"
    else:
        # token / alternate-surface probe across forge-gui/res
        wider = git_grep_files(FORGE_REPO, FORGE_PIN, f"Name:{name}", ["forge-gui/res/"])
        evidence["wider_res_probe_files"] = wider
        if wider:
            status = "AMBIGUOUS"
            evidence["ambiguity"] = ("exact Name found outside canonical cardsfolder "
                                     "(possible token/alternate surface); canonical registration unconfirmed")
        else:
            status = "NOT_FOUND"
    evidence["candidate_registration"] = (
        "forge-core/src/main/java/forge/CardStorageReader.java loads the cardsfolder "
        "surface at runtime (registration surface = cardsfolder presence)"
        if status in ("SOURCE_IMPLEMENTATION_FOUND",) else
        "no cardsfolder registration surface entry located" if status == "NOT_FOUND" else
        "registration surface entry ambiguous, see ambiguity")
    return status, evidence


def xmage_class(name):
    return re.sub(r"[^A-Za-z0-9]", "", name)


def xmage_lookup(card):
    name = card["name"]
    cls_guess = xmage_class(name)
    evidence = {"lookup_mechanism": ("set-registration-first: quoted-name grep at pin under "
                "Mage.Sets/src/mage/sets/ -> mage.cards.*.class refs on name-bearing lines "
                "-> impl existence probe via git ls-tree; class-name guess only secondary"),
                "commit": XMAGE_PIN,
                "derived_class_guess": cls_guess,
                "aliases_or_normalization": []}
    set_files = git_grep_files(XMAGE_REPO, XMAGE_PIN, f'"{name}"',
                               ["Mage.Sets/src/mage/sets/"])
    evidence["set_nameref_files"] = set_files
    # Extract referenced impl classes from name-bearing lines in set files.
    ref_classes = set()
    for f in set_files:
        try:
            blob = git_show_blob(XMAGE_REPO, f"{XMAGE_PIN}:{f}")
        except RuntimeError:
            continue
        for line in blob.splitlines():
            if f'"{name}"' in line:
                for m in re.finditer(r"mage\.cards\.([A-Za-z0-9_.]+)\.class", line):
                    ref_classes.add(m.group(1))
    evidence["referenced_impl_classes"] = sorted(ref_classes)
    impl = []
    for dotted in sorted(ref_classes):
        # dotted is relative to mage.cards (regex captured after that prefix),
        # e.g. 'r.RestInPeace' -> Mage.Sets/src/mage/cards/r/RestInPeace.java
        parts = dotted.split(".")
        if len(parts) < 2 or not all(parts):
            continue
        rel = "/".join(parts)
        for base in ("Mage.Sets/src/mage/cards", "Mage/src/main/java/mage/cards"):
            probe = f"{base}/{rel}.java"
            if git_lstree(XMAGE_REPO, XMAGE_PIN, probe) and probe not in impl:
                impl.append(probe)
    # Secondary: canonical class-name guess probe (covers impl-registered-but-unquoted cases).
    if cls_guess:
        probe = f"Mage.Sets/src/mage/cards/{cls_guess[0].lower()}/{cls_guess}.java"
        if git_lstree(XMAGE_REPO, XMAGE_PIN, probe) and probe not in impl:
            impl.append(probe)
            evidence["aliases_or_normalization"].append(
                f"impl located via canonical class-name guess {cls_guess}")
        basic = f"Mage/src/main/java/mage/cards/basiclands/{cls_guess}.java"
        if git_lstree(XMAGE_REPO, XMAGE_PIN, basic) and basic not in impl:
            impl.append(basic)
    for dotted in sorted(ref_classes):
        canon = dotted.split(".")[-1]
        if canon != cls_guess:
            evidence["aliases_or_normalization"].append(
                f"class-name normalization: printed {name!r} -> impl class {canon}")
    evidence["impl_class_files"] = sorted(impl)
    evidence["aliases_or_normalization"] = sorted(set(evidence["aliases_or_normalization"]))
    if impl and set_files:
        status = "REGISTERED_OR_RESOLVABLE"
    elif impl and not set_files:
        # confirm some set file references the located impl class
        canon_refs = []
        for p in impl:
            m = re.match(r"^(?:Mage\.Sets/src/mage/cards|Mage/src/main/java/mage/cards)/(.+)\.java$", p)
            if m:
                canon_refs.extend(git_grep_files(
                    XMAGE_REPO, XMAGE_PIN,
                    "mage.cards." + m.group(1).replace("/", ".") + ".class",
                    ["Mage.Sets/src/mage/sets/"]))
        evidence["set_classref_files"] = sorted(set(canon_refs))
        if canon_refs:
            status = "REGISTERED_OR_RESOLVABLE"
        else:
            status = "SOURCE_IMPLEMENTATION_FOUND"
            evidence["set_classref_files"] = []
    elif not impl and set_files:
        status = "AMBIGUOUS"
        evidence["ambiguity"] = ("set registration references the card name but none of the "
                                 "referenced impl classes exist at pin")
    else:
        token_hits = git_grep_files(XMAGE_REPO, XMAGE_PIN, f'"{name}"',
                                    ["Mage.Sets/src/mage/cards/tokens/"])
        evidence["token_probe_files"] = token_hits
        if token_hits:
            status = "AMBIGUOUS"
            evidence["ambiguity"] = ("no full-card impl/registration; only token-surface "
                                     "references located; token representation unconfirmed as scenario role")
        else:
            status = "NOT_FOUND"
    if status in ("REGISTERED_OR_RESOLVABLE", "SOURCE_IMPLEMENTATION_FOUND"):
        evidence["candidate_registration"] = (
            "Mage/src/main/java/mage/cards/repository/CardScanner.java + "
            "CardRepository.java scan the mage.sets SetCardInfo surface at runtime")
    else:
        evidence["candidate_registration"] = "no impl/registration located (or ambiguous)"
    return status, evidence


# ------------------------------------------------------------ main
def main():
    global FORGE_REPO, XMAGE_REPO
    repo = os.environ.get("WS72_REPO",
                          "/home/moeen/code/ws72-cross-candidate-card-availability-preflight")
    forge_cands = os.environ.get("WS72_FORGE_CANDIDATES",
                                 "/home/moeen/code/forge").split(os.pathsep)
    xmage_cands = os.environ.get("WS72_XMAGE_CANDIDATES",
                                 "/home/moeen/code/ws54-xmage-rng-reexecution-remediation-engine").split(os.pathsep)
    FORGE_REPO, forge_remote, forge_tried = discover_engine_repo(
        forge_cands, FORGE_PIN, FORGE_TREE, FORGE_REMOTE, "Forge")
    XMAGE_REPO, xmage_remote, xmage_tried = discover_engine_repo(
        xmage_cands, XMAGE_PIN, XMAGE_TREE, XMAGE_REMOTE, "XMage")

    source_identity = {
        "rq_c3_authority_pin": RQ_C3_PIN,
        "forge": {"pin": FORGE_PIN, "tree": FORGE_TREE,
                  "remote": forge_remote, "discovery_tried": forge_tried},
        "xmage": {"pin": XMAGE_PIN, "tree": XMAGE_TREE,
                  "remote": xmage_remote, "discovery_tried": xmage_tried},
    }

    scenarios, cards, excluded = build_corpus(repo)
    with open(os.path.join(OUT_DIR, "WS72_ACTUAL_CARD_CORPUS.json"), "w") as f:
        json.dump({
            "schema": "ws72.actual-card-corpus.v1",
            "authority_pin": RQ_C3_PIN,
            "derivation": ("40 RQ-C1 scenario families; RQ-C3 corrected overlay preferred "
                           "where present (18); state-zone names normalized by stripping "
                           "parenthetical annotations; non-card placeholders excluded with reasons"),
            "defined_scenario_count": len(scenarios),
            "full107_note": ("RQ-C3 authority enumerates 40 unique scenarios; no authority "
                             "artifact enumerates 107 scenarios or the 'remaining 92'. "
                             "Slots beyond these 40 are AUTHORITY_ABSENT (UNKNOWN), not invented."),
            "unique_actual_card_count": len(cards),
            "scenarios": scenarios,
            "cards": cards,
            "excluded_non_cards": excluded,
            "evidence_class": "CODE_DERIVED",
        }, f, indent=2, sort_keys=True)
        f.write("\n")

    forge_rows, xmage_rows = [], []
    for card in cards:
        st, ev = forge_lookup(card)
        forge_rows.append({"name": card["name"], "oracle_ids": card["oracle_ids"],
                           "status": st, "evidence": ev,
                           "evidence_class": "CODE_DERIVED"})
        st, ev = xmage_lookup(card)
        xmage_rows.append({"name": card["name"], "oracle_ids": card["oracle_ids"],
                           "status": st, "evidence": ev,
                           "evidence_class": "CODE_DERIVED"})
    forge_rows.sort(key=lambda r: r["name"])
    xmage_rows.sort(key=lambda r: r["name"])
    with open(os.path.join(OUT_DIR, "WS72_FORGE_CARD_PREFLIGHT.json"), "w") as f:
        json.dump({"schema": "ws72.engine-card-preflight.v1", "engine": "Forge",
                   "commit": FORGE_PIN, "tree": FORGE_TREE, "remote": forge_remote,
                   "behavior_credit_note": "SOURCE FOUND != BEHAVIOR PASS. Presence grants zero behavior credit.",
                   "results": forge_rows, "evidence_class": "CODE_DERIVED"},
                  f, indent=2, sort_keys=True)
        f.write("\n")
    with open(os.path.join(OUT_DIR, "WS72_XMAGE_CARD_PREFLIGHT.json"), "w") as f:
        json.dump({"schema": "ws72.engine-card-preflight.v1", "engine": "XMage",
                   "commit": XMAGE_PIN, "tree": XMAGE_TREE, "remote": xmage_remote,
                   "behavior_credit_note": "SOURCE FOUND != BEHAVIOR PASS. Presence grants zero behavior credit.",
                   "results": xmage_rows, "evidence_class": "CODE_DERIVED"},
                  f, indent=2, sort_keys=True)
        f.write("\n")

    fmap = {r["name"]: r["status"] for r in forge_rows}
    xmap = {r["name"]: r["status"] for r in xmage_rows}

    def scen_status(statuses):
        if any(s == "UNKNOWN" for s in statuses):
            return "UNKNOWN"
        if any(s == "NOT_FOUND" for s in statuses):
            return "HAS_NOT_FOUND"
        if any(s == "AMBIGUOUS" for s in statuses):
            return "HAS_AMBIGUOUS"
        return "ALL_FOUND"

    matrix = []
    for s in scenarios:
        fs = [fmap[n] for n in s["cards"]]
        xs = [xmap[n] for n in s["cards"]]
        matrix.append({
            "scenario_id": s["scenario_id"],
            "parent_scenario_id": s["parent_scenario_id"],
            "first_wave": s["first_wave"],
            "forge_card_preflight": scen_status(fs),
            "xmage_card_preflight": scen_status(xs),
            "forge_blocking_cards": sorted({n for n, st in zip(s["cards"], fs)
                                            if st in ("NOT_FOUND", "AMBIGUOUS", "UNKNOWN")}),
            "xmage_blocking_cards": sorted({n for n, st in zip(s["cards"], xs)
                                            if st in ("NOT_FOUND", "AMBIGUOUS", "UNKNOWN")}),
            "cards": s["cards"],
            "note": ("card presence only; NOT behavior READY"),
        })
    with open(os.path.join(OUT_DIR, "WS72_SCENARIO_CARD_MATRIX.json"), "w") as f:
        json.dump({"schema": "ws72.scenario-card-matrix.v1",
                   "defined_scenario_count": len(matrix),
                   "scenarios": matrix,
                   "authority_absent_slots": {
                       "count": 67,
                       "status": "UNKNOWN",
                       "reason": ("no authority artifact enumerates the remaining "
                                  "Full107-minus-40 scenarios; not invented")},
                   "evidence_class": "CODE_DERIVED"}, f, indent=2, sort_keys=True)
        f.write("\n")

    # clusters
    clusters = {}
    for rows, eng in ((forge_rows, "forge"), (xmage_rows, "xmage")):
        for r in rows:
            if r["status"] in ("NOT_FOUND", "AMBIGUOUS", "UNKNOWN"):
                ev = r["evidence"]
                cause = "true_absent_implementation"
                if "ambiguity" in ev:
                    a = ev["ambiguity"]
                    if "token" in a:
                        cause = "token_representation"
                    elif "outside canonical" in a:
                        cause = "alias_or_registration_mismatch"
                    elif "alias" in a or "rename" in a:
                        cause = "alias_or_registration_mismatch"
                    elif "identical-blob" in ev.get("duplicate_note", ""):
                        cause = "duplicate_path_same_implementation"
                    elif "Distinct" in a or "distinct" in a:
                        cause = "set_or_version_naming"
                    else:
                        cause = "alias_or_registration_mismatch"
                key = (cause, eng)
                clusters.setdefault(f"{cause}::{eng}",
                                    {"cause": cause, "engine": eng, "cards": []})["cards"].append(r["name"])
    cluster_list = sorted(({"cause": c["cause"], "engine": c["engine"],
                            "count": len(c["cards"]), "cards": sorted(c["cards"])}
                           for c in clusters.values()),
                          key=lambda d: (d["cause"], d["engine"]))
    with open(os.path.join(OUT_DIR, "WS72_MISSING_CARD_CLUSTERS.json"), "w") as f:
        json.dump({"schema": "ws72.missing-card-clusters.v1",
                   "note": "no card-name hacks applied; causes are observational only",
                   "clusters": cluster_list,
                   "evidence_class": "CODE_DERIVED"}, f, indent=2, sort_keys=True)
        f.write("\n")

    def counts(rows):
        c = {"found": 0, "not_found": 0, "ambiguous": 0, "unknown": 0}
        for r in rows:
            if r["status"] in ("SOURCE_IMPLEMENTATION_FOUND", "REGISTERED_OR_RESOLVABLE"):
                c["found"] += 1
            elif r["status"] == "NOT_FOUND":
                c["not_found"] += 1
            elif r["status"] == "AMBIGUOUS":
                c["ambiguous"] += 1
            else:
                c["unknown"] += 1
        return c
    fc, xc = counts(forge_rows), counts(xmage_rows)
    fw = [m for m in matrix if m["first_wave"]]
    nonfw = [m for m in matrix if not m["first_wave"]]

    def all_found(rows):
        return sum(1 for m in rows if m["forge_card_preflight"] == "ALL_FOUND"), \
            sum(1 for m in rows if m["xmage_card_preflight"] == "ALL_FOUND")
    fw_f, fw_x = all_found(fw)
    nf_f, nf_x = all_found(nonfw)
    summary = {
        "schema": "ws72.card-availability-summary.v1",
        "source_identity": source_identity,
        "full107_unique_actual_cards_defined_corpus": len(cards),
        "full107_denominator_note": ("40 scenarios / defined corpus cards are authority-derived; "
                                     "67 Full107 slots are AUTHORITY_ABSENT (UNKNOWN)"),
        "forge": {"found": fc["found"], "not_found": fc["not_found"],
                  "ambiguous": fc["ambiguous"], "unknown": fc["unknown"]},
        "xmage": {"found": xc["found"], "not_found": xc["not_found"],
                  "ambiguous": xc["ambiguous"], "unknown": xc["unknown"]},
        "first_wave15_forge_all_cards_found": f"{fw_f}/15",
        "first_wave15_xmage_all_cards_found": f"{fw_x}/15",
        "defined_non_first_wave25_forge_all_cards_found": f"{nf_f}/25",
        "defined_non_first_wave25_xmage_all_cards_found": f"{nf_x}/25",
        "forge_remaining92_all_cards_found": "UNKNOWN/92",
        "xmage_remaining92_all_cards_found": "UNKNOWN/92",
        "remaining92_note": ("remaining-92 population is not enumerated by RQ-C3 authority; "
                             "no runtime attempts can be cleared by this preflight"),
        "behavior_credit": "0/107",
        "full107": "NOT_RUN",
        "evidence_class": "CODE_DERIVED",
    }
    with open(os.path.join(OUT_DIR, "WS72_CARD_AVAILABILITY_SUMMARY.json"), "w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps({"unique_cards": len(cards), "scenarios": len(scenarios),
                      "forge": fc, "xmage": xc,
                      "fw_all_found": [fw_f, fw_x],
                      "nonfw_all_found": [nf_f, nf_x]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    sys.exit(main())
