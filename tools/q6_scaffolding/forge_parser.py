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

Task-2B industrialization: the brittle hand-maintained verb/mode frozensets
are now projections of the versioned, provenance-bearing registries in
:mod:`registries` (``verb_registry.json``, ``trigger_mode_registry.json``,
``static_mode_registry.json``). Recognition is generic by grammar
construct, never by card name. Unknown tokens stay exactly reported with
no catch-all "supported" fallback and no silent coercion.

PARSE/IMPORT != BEHAVIOR PASS: parser success never promotes a behavior
row. The parser emits features, diagnostics, and pre-tags only. Shapes
(``DAMAGE_SHAPE``, ``TOKEN_SHAPE``, ...) name mechanical structure only;
no Rules outcome is inferred from any label.
"""

from __future__ import annotations

import hashlib
import re

from .registries import (
    ability_mode_class,
    is_known_trigger_mode,
    static_mode_class,
    static_mode_registry,
    trigger_mode_registry,
    verb_registry,
    verb_shape,
)

FORGE_PARSER_VERSION = "q6-forge-parser-0.2.0"

# Top-level keys described by the public Forge wiki format plus corpus
# observation. Anything else is recorded as unsupported (fail-closed into
# review), never silently accepted.
#
# ``AI`` is allowlisted as benign deck-hint metadata (D3 decomposition:
# ``topkey:AI`` hint lines carry no game semantics; the real semantic gaps
# live one layer deeper in ability verbs and trigger modes).
# ``ODeckHints`` shares the ``DeckHints`` hint shape (single-file variant
# spelling, verified hint-like content).
# ``DBCleanup`` is an SVar-like ``DB$ Cleanup`` record (sub-ability
# cleanup step), parsed generically, not a game directive.
# ``CopyFaceFrom`` is a split-face copy marker (face-class record).
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
        "DBCleanup",
        "Oracle",
        "Text",
        "AlternateMode",
        "CopyFaceFrom",
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
        "ODeckHints",
    }
)

ABILITY_LINE_KINDS = {"A": "Ability", "T": "Trigger", "S": "Static", "R": "Replacement"}

# Ability containers: SP (spell), AB (activated), DB (triggered/delayed
# sub-ability body), ST (static ability; 1 census file, Circling Vultures).
ABILITY_CONTAINERS = ("SP", "AB", "DB", "ST")


def _registry_verbs() -> frozenset:
    return frozenset(verb_registry().get("verbs", {}))


def _registry_tmodes() -> frozenset:
    return frozenset(trigger_mode_registry().get("modes", {}))


# Registry projections (kept as module names for test/debug readability;
# authoritative content lives in the JSON registries).
KNOWN_ABILITY_KINDS = _registry_verbs()
KNOWN_TRIGGER_MODES = _registry_tmodes()

_PARAM_SPLIT_RE = re.compile(r"\s*\|\s*")
_KEYVAL_RE = re.compile(r"^([^:]*):(.*)$", re.DOTALL)
_X_TOKEN_RE = re.compile(r"(?<![A-Za-z])X(?![A-Za-z])")
_VERB_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

# Param keys whose standalone-X value denotes a controller-chosen X value
# (Fireball-style). Internal SVar cross-references (ConditionCheckSVar$ X)
# and SVar *names* never count: only real numeric slots on ability records.
NUMERIC_X_PARAM_KEYS = frozenset({"numdmg", "amount", "lifeamount", "numcards", "x", "value"})
_SVAR_REF_RE = re.compile(
    r"(Execute|TrueSubAbility|FalseSubAbility|SubAbility|Remembered|Imprinted)"
    r"\$\s*([A-Za-z0-9_]+)"
)
_X_CONDITION_RE = re.compile(r"(?:BranchConditionSVar|ConditionCheckSVar)\$\s*X(?![A-Za-z0-9_])")

# Multiplayer mechanical signals: multi-word phrases match by substring;
# single words match on word boundaries only (``devoted``/``steam`` must
# not read as voting/teams).
_MULTIPLAYER_PHRASES = (
    "each player",
    "each opponent",
    "each other",
    "target opponent",
    "chosen opponent",
    "will of the council",
    "starting with you",
    "attack each",
    "attack a different",
)
_MULTIPLAYER_WORD_RE = re.compile(
    r"\b(vote|votes|voting|monarch|council|team|shared)\b", re.IGNORECASE
)

# Commander mechanical signals (specific enough for substring matching).
_COMMANDER_SIGNALS = (
    "commander",
    "Commander",
    "command zone",
    "CommandZone",
    "commander tax",
    "partner",
)

# Randomness taxonomy signals. Bare ``die``/``roll``/``flip`` are NOT
# matched alone (``would die``, ``troll``, ``flip CARDNAME`` are not
# randomness). Shuffle is recorded separately and never implies
# discretionary randomness.
_SHUFFLE_RE = re.compile(r"\bshuffles?\b|\bshuffled\b", re.IGNORECASE)
_COIN_RE = re.compile(r"\bflips?\s+a\s+coin\b|\bcoin\s+flip\b|\btoss\s+a\s+coin\b", re.IGNORECASE)
_COIN_WORD_RE = re.compile(r"\bcoin\b", re.IGNORECASE)
_FLIP_WORD_RE = re.compile(r"\bflips?\b", re.IGNORECASE)
_DIE_RE = re.compile(
    r"\bdice\b|\bdie\s+rolls?\b|\brolls?\s+a\s+d(ie|ice)\b|\bplanar\s+dice\b",
    re.IGNORECASE,
)
_RANDOM_RE = re.compile(r"\brandom\b", re.IGNORECASE)
_AT_RANDOM_RE = re.compile(r"\bat\s+random\b", re.IGNORECASE)

# Copy/control mechanical signals (observation layer). ``clone`` is matched
# via the Clone verb shape, not substring (``cyclone`` is not a copy).
# ``exchange`` alone is not matched (life-total exchanges are not
# copy/control layers); control exchanges match ``exchange control`` or the
# registered Exchange verbs.
_COPY_CONTROL_SIGNALS = (
    "copy",
    "gaincontrol",
    "gain control",
    "attach",
    "exchange control",
    "control of",
    "meld",
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

# SVar fragment heads that denote computed/reference values (state-defined
# variables, counters of game objects, remembered selections).
_COMPUTED_SVAR_HEADS = frozenset(
    {
        "Count",
        "SVar",
        "Number",
        "TriggerCount",
        "ReplaceCount",
        "PlayerCount",
        "PlayerCountOther",
        "PlayerCountPlayers",
        "PlayerCountOpponents",
        "PlayerCountPropertyYou",
        "PlayerCountRemembered",
        "PlayerCountRememberedController",
        "PlayerCountRegisteredOpponents",
        "PlayerCountDefinedRememberedOwner",
        "PlayerCountDefinedNonTriggeredTarget",
        "TriggeredCard",
        "TriggeredCardController",
        "TriggeredPlayer",
        "TriggeredTarget",
        "TriggeredAttacker",
        "TriggeredBlocker",
        "TriggeredDefendingPlayer",
        "TriggeredSource",
        "TriggeredSpellAbility",
        "Targeted",
        "TargetedPlayer",
        "TargetedController",
        "TargetedObjects",
        "ParentTargeted",
        "Remembered",
        "RememberedLKI",
        "Imprinted",
        "TriggerRemembered",
        "Sacrificed",
        "Discarded",
        "Exiled",
        "ExiledWith",
        "Revealed",
        "ThisTurn",
        "Enchanted",
        "Equipped",
        "Tapped",
        "ChosenCard",
        "ReplacedSource",
        "TriggerObjectsAttackers",
        "TriggerObjectsCards",
        "DungeonsCompleted",
        "ManaFrom",
        "CreatureEvalThreshold",
        "NeverCastIfLifeBelow",
        "SpellTargeted",
    }
)
_COST_SVAR_HEADS = frozenset({"SacCost", "DiscardCost"})


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
        if key in ("ALTERNATE", "AlternateMode", "SPECIALIZE", "CopyFaceFrom"):
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
        elif key in ("SVar", "DBCleanup"):
            rest = value
            if ":" not in rest:
                diagnostics.append(
                    _diag(
                        "svar_missing_name_sep",
                        f"{key} without name ':' separator",
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


def _svar_fragment_kind(name: str, value: str) -> str:
    """Mechanically classify one SVar block by its head token.

    EFFECT_FRAGMENT (``DB$``/``AB$``/``SP$`` bodies), STATIC_FRAGMENT and
    TRIGGER_FRAGMENT (``Mode$`` blocks whose mode is registered as a static
    or trigger mode), COMPUTED_FRAGMENT (state-defined/reference values),
    COST_FRAGMENT (cost definitions), else OTHER_FRAGMENT. Referenced (not
    chained) sub-abilities are distinguished from chained ones by the
    caller via ``SubAbility``/``Execute`` edge analysis.
    """
    head_match = re.match(r"^\s*([A-Za-z0-9_]+)\$", value)
    if not head_match:
        return "OTHER_FRAGMENT"
    head = head_match.group(1)
    if head in ("DB", "AB", "SP"):
        return "EFFECT_FRAGMENT"
    if head in _COST_SVAR_HEADS:
        return "COST_FRAGMENT"
    if head in _COMPUTED_SVAR_HEADS:
        return "COMPUTED_FRAGMENT"
    if head == "Mode":
        mode_match = re.match(r"^\s*Mode\$\s*([A-Za-z0-9_]+)", value)
        mode = mode_match.group(1) if mode_match else ""
        if static_mode_class("S", mode) is not None:
            return "STATIC_FRAGMENT"
        if is_known_trigger_mode(mode):
            return "TRIGGER_FRAGMENT"
        return "REFERENCED_OTHER_FRAGMENT"
    if head == "SVar":
        return "COMPUTED_FRAGMENT"
    return "OTHER_FRAGMENT"


def _random_kinds(text: str, features: dict, ability_text: str) -> list[str]:
    """Mechanically distinguish randomness variants (classification only).

    SHUFFLE (library shuffle operation) never implies discretionary
    randomness. Coin flip, die roll, random discard, random selection, and
    otherwise-unclassified random-like constructs are separated so the
    RNG-attribution question fires only for genuine Rules randomness.
    """
    lowered = text.lower()
    kinds: set[str] = set()
    if _SHUFFLE_RE.search(lowered):
        kinds.add("SHUFFLE")
    coin_verb = any(
        shape == "RANDOM_SHAPE" and ("Coin" in verb or "Flip" in verb)
        for verb, shape in features.get("_verb_shapes", [])
    )
    die_verb = any(
        shape == "RANDOM_SHAPE" and ("Dice" in verb or "Die" in verb or "Roll" in verb)
        for verb, shape in features.get("_verb_shapes", [])
    )
    if (
        _COIN_RE.search(lowered)
        or coin_verb
        or (_FLIP_WORD_RE.search(lowered) and _COIN_WORD_RE.search(lowered))
    ):
        kinds.add("COIN_FLIP")
    if _DIE_RE.search(lowered) or die_verb:
        kinds.add("DIE_ROLL")
    random_word = bool(_RANDOM_RE.search(lowered))
    seek_flag = "RANDOMNESS" in features.get("_shape_flags", []) and any(
        verb == "Seek" for verb, _ in features.get("_verb_shapes", [])
    )
    discard_context = "DISCARD_SHAPE" in features.get("_verb_shape_set", set()) or bool(
        re.search(r"\bdiscards?\b", lowered)
    )
    if "RANDOMNESS_SELECTOR" in features.get("ability_mode_classes", []) or seek_flag:
        kinds.add("RANDOM_SELECT")
    if random_word and discard_context:
        kinds.add("RANDOM_DISCARD")
    if _AT_RANDOM_RE.search(lowered) and not discard_context:
        kinds.add("RANDOM_SELECT")
    if "RANDOMNESS" in features.get("_shape_flags", []) and not (
        coin_verb or die_verb or seek_flag
    ):
        kinds.add("RANDOM_SELECT")
    if random_word and not (kinds - {"SHUFFLE"}):
        # Bare random-like wording with no coin/die/discard/select evidence.
        kinds.add("RANDOM_UNKNOWN")
    _ = ability_text
    return sorted(kinds)


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
        "svar_fragment_kinds": {},
        "has_targets": False,
        "has_choices": False,
        "has_modes": False,
        "has_modal_choice": False,
        "has_trigger_condition": False,
        "has_combat": False,
        "has_mana_cost": False,
        "has_additional_cost": False,
        "has_alternative_cost": False,
        "has_x_value": False,
        "x_sources": [],
        "has_hidden": False,
        "has_random": False,
        "has_shuffle": False,
        "random_kinds": [],
        "has_copy_control": False,
        "has_multiplayer": False,
        "multiplayer_signals": [],
        "has_commander": False,
        "ability_kinds": [],
        "verb_shapes": [],
        "trigger_modes": [],
        "static_mode_classes": [],
        "ability_mode_classes": [],
        "unknown_ability_verbs": [],
        "unknown_trigger_modes": [],
        "unknown_static_modes": [],
        "unknown_ability_modes": [],
        "manual_review_verbs": [],
        "layer_adjudication_verbs": [],
        "prevention_adjudication_verbs": [],
    }
    verb_shapes: list[tuple[str, str]] = []  # (verb, shape), internal
    shape_flags: set[str] = set()
    verb_shape_set: set[str] = set()
    svar_map: dict[str, str] = {}
    ability_mode_classes: set[str] = set()
    static_mode_classes: set[str] = set()
    modal_meta_key = set(static_mode_registry().get("modal_meta_keys", []))
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
                if pkey in modal_meta_key:
                    # Modal-meta structure (CanRepeatModes$ True on Charms):
                    # a genuine modal-choice signal, not an effect modifier.
                    feats["has_modes"] = True
                    feats["has_choices"] = True
                    feats["has_modal_choice"] = True
                if pkey in ("Mode", "Mode$"):
                    if kind == "Trigger":
                        feats["trigger_modes"].append(praw)
                        if not is_known_trigger_mode(praw):
                            feats["unknown_trigger_modes"].append(praw)
                    elif kind == "Static":
                        cls = static_mode_class("S", praw)
                        if cls is None:
                            feats["unknown_static_modes"].append(praw)
                        else:
                            static_mode_classes.add(cls)
                            if cls == "STATIC_COST_CHOICE":
                                # Static alternative/optional-cost mode
                                # (Force of Will shape): a payment choice.
                                feats["has_alternative_cost"] = True
                            elif cls == "STATIC_COMBAT":
                                feats["has_combat"] = True
                    elif kind == "Ability":
                        cls = ability_mode_class(praw)
                        if cls is None:
                            feats["unknown_ability_modes"].append(praw)
                        else:
                            ability_mode_classes.add(cls)
                            if cls == "MODAL_META":
                                feats["has_modal_choice"] = True
                            elif cls == "TRIGGER_CONDITION":
                                # Ability-carried trigger condition
                                # (Adaptive Training Post DelayedTrigger
                                # shape): a trigger will exist at runtime,
                                # but this is not a modal choice.
                                feats["has_trigger_condition"] = True
                            elif cls == "RANDOMNESS_SELECTOR":
                                shape_flags.add("RANDOMNESS")
                if pkey in ABILITY_CONTAINERS:
                    if pkey == "ST":
                        # Static ability carried on an A: line (Circling
                        # Vultures shape): static, not modal.
                        feats["has_static"] = True
                    if _VERB_TOKEN_RE.match(praw):
                        feats["ability_kinds"].append(praw)
                        shape, flags = verb_shape(praw)
                        if shape is None:
                            feats["unknown_ability_verbs"].append(praw)
                        else:
                            verb_shapes.append((praw, shape))
                            verb_shape_set.add(shape)
                            shape_flags.update(flags)
                            if "MANUAL_REVIEW" in flags:
                                feats["manual_review_verbs"].append(praw)
                            if "LAYER_ADJUDICATION" in flags:
                                feats["layer_adjudication_verbs"].append(praw)
                            if "PREVENTION_ADJUDICATION" in flags:
                                feats["prevention_adjudication_verbs"].append(praw)
                            if shape == "MODAL_SHAPE":
                                feats["has_modal_choice"] = True
                    if praw == "Charm":
                        feats["has_modal_choice"] = True
                if klow in ("cost",) or "additionalcost" in klow or "unlesscost" in klow:
                    feats["has_additional_cost"] = True
                if "alternative" in klow or "maybecost" in klow or "unlesscost" in klow:
                    feats["has_alternative_cost"] = True
                if klow in NUMERIC_X_PARAM_KEYS and _X_TOKEN_RE.search(praw):
                    feats["has_x_value"] = True
                    if "NUMERIC_X" not in feats["x_sources"]:
                        feats["x_sources"].append("NUMERIC_X")
        elif kind == "SVar":
            feats["has_svar"] = True
            feats["svar_names"].append(line.get("name", ""))
            svar_map[line.get("name", "")] = line.get("value", "")
            frag = _svar_fragment_kind(line.get("name", ""), line.get("value", ""))
            feats["svar_fragment_kinds"][frag] = feats["svar_fragment_kinds"].get(frag, 0) + 1
            for param in line.get("params", []):
                pkey = param.get("key", "")
                praw = param.get("raw", "")
                if pkey in ABILITY_CONTAINERS and _VERB_TOKEN_RE.match(praw):
                    # SVar effect bodies (DB$/AB$ fragments) carry the same
                    # verb grammar as ability lines (Cleanup, ReplaceEffect
                    # shapes): recognize them identically.
                    feats["ability_kinds"].append(praw)
                    shape, flags = verb_shape(praw)
                    if shape is None:
                        feats["unknown_ability_verbs"].append(praw)
                    else:
                        verb_shapes.append((praw, shape))
                        verb_shape_set.add(shape)
                        shape_flags.update(flags)
                        if "MANUAL_REVIEW" in flags:
                            feats["manual_review_verbs"].append(praw)
                        if "LAYER_ADJUDICATION" in flags:
                            feats["layer_adjudication_verbs"].append(praw)
                        if "PREVENTION_ADJUDICATION" in flags:
                            feats["prevention_adjudication_verbs"].append(praw)
        elif kind == "Keyword":
            feats["has_keyword"] = True
        elif kind == "Field":
            fkey = line.get("key", "")
            fval = line.get("value", "")
            if fkey == "ManaCost" and fval.strip() not in ("", "no cost"):
                feats["has_mana_cost"] = True
                if _X_TOKEN_RE.search(fval):
                    feats["has_x_value"] = True
                    if "MANACOST_X" not in feats["x_sources"]:
                        feats["x_sources"].append("MANACOST_X")
            if fkey in ("Commander",):
                feats["has_commander"] = True
    # SVar named X is a symbolic reference, never an X mechanic by itself
    # (Braids shape). Record its definition kind for adjudication context.
    if "X" in svar_map:
        feats["x_sources"].append("SVAR_X_DEFINED")
        if re.match(r"^\s*Count\$", svar_map["X"]):
            feats["x_sources"].append("X_COUNT_DEFINED")
    if _X_CONDITION_RE.search(text):
        feats["x_sources"].append("X_CONDITION_REF")
    lowered = text.lower()
    if any(s in lowered for s in _HIDDEN_SIGNALS):
        feats["has_hidden"] = True
    if "HIDDEN" in shape_flags:
        feats["has_hidden"] = True
    # Shape-driven signal promotion (generic by construct, not card name).
    if "COPY_CONTROL" in shape_flags:
        feats["has_copy_control"] = True
    if "REPLACEMENT" in shape_flags:
        feats["has_replacement"] = True
    if "TRIGGER" in shape_flags:
        feats["has_trigger"] = True
    if "COMBAT" in shape_flags:
        feats["has_combat"] = True
    feats["_verb_shapes"] = verb_shapes
    feats["_shape_flags"] = sorted(shape_flags)
    feats["_verb_shape_set"] = sorted(verb_shape_set)
    feats["static_mode_classes"] = sorted(static_mode_classes)
    feats["ability_mode_classes"] = sorted(ability_mode_classes)
    feats["random_kinds"] = _random_kinds(text, feats, text)
    # Tutor-shuffle rule preserved: a bare library shuffle is recorded as
    # has_shuffle and never implies discretionary RANDOMNESS.
    if "SHUFFLE" in feats["random_kinds"]:
        feats["has_shuffle"] = True
    if any(k != "SHUFFLE" for k in feats["random_kinds"]):
        feats["has_random"] = True
    if any(s in lowered for s in _COPY_CONTROL_SIGNALS):
        feats["has_copy_control"] = True
    multiplayer_hits: list[str] = []
    for phrase in _MULTIPLAYER_PHRASES:
        if phrase in lowered:
            multiplayer_hits.append(phrase)
    for found in sorted(set(_MULTIPLAYER_WORD_RE.findall(lowered))):
        multiplayer_hits.append(found.lower())
    if multiplayer_hits:
        feats["has_multiplayer"] = True
        feats["multiplayer_signals"] = sorted(set(multiplayer_hits))
    if any(s in text for s in _COMMANDER_SIGNALS):
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
    feats["verb_shapes"] = sorted({shape for _, shape in verb_shapes})
    feats["trigger_modes"] = sorted(set(feats["trigger_modes"]))
    feats["unknown_ability_verbs"] = sorted(set(feats["unknown_ability_verbs"]))
    feats["unknown_trigger_modes"] = sorted(set(feats["unknown_trigger_modes"]))
    feats["unknown_static_modes"] = sorted(set(feats["unknown_static_modes"]))
    feats["unknown_ability_modes"] = sorted(set(feats["unknown_ability_modes"]))
    feats["manual_review_verbs"] = sorted(set(feats["manual_review_verbs"]))
    feats["layer_adjudication_verbs"] = sorted(set(feats["layer_adjudication_verbs"]))
    feats["prevention_adjudication_verbs"] = sorted(set(feats["prevention_adjudication_verbs"]))
    feats["x_sources"] = sorted(set(feats["x_sources"]))
    del feats["_verb_shapes"]
    del feats["_shape_flags"]
    del feats["_verb_shape_set"]
    feats["diagnostic_count"] = len(parsed["diagnostics"]) + sum(
        len(line.get("diagnostics", [])) for line in parsed["lines"] if isinstance(line, dict)
    )
    feats["unsupported_count"] = len(parsed["unsupported"])
    return feats
