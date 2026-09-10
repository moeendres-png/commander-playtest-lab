"""Clean-room Forge card-script parser (project-authored port).

Ported from the D3 clean-room prototype ``d3q6-cleanroom-0.1.0``
(``research/d3-q6-import-automation/forge_script_parser.py`` at
``moeendres-png/mage@a766f900``), which was written from the public Forge
wiki format description (line-oriented ``Key:Value`` records; ``A:`` /
``T:`` / ``S:`` / ``R:`` / ``SVar:`` / ``K:`` lines; ``$``-delimited param
records) plus direct observation of pinned corpus files.

Port provenance: the D3 prototype is project-authored clean-room code, so
porting its *logic* is permitted by the task contract. No Forge GPL
implementation, Manabrew AGPL implementation, or third-party
implementation body is copied, linked, or embedded here. Token tables were
curated from the public wiki and observed corpus; unknown constructs are
kept as raw/unsupported and never guessed.

Adaptations vs D3: plain-JSON-serializable records (no dataclasses), Q6
parser version stamp, byte-span diagnostics retained, and the output feeds
the Q6 state model instead of the D3 experiment summary.

PARSE/IMPORT != BEHAVIOR PASS: parser success never promotes a behavior
row. The parser emits features, diagnostics, and pre-tags only.
"""

from __future__ import annotations

import hashlib
import re

FORGE_PARSER_VERSION = "q6-forge-parser-0.1.0"

# Top-level keys described by the public Forge wiki format plus corpus
# observation. Anything else is recorded as unsupported (fail-closed into
# review), never silently accepted.
#
# ``AI`` is allowlisted as benign deck-hint metadata (D3 decomposition:
# ``topkey:AI`` hint lines carry no game semantics; the real semantic gaps
# live one layer deeper in ability verbs and trigger modes).
KNOWN_TOP_KEYS = frozenset(
    {
        "Name",
        "ManaCost",
        "Colors",
        "Types",
        "PT",
        "Loyalty",
        "Defense",
        "K",
        "A",
        "T",
        "S",
        "R",
        "SVar",
        "Oracle",
        "Text",
        "AlternateMode",
        "ALTERNATE",
        "SPECIALIZE",
        "Variant",
        "DeckHints",
        "DeckHas",
        "DeckNeeds",
        "DeckShuffles",
        "RemAIDeck",
        "RemRandomDeck",
        "Commander",
        "MustBlock",
        "MustAttack",
        "ETB",
        "Flashback",
        "Madness",
        "Bestow",
        "Cipher",
        "SoundEffect",
        "AI",
    }
)

ABILITY_LINE_KINDS = {"A": "Ability", "T": "Trigger", "S": "Static", "R": "Replacement"}

# Minimal verb vocabulary from public wiki examples. Unknown verbs stay
# Raw/unsupported; the classifier routes them to manual review.
KNOWN_ABILITY_KINDS = frozenset(
    {
        "DealDamage",
        "Draw",
        "Destroy",
        "Exile",
        "Pump",
        "Token",
        "Sacrifice",
        "GainLife",
        "LoseLife",
        "Counters",
        "PutCounter",
        "RemoveCounter",
        "Discard",
        "Mulligan",
        "SearchLibrary",
        "ChangeZone",
        "Branch",
        "ChooseCard",
        "ChoosePlayer",
        "ChooseType",
        "ChooseNumber",
        "ChooseSource",
        "FlipACoin",
        "RollDice",
        "Shuffle",
        "Scry",
        "Surveil",
        "Investigate",
        "Play",
        "Copy",
        "GainControl",
        "Attach",
        "Untap",
        "Tap",
        "Regenerate",
        "PreventDamage",
        "Protection",
        "Effect",
        "Animate",
        "Repeat",
        "RepeatEach",
        "DelayedTrigger",
        "TwoPiles",
        "Clash",
        "Cleanup",
        "Mana",
        "Charm",
        "Dig",
        "ChangeZoneAll",
        "PumpAll",
        "Counter",
        "Mill",
        "Vote",
        "Meld",
        "SacrificeAll",
    }
)

KNOWN_TRIGGER_MODES = frozenset(
    {
        "ChangesZone",
        "DamageDone",
        "DamageDealt",
        "SpellCast",
        "AbilityCast",
        "Phase",
        "Drawn",
        "Discarded",
        "Sacrificed",
        "LifeGained",
        "LifeLost",
        "CounterAdded",
        "CounterRemoved",
        "AttackersDeclared",
        "BlockersDeclared",
        "TurnFaceUp",
        "TurnFaceDown",
        "Taps",
        "Untaps",
        "ChangesController",
        "LandPlayed",
        "Cycled",
        "Storm",
        "ETBReplacement",
        "Attacks",
        "Blocks",
        "Always",
    }
)

_PARAM_SPLIT_RE = re.compile(r"\s*\|\s*")
_KEYVAL_RE = re.compile(r"^([^:]*):(.*)$", re.DOTALL)
_X_TOKEN_RE = re.compile(r"(?<![A-Za-z])X(?![A-Za-z])")

# Param keys whose standalone-X value denotes a controller-chosen X value
# (Fireball-style). Internal SVar cross-references (ConditionCheckSVar$ X)
# and SVar *names* never count: only real numeric slots on ability records.
NUMERIC_X_PARAM_KEYS = frozenset({"numdmg", "amount", "lifeamount", "numcards", "x", "value"})
_SVAR_REF_RE = re.compile(
    r"(Execute|TrueSubAbility|FalseSubAbility|SubAbility|Remembered|Imprinted)"
    r"\$\s*([A-Za-z0-9_]+)"
)


def classify_semantic(key: str, value: str) -> str:
    """Heuristic semantic typing by key-name pattern. Raw is the fallback."""
    k = key.lower()
    v = value.strip()
    if not v:
        return "empty"
    if k.startswith("defined"):
        return "defined_ref"
    if "valid" in k and ("tgt" in k or "card" in k or "player" in k or "target" in k):
        return "selector"
    if k.startswith("num") or k in ("amount", "counternum", "lifegain", "lifeloss"):
        return "amount"
    if k in ("cost", "manacost", "playcost"):
        return "cost"
    if "produced" in k or "combo" in k:
        return "produced_mana"
    if "svarcompare" in k or "checksvar" in k or k.startswith("branchcondition"):
        return "comparison"
    if "zone" in k or k in ("origin", "destination"):
        return "zone_list"
    if k in (
        "execute",
        "truesubability",
        "falsesubability",
        "subability",
        "remembered",
        "imprinted",
    ):
        return "svar_ref"
    if k in ("mode", "triggermode"):
        return "trigger_mode"
    if k in ("oracle", "triggerdescription", "spelldescription", "stackdescription"):
        return "rules_text"
    if re.fullmatch(r"[0-9Xx*/+\-. ]+", v):
        return "numeric_expr"
    if v.startswith("Count$") or v.startswith("SVar$") or "Triggered" in v:
        return "computed_expr"
    return "raw"


def _diag(code: str, message: str, line_no: int, span: list) -> dict:
    return {"code": code, "message": message, "line_no": line_no, "span": list(span)}


def parse_script(text: str, path: str = "<memory>") -> dict:
    """Parse one Forge card script into a JSON-serializable record.

    The parser never throws on malformed input: every anomaly becomes a
    diagnostic (and, where it blocks interpretation, an ambiguity flag).
    """
    lines: list = []
    diagnostics: list = []
    unsupported: list = []
    ambiguous = False
    raw_lines = text.splitlines()
    offset = 0
    for idx, raw in enumerate(raw_lines, start=1):
        span = [offset, offset + len(raw)]
        offset += len(raw) + 1
        stripped = raw.strip()
        if stripped == "":
            lines.append({"kind": "Blank", "line_no": idx, "span": span})
            continue
        if raw.lstrip().startswith("#"):
            lines.append({"kind": "Comment", "line_no": idx, "span": span})
            continue
        if stripped == "ALTERNATE":
            # Bare multi-face separator (no colon): documented format feature
            # for double-faced/modal scripts, observed in pinned corpus files.
            lines.append(
                {
                    "kind": "Face",
                    "key": "ALTERNATE",
                    "value": "",
                    "line_no": idx,
                    "span": span,
                }
            )
            continue
        match = _KEYVAL_RE.match(raw)
        if not match:
            diagnostics.append(_diag("missing_colon", "line has no ':' separator", idx, span))
            ambiguous = True
            lines.append({"kind": "Unknown", "line_no": idx, "span": span, "raw": raw})
            continue
        key, value = match.group(1).strip(), match.group(2)
        if key == "":
            diagnostics.append(_diag("empty_key", "empty key before ':'", idx, span))
            ambiguous = True
        if key in ("ALTERNATE", "AlternateMode", "SPECIALIZE"):
            lines.append(
                {
                    "kind": "Face",
                    "key": key,
                    "value": value.strip(),
                    "line_no": idx,
                    "span": span,
                }
            )
            continue
        if key not in KNOWN_TOP_KEYS and not key.startswith("Variant"):
            unsupported.append(f"topkey:{key}")
            diagnostics.append(
                _diag(
                    "unknown_topkey",
                    f"unrecognized top-level key {key!r}",
                    idx,
                    span,
                )
            )
        if key in ABILITY_LINE_KINDS:
            record: dict = {
                "kind": ABILITY_LINE_KINDS[key],
                "header": value.strip(),
                "params": [],
                "diagnostics": [],
                "line_no": idx,
            }
            if "$" not in value:
                record["diagnostics"].append(
                    _diag(
                        "missing_ability_record",
                        f"{key}: line has no '$' record",
                        idx,
                        span,
                    )
                )
                ambiguous = True
            else:
                for part in _PARAM_SPLIT_RE.split(value.strip()):
                    if "$" not in part:
                        record["diagnostics"].append(
                            _diag(
                                "missing_dollar",
                                f"param segment without '$': {part!r}",
                                idx,
                                span,
                            )
                        )
                        ambiguous = True
                        continue
                    param_key, param_val = part.split("$", 1)
                    param_key, param_val = param_key.strip(), param_val.strip()
                    if param_key == "":
                        record["diagnostics"].append(
                            _diag("empty_param_key", "empty param key", idx, span)
                        )
                        ambiguous = True
                    record["params"].append(
                        {
                            "key": param_key,
                            "raw": param_val,
                            "semantic": classify_semantic(param_key, param_val),
                            "span": list(span),
                        }
                    )
                keys = [p["key"] for p in record["params"]]
                if len(keys) != len(set(keys)):
                    record["diagnostics"].append(
                        _diag("duplicate_param", "duplicate param keys", idx, span)
                    )
                    ambiguous = True
            lines.append(record)
        elif key == "SVar":
            rest = value
            if ":" not in rest:
                diagnostics.append(
                    _diag(
                        "svar_missing_name_sep",
                        "SVar without name ':' separator",
                        idx,
                        span,
                    )
                )
                ambiguous = True
                lines.append(
                    {
                        "kind": "SVar",
                        "name": rest.strip(),
                        "value": "",
                        "line_no": idx,
                        "span": span,
                        "params": [],
                    }
                )
                continue
            name, sval = rest.split(":", 1)
            name, sval = name.strip(), sval.strip()
            params: list = []
            if "$" in sval:
                for part in _PARAM_SPLIT_RE.split(sval):
                    if "$" not in part:
                        params.append(
                            {
                                "key": "",
                                "raw": part.strip(),
                                "semantic": classify_semantic("", part),
                                "span": list(span),
                            }
                        )
                        continue
                    param_key, param_val = part.split("$", 1)
                    params.append(
                        {
                            "key": param_key.strip(),
                            "raw": param_val.strip(),
                            "semantic": classify_semantic(param_key.strip(), param_val.strip()),
                            "span": list(span),
                        }
                    )
            lines.append(
                {
                    "kind": "SVar",
                    "name": name,
                    "value": sval,
                    "line_no": idx,
                    "span": span,
                    "params": params,
                }
            )
        elif key == "K":
            lines.append({"kind": "Keyword", "value": value.strip(), "line_no": idx, "span": span})
        else:
            lines.append(
                {
                    "kind": "Field",
                    "key": key,
                    "value": value.strip(),
                    "line_no": idx,
                    "span": span,
                }
            )
    return {
        "path": path,
        "parser_version": FORGE_PARSER_VERSION,
        "lines": lines,
        "diagnostics": diagnostics,
        "unsupported": sorted(set(unsupported)),
        "ambiguous": ambiguous,
        "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def extract_features(parsed: dict, text: str) -> dict:
    """Derive boolean/shape features from a parsed script (no judgments)."""
    feats: dict = {
        "has_trigger": False,
        "has_replacement": False,
        "has_static": False,
        "has_ability": False,
        "has_svar": False,
        "has_keyword": False,
        "svar_names": [],
        "svar_edge_count": 0,
        "max_svar_depth": 0,
        "nested_svar": False,
        "has_targets": False,
        "has_choices": False,
        "has_modes": False,
        "has_modal_choice": False,
        "has_mana_cost": False,
        "has_additional_cost": False,
        "has_alternative_cost": False,
        "has_x_value": False,
        "has_hidden": False,
        "has_random": False,
        "has_copy_control": False,
        "has_multiplayer": False,
        "has_commander": False,
        "ability_kinds": [],
        "trigger_modes": [],
        "unknown_ability_verbs": [],
        "unknown_trigger_modes": [],
    }
    svar_map: dict[str, str] = {}
    for line in parsed["lines"]:
        if not isinstance(line, dict):
            continue
        kind = line.get("kind")
        if kind == "Face":
            # Modal double-face marker (AlternateMode:Modal shape): the card
            # offers a face/mode choice at runtime.
            if "Modal" in str(line.get("value", "")):
                feats["has_modes"] = True
                feats["has_choices"] = True
                feats["has_modal_choice"] = True
            continue
        if kind in ("Ability", "Trigger", "Static", "Replacement"):
            if kind == "Ability":
                feats["has_ability"] = True
            elif kind == "Trigger":
                feats["has_trigger"] = True
            elif kind == "Static":
                feats["has_static"] = True
            else:
                feats["has_replacement"] = True
            for param in line.get("params", []):
                pkey = param.get("key", "")
                praw = param.get("raw", "")
                klow = pkey.lower()
                if "tgt" in klow or "validtgts" in klow or "targetmin" in klow:
                    feats["has_targets"] = True
                if (
                    "mode" in klow
                    or "choice" in klow
                    or "choose" in klow
                    or "optional" in klow
                    or "vote" in klow
                ):
                    feats["has_choices"] = True
                    if "mode" in klow:
                        feats["has_modes"] = True
                        if kind == "Ability":
                            # Modal choice on a spell/ability (Charm shape).
                            # Static/Trigger Mode$ lines are effect/trigger
                            # modes, not modal choices.
                            feats["has_modal_choice"] = True
                if pkey in ("Mode", "Mode$"):
                    if kind == "Trigger":
                        feats["trigger_modes"].append(praw)
                        if praw not in KNOWN_TRIGGER_MODES:
                            feats["unknown_trigger_modes"].append(praw)
                    elif kind == "Static" and praw == "AlternativeCost":
                        # Static alternative-cost mode (Force of Will shape):
                        # a payment choice, not a trigger mode.
                        feats["has_alternative_cost"] = True
                if pkey in ("SP", "AB", "DB"):
                    feats["ability_kinds"].append(praw)
                    if praw not in KNOWN_ABILITY_KINDS:
                        feats["unknown_ability_verbs"].append(praw)
                    if praw == "Charm":
                        feats["has_modal_choice"] = True
                if klow in ("cost",) or "additionalcost" in klow or "unlesscost" in klow:
                    feats["has_additional_cost"] = True
                if "alternative" in klow or "maybecost" in klow or "unlesscost" in klow:
                    feats["has_alternative_cost"] = True
                if klow in NUMERIC_X_PARAM_KEYS and _X_TOKEN_RE.search(praw):
                    feats["has_x_value"] = True
        elif kind == "SVar":
            feats["has_svar"] = True
            feats["svar_names"].append(line.get("name", ""))
            svar_map[line.get("name", "")] = line.get("value", "")
        elif kind == "Keyword":
            feats["has_keyword"] = True
        elif kind == "Field":
            fkey = line.get("key", "")
            fval = line.get("value", "")
            if fkey == "ManaCost" and fval.strip() not in ("", "no cost"):
                feats["has_mana_cost"] = True
                if _X_TOKEN_RE.search(fval):
                    feats["has_x_value"] = True
            if fkey in ("Commander",):
                feats["has_commander"] = True
    lowered = text.lower()
    if any(
        s in lowered
        for s in (
            "facedown",
            "face down",
            "look at",
            "reveal",
            "manifest",
            "morph",
            "disguise",
            "cloak",
        )
    ):
        feats["has_hidden"] = True
    # Strong randomness signals (Rules randomness). Plain "shuffle" (tutor
    # shuffle) is recorded separately: it needs no RNG-attribution question.
    # Word boundaries avoid false hits (e.g. "troll" is not a die roll).
    if re.search(r"\b(flip a coin|flip|rolls?|dice|die|random|coin)\b", lowered):
        feats["has_random"] = True
    if "shuffle" in lowered:
        feats["has_shuffle"] = True
    if any(
        s in lowered
        for s in ("copy", "gaincontrol", "gain control", "attach", "exchange", "control of", "meld")
    ):
        feats["has_copy_control"] = True
    if any(
        s in lowered
        for s in (
            "each player",
            "each opponent",
            "each other",
            "vote",
            "will of the council",
            "monarch",
            "council",
        )
    ):
        feats["has_multiplayer"] = True
    if any(
        s in text
        for s in (
            "commander",
            "Commander",
            "command zone",
            "CommandZone",
            "commander tax",
            "partner",
        )
    ):
        feats["has_commander"] = True
    edges: dict[str, list] = {name: _SVAR_REF_RE.findall(value) for name, value in svar_map.items()}
    feats["svar_edge_count"] = sum(len(v) for v in edges.values())

    def depth(name: str, seen: frozenset) -> int:
        if name in seen or name not in edges:
            return 0
        seen = seen | {name}
        kids = [target for _, target in edges[name] if target in svar_map]
        if not kids:
            return 1 if edges[name] else 0
        return 1 + max((depth(kid, seen) for kid in kids), default=0)

    feats["max_svar_depth"] = max((depth(n, frozenset()) for n in svar_map), default=0)
    feats["nested_svar"] = feats["max_svar_depth"] >= 2 or feats["svar_edge_count"] >= 2
    feats["ability_kinds"] = sorted(set(feats["ability_kinds"]))
    feats["trigger_modes"] = sorted(set(feats["trigger_modes"]))
    feats["unknown_ability_verbs"] = sorted(set(feats["unknown_ability_verbs"]))
    feats["unknown_trigger_modes"] = sorted(set(feats["unknown_trigger_modes"]))
    feats["diagnostic_count"] = len(parsed["diagnostics"]) + sum(
        len(line.get("diagnostics", [])) for line in parsed["lines"] if isinstance(line, dict)
    )
    feats["unsupported_count"] = len(parsed["unsupported"])
    return feats
