"""Deterministic read-only inventory of the pinned Forge card-script corpus.

Reads blobs straight from the pinned git objects (``git ls-tree`` +
``git cat-file --batch`` in a single streaming pass). The corpus is NEVER
vendored: file contents live only in memory long enough to observe, parse,
and aggregate; only compact summaries, frequency tables, and hashes are
persisted.

Output separates three layers (never collapsed):

- TOKEN OBSERVATION: raw regular-expression token counts straight from the
  script text, independent of the Q6 parser (no interpretation).
- PARSER INTERPRETATION: what the current Q6 parser (``forge_parser``)
  makes of each file (features, diagnostics, unsupported, ambiguous).
- CAPABILITY HYPOTHESIS: what the classifier + router hypothesize
  (capability families, terminal routing states). Hypotheses only.

Scaffolding metrics only. ``BEHAVIOR_PASS = NOT_MEASURED``.

Usage::

    PYTHONPATH=tools python3 -m q6_scaffolding.corpus_inventory \\
        --corpus-dir /home/moeen/forge-corpus --ref 8c7e9afb... \\
        --out docs/qualification/q6-scaffolding/evidence/corpus-inventory.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

FORGE_PIN = "8c7e9afb8e6caee88644b94e25da5852e36f8928"
FORGE_REMOTE = "https://github.com/Card-Forge/forge.git"
CARDS_PREFIX = "forge-gui/res/cardsfolder"

# ---------------------------------------------------------------------------
# TOKEN OBSERVATION patterns (raw text only; no parser involvement).
# ---------------------------------------------------------------------------

_KEYVAL_RE = re.compile(r"^([^:\n]*):(.*)$", re.DOTALL)
_CONTAINER_VERB_RE = re.compile(r"(?:^|\|)\s*(SP|AB|DB)\$\s*([A-Za-z0-9_]+)")
_MODEKEY_RE = re.compile(
    r"(?:^|\|)\s*([A-Za-z0-9_]*[Mm][Oo][Dd][Ee][A-Za-z0-9_]*)\$\s*([A-Za-z0-9_]+)"
)
_COSTKEY_RE = re.compile(r"(?:^|\|)\s*([A-Za-z0-9_]*[Cc][Oo][Ss][Tt][A-Za-z0-9_]*)\$")
_TGTKEY_RE = re.compile(
    r"(?:^|\|)\s*([A-Za-z0-9_]*(?:Tgt|Target|Valid|Define|Choose|Choice)[A-Za-z0-9_]*)\$",
    re.IGNORECASE,
)
_SVAR_HEAD_RE = re.compile(r"^\s*([A-Za-z0-9_]+)\$")
_SUBREF_RE = re.compile(
    r"(Execute|TrueSubAbility|FalseSubAbility|SubAbility|Remembered|Imprinted)\$\s*([A-Za-z0-9_]+)"
)
_ZONEKEY_RE = re.compile(
    r"(?:^|\|)\s*((?:Origin|Destination|Zone|Defined)[A-Za-z0-9_]*)\$\s*([^\|]*)"
)
_X_TOKEN_RE = re.compile(r"(?<![A-Za-z])X(?![A-Za-z])")
# Replacement-line forms: R: lines carry Event$ + ReplacementResult$ +
# ReplaceWith$ (+ ValidMode$ reference lists also appear on T:/S: lines).
_REPL_EVENT_RE = re.compile(r"(?:^|\|)\s*Event\$\s*([A-Za-z0-9_]+)")
_REPL_RESULT_RE = re.compile(r"(?:^|\|)\s*ReplacementResult\$\s*([A-Za-z0-9_]+)")
_REPL_WITH_RE = re.compile(r"(?:^|\|)\s*ReplaceWith\$\s*([A-Za-z0-9_]+)")
_VALIDMODE_RE = re.compile(r"(?:^|\|)\s*ValidMode\$\s*([A-Za-z0-9_, ]+)")
# Cost$ head token (SubCounter<3/CHARGE> -> SubCounter; {1} stays symbolic).
_COST_HEAD_RE = re.compile(r"^\s*([A-Za-z0-9_]+)")
_COMMANDER_DAMAGE_RES = (
    re.compile(r"commander damage", re.IGNORECASE),
    re.compile(r"CommanderDamage"),
    re.compile(r"commander-damage", re.IGNORECASE),
)

# Raw indicator phrases (observation only; presence != capability claim).
_COMMANDER_SIGNALS = (
    "commander",
    "Commander",
    "command zone",
    "CommandZone",
    "commander tax",
    "partner",
)
_MULTIPLAYER_SIGNALS = (
    "each player",
    "Each player",
    "each opponent",
    "Each opponent",
    "each other",
    "target opponent",
    "Target opponent",
    "chosen opponent",
    "vote",
    "Vote",
    "will of the council",
    "monarch",
    "Monarch",
    "council",
    "starting with you",
    "attack each",
    "attack a different",
    "team",
    "shared",
)
_RANDOM_VARIANTS = (
    "shuffle",
    "flip a coin",
    "flip",
    "rolls",
    "roll a d",
    "roll a die",
    "dice",
    "die roll",
    "random",
    "coin",
)
_COPY_CONTROL_VARIANTS = (
    "copy",
    "gaincontrol",
    "gain control",
    "attach",
    "exchange",
    "control of",
    "meld",
    "clone",
)
_REPLACEMENT_SIGNALS = (
    "ReplaceEffect",
    "ETBReplacement",
    "PreventDamage",
    "Protection",
    "Regenerate",
)
_HIDDEN_SIGNALS = (
    "facedown",
    "face down",
    "look at",
    "reveal",
    "manifest",
    "morph",
    "disguise",
    "cloak",
)


def _git(cwd: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=300)


def list_corpus_files(corpus_dir: str, ref: str) -> list[tuple[str, str]]:
    """Return sorted [(path, blob_sha)] for .txt files under the cards prefix."""
    r = _git(corpus_dir, "ls-tree", "-r", ref, "--", CARDS_PREFIX)
    if r.returncode != 0:
        raise RuntimeError(f"git ls-tree failed: {r.stderr[:500]}")
    out: list[tuple[str, str]] = []
    for line in r.stdout.splitlines():
        # "<mode> <type> <sha>\t<path>"
        try:
            meta, path = line.split("\t", 1)
        except ValueError:
            continue
        if not path.endswith(".txt"):
            continue
        parts = meta.split()
        if len(parts) != 3:
            continue
        out.append((path, parts[2]))
    out.sort(key=lambda t: t[0])
    return out


def stream_blobs(corpus_dir: str, blob_shas: list[str]):
    """Yield raw blob bytes in request order via one cat-file --batch process.

    Request/response are interleaved (one write then one read) so neither
    pipe direction ever blocks on a full buffer, regardless of batch size.
    """
    proc = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        cwd=corpus_dir,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    assert proc.stdin is not None and proc.stdout is not None
    out = proc.stdout

    def _read_exactly(n: int) -> bytes:
        chunks: list[bytes] = []
        remaining = n
        while remaining > 0:
            piece = out.read(remaining)
            if not piece:
                raise RuntimeError("unexpected EOF from git cat-file --batch")
            chunks.append(piece)
            remaining -= len(piece)
        return b"".join(chunks)

    for sha in blob_shas:
        proc.stdin.write((sha + "\n").encode("ascii"))
        proc.stdin.flush()
        header = out.readline().decode("ascii").strip()
        # "<sha> <type> <size>" or "<sha> missing"
        parts = header.split()
        if len(parts) == 2 and parts[1] == "missing":
            yield None
            continue
        size = int(parts[2])
        data = _read_exactly(size)
        _read_exactly(1)  # trailing newline
        yield data
    proc.stdin.close()
    proc.wait()


def observe_tokens(text: str) -> dict:
    """Raw token observation (no parser). Returns counters-friendly dict."""
    obs: dict = {
        "topkeys": Counter(),
        "bare_alternate": 0,
        "container_verbs": Counter(),  # (linekind, container, verb)
        "mode_keys": Counter(),  # (linekind, key, value)
        "cost_keys": Counter(),  # key
        "target_keys": Counter(),  # key
        "svar_heads": Counter(),  # head op
        "subrefs": Counter(),  # refkind
        "zone_keys": Counter(),  # key
        "commander_hits": Counter(),
        "multiplayer_hits": Counter(),
        "random_hits": Counter(),
        "copy_control_hits": Counter(),
        "replacement_hits": Counter(),
        "hidden_hits": Counter(),
        "replacement_events": Counter(),  # R-line Event$ values
        "replacement_results": Counter(),  # ReplacementResult$ values
        "replacement_with": Counter(),  # ReplaceWith$ head ops
        "valid_modes": Counter(),  # ValidMode$ referenced modes
        "cost_heads": Counter(),  # Cost$ head tokens
        "commander_damage": 0,  # files mentioning commander damage
        "x_in_manacost": False,
        "x_in_numeric": False,
    }
    lowered = text.lower()
    for sig in _COMMANDER_SIGNALS:
        if sig in text:
            obs["commander_hits"][sig] += 1
    for sig in _MULTIPLAYER_SIGNALS:
        if sig in text:
            obs["multiplayer_hits"][sig] += 1
    for sig in _RANDOM_VARIANTS:
        if sig in lowered:
            obs["random_hits"][sig] += 1
    for sig in _COPY_CONTROL_VARIANTS:
        if sig in text or sig in lowered:
            obs["copy_control_hits"][sig] += 1
    for sig in _REPLACEMENT_SIGNALS:
        if sig in text:
            obs["replacement_hits"][sig] += 1
    for sig in _HIDDEN_SIGNALS:
        if sig in lowered:
            obs["hidden_hits"][sig] += 1
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped == "":
            continue
        if raw.lstrip().startswith("#"):
            continue
        if stripped == "ALTERNATE":
            obs["bare_alternate"] += 1
            continue
        m = _KEYVAL_RE.match(raw)
        if not m:
            obs["topkeys"]["<no-colon>"] += 1
            continue
        key = m.group(1).strip()
        value = m.group(2)
        obs["topkeys"][key if key else "<empty-key>"] += 1
        linekind = key  # A/T/S/R/SVar/K/...
        if key in ("A", "T", "S", "R"):
            for container, verb in _CONTAINER_VERB_RE.findall(value):
                obs["container_verbs"][(linekind, container, verb)] += 1
            for mkey, mval in _MODEKEY_RE.findall(value):
                obs["mode_keys"][(linekind, mkey, mval)] += 1
            for ckey in _COSTKEY_RE.findall(value):
                obs["cost_keys"][ckey] += 1
            for tkey in _TGTKEY_RE.findall(value):
                obs["target_keys"][tkey] += 1
            for zkey, _zval in _ZONEKEY_RE.findall(value):
                obs["zone_keys"][zkey] += 1
            if key == "R":
                for ev in _REPL_EVENT_RE.findall(value):
                    obs["replacement_events"][ev] += 1
                for rr in _REPL_RESULT_RE.findall(value):
                    obs["replacement_results"][rr] += 1
                for rw in _REPL_WITH_RE.findall(value):
                    obs["replacement_with"][rw] += 1
            for vm in _VALIDMODE_RE.findall(value):
                for mode in vm.replace(" ", "").split(","):
                    if mode:
                        obs["valid_modes"][mode] += 1
            for cost_match in re.finditer(r"(?:^|\|)\s*Cost\$\s*([^\|]*)", value):
                head = _COST_HEAD_RE.match(cost_match.group(1).strip())
                obs["cost_heads"][head.group(1) if head else "<symbolic>"] += 1
        elif key == "SVar":
            rest = value
            if ":" in rest:
                _, sval = rest.split(":", 1)
                hm = _SVAR_HEAD_RE.match(sval.strip())
                if hm:
                    obs["svar_heads"][hm.group(1)] += 1
                else:
                    obs["svar_heads"]["<bare-expr>"] += 1
                for refkind, _ref in _SUBREF_RE.findall(sval):
                    obs["subrefs"][refkind] += 1
                for ckey in _COSTKEY_RE.findall(sval):
                    obs["cost_keys"][f"SVar:{ckey}"] += 1
        elif key == "ManaCost":
            if _X_TOKEN_RE.search(value):
                obs["x_in_manacost"] = True
        if key in ("A", "T", "S", "R") and _X_TOKEN_RE.search(value):
            obs["x_in_numeric"] = True
    if any(rx.search(text) for rx in _COMMANDER_DAMAGE_RES):
        obs["commander_damage"] = 1
    return obs


def _top(counter: Counter, n: int) -> list:
    return [[str(k), int(v)] for k, v in counter.most_common(n)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Q6 pinned-corpus read-only inventory")
    ap.add_argument("--corpus-dir", default="/home/moeen/forge-corpus")
    ap.add_argument("--ref", default=FORGE_PIN)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-files", type=int, default=0, help="0 = full corpus")
    ap.add_argument("--parser-version-note", default="")
    args = ap.parse_args(argv)

    # Late import so --help works without the package path fuss.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from q6_scaffolding import Q6_SCAFFOLDING_VERSION
    from q6_scaffolding.classify import classify_card
    from q6_scaffolding.forge_parser import (
        FORGE_PARSER_VERSION,
        extract_features,
        parse_script,
    )
    from q6_scaffolding.skeleton import generate_skeleton, route_state

    # Verify the pin resolves to the expected commit.
    r = _git(args.corpus_dir, "rev-parse", args.ref)
    if r.returncode != 0:
        print(f"inventory: FAIL-CLOSED: cannot resolve ref {args.ref}", file=sys.stderr)
        return 2
    resolved = r.stdout.strip()
    if resolved.lower() != FORGE_PIN.lower():
        print(
            f"inventory: FAIL-CLOSED: ref {args.ref} resolves to {resolved}, "
            f"expected pinned {FORGE_PIN}",
            file=sys.stderr,
        )
        return 2

    files = list_corpus_files(args.corpus_dir, args.ref)
    if args.max_files:
        files = files[: args.max_files]
    total = len(files)

    # Aggregates: TOKEN OBSERVATION layer.
    tok_topkeys: Counter = Counter()
    tok_bare_alternate = 0
    tok_container_verbs: Counter = Counter()
    tok_mode_keys: Counter = Counter()
    tok_cost_keys: Counter = Counter()
    tok_target_keys: Counter = Counter()
    tok_svar_heads: Counter = Counter()
    tok_subrefs: Counter = Counter()
    tok_zone_keys: Counter = Counter()
    tok_commander: Counter = Counter()
    tok_multiplayer: Counter = Counter()
    tok_random: Counter = Counter()
    tok_copy_control: Counter = Counter()
    tok_replacement: Counter = Counter()
    tok_hidden: Counter = Counter()
    tok_repl_events: Counter = Counter()
    tok_repl_results: Counter = Counter()
    tok_repl_with: Counter = Counter()
    tok_valid_modes: Counter = Counter()
    tok_cost_heads: Counter = Counter()
    tok_commander_damage_files = 0
    tok_files_with: Counter = Counter()

    # PARSER INTERPRETATION layer.
    readable = 0
    unreadable = 0
    parsed_ok = 0
    structured = 0
    skeleton_eligible = 0
    ambiguous_files = 0
    unsupported_files = 0
    unsupported_counter: Counter = Counter()
    diag_counter: Counter = Counter()
    unknown_verbs: Counter = Counter()
    unknown_tmodes: Counter = Counter()
    unknown_smodes: Counter = Counter()
    unknown_amodes: Counter = Counter()
    manual_verbs: Counter = Counter()
    layer_verbs: Counter = Counter()
    prevention_verbs: Counter = Counter()
    random_kinds: Counter = Counter()
    x_sources: Counter = Counter()
    observed_verbs: Counter = Counter()
    observed_tmodes: Counter = Counter()
    feat_files_with: Counter = Counter()
    false_positive_probes = 0
    total_params = 0

    # CAPABILITY HYPOTHESIS layer.
    family_files: Counter = Counter()
    routing_states: Counter = Counter()
    routing_reasons: Counter = Counter()
    pretag_kinds: Counter = Counter()

    file_hashes: list[str] = []
    file_count = 0
    batch = 2000
    for start in range(0, total, batch):
        chunk = files[start : start + batch]
        shas = [sha for _, sha in chunk]
        for (path, _sha), data in zip(chunk, stream_blobs(args.corpus_dir, shas), strict=False):
            file_count += 1
            if data is None:
                unreadable += 1
                continue
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                unreadable += 1
                continue
            readable += 1
            file_hashes.append(hashlib.sha256(data).hexdigest())
            obs = observe_tokens(text)
            tok_topkeys.update(obs["topkeys"])
            tok_bare_alternate += obs["bare_alternate"]
            tok_container_verbs.update(obs["container_verbs"])
            tok_mode_keys.update(obs["mode_keys"])
            tok_cost_keys.update(obs["cost_keys"])
            tok_target_keys.update(obs["target_keys"])
            tok_svar_heads.update(obs["svar_heads"])
            tok_subrefs.update(obs["subrefs"])
            tok_zone_keys.update(obs["zone_keys"])
            tok_commander.update(obs["commander_hits"])
            tok_multiplayer.update(obs["multiplayer_hits"])
            tok_random.update(obs["random_hits"])
            tok_copy_control.update(obs["copy_control_hits"])
            tok_replacement.update(obs["replacement_hits"])
            tok_hidden.update(obs["hidden_hits"])
            tok_repl_events.update(obs["replacement_events"])
            tok_repl_results.update(obs["replacement_results"])
            tok_repl_with.update(obs["replacement_with"])
            tok_valid_modes.update(obs["valid_modes"])
            tok_cost_heads.update(obs["cost_heads"])
            tok_commander_damage_files += obs["commander_damage"]
            for layer_key, present in (
                ("tok_commander", bool(obs["commander_hits"])),
                ("tok_multiplayer", bool(obs["multiplayer_hits"])),
                ("tok_random", bool(obs["random_hits"])),
                ("tok_copy_control", bool(obs["copy_control_hits"])),
                ("tok_replacement", bool(obs["replacement_hits"])),
                ("tok_hidden", bool(obs["hidden_hits"])),
                ("tok_x_manacost", bool(obs["x_in_manacost"])),
                ("tok_x_numeric", bool(obs["x_in_numeric"])),
                ("tok_svar", bool(obs["svar_heads"])),
                ("tok_modekey", bool(obs["mode_keys"])),
            ):
                if present:
                    tok_files_with[layer_key] += 1
            try:
                parsed = parse_script(text, path)
                features = extract_features(parsed, text)
                classification = classify_card(f"inventory-{file_count}", features)
                skeleton = generate_skeleton(
                    f"inventory-{file_count}", "", features, classification
                )
                state, reasons = route_state(
                    ambiguous=bool(parsed.get("ambiguous")),
                    unsupported=list(parsed.get("unsupported", [])),
                    features=features,
                    classification=classification,
                    skeleton=skeleton,
                    provenance_complete=True,
                )
            except Exception:
                diag_counter["<inventory-exception>"] += 1
                continue
            blocking = any(
                d.get("code") in ("missing_colon", "svar_missing_name_sep")
                for d in parsed.get("diagnostics", [])
            ) or any(
                d.get("code") in ("missing_colon", "svar_missing_name_sep")
                for line in parsed.get("lines", [])
                if isinstance(line, dict)
                for d in line.get("diagnostics", [])
            )
            if not blocking:
                parsed_ok += 1
            nparams = sum(
                len(line.get("params", []))
                for line in parsed.get("lines", [])
                if isinstance(line, dict) and "params" in line
            )
            total_params += nparams
            if nparams > 0:
                structured += 1
            if path.endswith(".txt") and not blocking:
                skeleton_eligible += 1
            if parsed.get("ambiguous"):
                ambiguous_files += 1
            if parsed.get("unsupported"):
                unsupported_files += 1
                for u in parsed["unsupported"]:
                    unsupported_counter[u] += 1
            for d in parsed.get("diagnostics", []):
                diag_counter[d.get("code", "?")] += 1
            for line in parsed.get("lines", []):
                if isinstance(line, dict):
                    for d in line.get("diagnostics", []):
                        diag_counter[d.get("code", "?")] += 1
            for v in features.get("ability_kinds", []):
                observed_verbs[v] += 1
            for v in features.get("unknown_ability_verbs", []):
                unknown_verbs[v] += 1
            for v in features.get("trigger_modes", []):
                observed_tmodes[v] += 1
            for v in features.get("unknown_trigger_modes", []):
                unknown_tmodes[v] += 1
            for v in features.get("unknown_static_modes", []):
                unknown_smodes[v] += 1
            for v in features.get("unknown_ability_modes", []):
                unknown_amodes[v] += 1
            for v in features.get("manual_review_verbs", []):
                manual_verbs[v] += 1
            for v in features.get("layer_adjudication_verbs", []):
                layer_verbs[v] += 1
            for v in features.get("prevention_adjudication_verbs", []):
                prevention_verbs[v] += 1
            for v in features.get("random_kinds", []):
                random_kinds[v] += 1
            for v in features.get("x_sources", []):
                x_sources[v] += 1
            for feat_key in (
                "has_trigger",
                "has_trigger_condition",
                "has_replacement",
                "has_static",
                "has_ability",
                "has_svar",
                "has_keyword",
                "has_targets",
                "has_choices",
                "has_modes",
                "has_modal_choice",
                "has_combat",
                "has_mana_cost",
                "has_additional_cost",
                "has_alternative_cost",
                "has_x_value",
                "has_hidden",
                "has_random",
                "has_copy_control",
                "has_multiplayer",
                "has_commander",
                "nested_svar",
            ):
                if features.get(feat_key):
                    feat_files_with[feat_key] += 1
            if features.get("has_shuffle"):
                feat_files_with["has_shuffle"] += 1
            if features.get("has_ability") and not (
                features.get("has_mana_cost")
                or features.get("has_targets")
                or features.get("has_choices")
            ):
                false_positive_probes += 1
            for fam in classification.capability_families:
                family_files[fam] += 1
            routing_states[state.value] += 1
            for rsn in reasons:
                routing_reasons[rsn] += 1
            for tag in classification.expected_decision_pretags:
                pretag_kinds[tag["kind"]] += 1
        print(f"inventory: {min(start + batch, total)}/{total}", flush=True)

    file_hashes.sort()
    inventory_hash = hashlib.sha256("".join(file_hashes).encode()).hexdigest()

    def rate(n: int, d: int) -> float:
        return (n / d) if d else 0.0

    doc = {
        "schema": "q6.corpus-inventory.v1",
        "provenance": {
            "source_corpus": "forge-card-scripts",
            "source_repository": FORGE_REMOTE,
            "source_commit": FORGE_PIN,
            "resolved_ref": resolved,
            "cards_prefix": CARDS_PREFIX,
            "tool_version": Q6_SCAFFOLDING_VERSION,
            "parser_version": FORGE_PARSER_VERSION,
            "note": args.parser_version_note,
        },
        "population": {
            "total_files_inspected": file_count,
            "files_readable": readable,
            "files_unreadable": unreadable,
        },
        "token_observation": {
            "topkeys": _top(tok_topkeys, 100),
            "bare_alternate_separators": tok_bare_alternate,
            "container_verbs": [
                [f"{lk}/{c}/{v}", n] for (lk, c, v), n in tok_container_verbs.most_common(600)
            ],
            "mode_keys": [[f"{lk}/{k}/{v}", n] for (lk, k, v), n in tok_mode_keys.most_common(600)],
            "cost_keys": _top(tok_cost_keys, 100),
            "target_keys": _top(tok_target_keys, 100),
            "svar_heads": _top(tok_svar_heads, 150),
            "subrefs": _top(tok_subrefs, 30),
            "zone_keys": _top(tok_zone_keys, 60),
            "commander_signals": _top(tok_commander, 20),
            "commander_damage_files": tok_commander_damage_files,
            "multiplayer_signals": _top(tok_multiplayer, 40),
            "randomness_variants": _top(tok_random, 20),
            "copy_control_variants": _top(tok_copy_control, 20),
            "replacement_signals": _top(tok_replacement, 20),
            "replacement_events": _top(tok_repl_events, 40),
            "replacement_results": _top(tok_repl_results, 20),
            "replacement_with": _top(tok_repl_with, 40),
            "valid_modes": _top(tok_valid_modes, 120),
            "cost_heads": _top(tok_cost_heads, 80),
            "hidden_signals": _top(tok_hidden, 20),
            "files_with_signal": dict(sorted(tok_files_with.items())),
        },
        "parser_interpretation": {
            "parsed_files": parsed_ok,
            "parse_rate": rate(parsed_ok, readable),
            "structured_files": structured,
            "structured_rate": rate(structured, readable),
            "skeleton_eligible_files": skeleton_eligible,
            "skeleton_eligible_rate": rate(skeleton_eligible, readable),
            "ambiguous_files": ambiguous_files,
            "ambiguity_rate": rate(ambiguous_files, readable),
            "unsupported_files": unsupported_files,
            "unsupported_rate": rate(unsupported_files, readable),
            "unsupported_constructs": _top(unsupported_counter, 60),
            "diagnostics": _top(diag_counter, 40),
            # observed_* = every verb/mode the parser saw (known + unknown);
            # unknown_* = the exact-reporting tripwire subset (not in registry).
            "observed_ability_verbs": _top(observed_verbs, 300),
            "unknown_ability_verbs": _top(unknown_verbs, 300),
            "unknown_verb_distinct": len(unknown_verbs),
            "unknown_verb_files": sum(unknown_verbs.values()),
            "observed_trigger_modes": _top(observed_tmodes, 300),
            "unknown_trigger_modes": _top(unknown_tmodes, 300),
            "unknown_tmode_distinct": len(unknown_tmodes),
            "unknown_static_modes": _top(unknown_smodes, 100),
            "unknown_ability_modes": _top(unknown_amodes, 100),
            "manual_review_verbs": _top(manual_verbs, 100),
            "layer_adjudication_verbs": _top(layer_verbs, 100),
            "prevention_adjudication_verbs": _top(prevention_verbs, 100),
            "random_kinds": _top(random_kinds, 20),
            "x_sources": _top(x_sources, 20),
            "feature_files": dict(sorted(feat_files_with.items())),
            "false_positive_probes": false_positive_probes,
            "total_params": total_params,
        },
        "capability_hypothesis": {
            "family_files": dict(sorted(family_files.items())),
            "routing_states": dict(sorted(routing_states.items())),
            "routing_reasons_top": _top(routing_reasons, 60),
            "pretag_kinds": dict(sorted(pretag_kinds.items())),
        },
        "integrity": {
            "inventory_hash": inventory_hash,
            "disclaimer": (
                "TOKEN OBSERVATION != PARSER INTERPRETATION != CAPABILITY "
                "HYPOTHESIS. Scaffolding metrics only. "
                "No behavior PASS is measured or awarded here. "
                "No behavior credit. No coverage promotion."
            ),
        },
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "files": file_count,
                "readable": readable,
                "parse_rate": round(rate(parsed_ok, readable), 4),
                "unknown_verb_distinct": len(unknown_verbs),
                "unknown_tmode_distinct": len(unknown_tmodes),
                "inventory_hash": inventory_hash[:16],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
