"""Compare the engine's rules text with the printed Oracle text.

Pure functions, typed, no I/O. Used by scripts/card_text_drift_report.py
to find candidate implementation differences between what the engine says
a card does and what the printed card says.
"""

from __future__ import annotations

import html
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

# Reminder text lives in parentheses or in <i>...</i> in the engine export.
_PAREN_REMINDER = re.compile(r"\([^()]*\)")
_ITALIC_REMINDER = re.compile(r"<i>.*?</i>", re.DOTALL | re.IGNORECASE)
_HTML_TAG = re.compile(r"<[^>]+>")

# Ability words ("Landfall", "Raid", ...) are reminder-style prefixes on both
# sides; the engine and Oracle agree on the effect, so drop the prefix.
_ABILITY_WORD_PREFIX = re.compile(
    r"^(?:landfall|raid|revolt|morbid|threshold|delirium|hellbent|fateful hour|"
    r"metalcraft|imprint|haunt|soulshift|bushido|ninjutsu|transmute|splice|"
    r"storm|replicate|retrace|flashback|unearth|persist|undying|evolve|"
    r"bloodrush|battalion|extort|cipher|tribute|inspired|outlast|dash|exploit|"
    r"renown|awaken|surge|devoid|ingest|void|rally|cohort|support|escalate|"
    r"emerge|meld|fabricate|revolt|aftermath|eternalize|afflict|mentor|jump-start|"
    r"undergrowth|addendum|riot|spectacle|adapt|amass|proliferate|companion|"
    r"mutate|escape|encore|blitz|casualty|alliance|enlist|domain|corrupted|"
    r"toxic|oil counters|for mirrodin!|celebration|parley|council's dilemma|"
    r"will of the council|tempting offer|join forces|assist|surge|improvise|"
    r"revolt|replicate)\s*[—–-]\s*",  # noqa: RUF001 (intentional: em/en dash + hyphen)
    re.IGNORECASE,
)

_TYPOGRAPHIC = (
    ("\u2018", "'"),
    ("\u2019", "'"),
    ("\u201c", '"'),
    ("\u201d", '"'),
    ("\u2014", "-"),
    ("\u2013", "-"),
    ("\u2212", "-"),  # minus sign: planeswalker loyalty costs use U+2212
    ("\u2022", "-"),
    ("\u00b7", "-"),
    ("&bull;", "-"),
    ("&mdash;", "-"),
    ("&ndash;", "-"),
    ("&rsquo;", "'"),
    ("&lsquo;", "'"),
    ("&ldquo;", '"'),
    ("&rdquo;", '"'),
    ("&amp;", "&"),
)
_WHITESPACE = re.compile(r"\s+")
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _strip_html(text: str) -> str:
    text = _ITALIC_REMINDER.sub(" ", text)
    text = _HTML_TAG.sub(" ", text)
    return html.unescape(text)


def _strip_tags_keep_content(text: str) -> str:
    """Remove HTML tags but keep their content (for keyword detection).

    Ability words like <i>Magecraft</i> are wrapped in italics in the engine
    export; dropping the content (as _strip_html does for similarity) would
    hide keywords that the Oracle keyword list contains.
    """
    text = _HTML_TAG.sub(" ", text)
    return html.unescape(text)


def _unify_typography(text: str) -> str:
    for old, new in _TYPOGRAPHIC:
        text = text.replace(old, new)
    return text


def _drop_reminder_parens(text: str) -> str:
    # Reminder text is always parenthesised on both sides. Iterate because
    # nested parens do not occur in Oracle text; one pass is enough, but a
    # second pass is cheap insurance.
    for _ in range(2):
        new = _PAREN_REMINDER.sub(" ", text)
        if new == text:
            break
        text = new
    return text


def _tilde_name(text: str, name: str) -> str:
    """Replace the card name (and its short form) and {this} with ~."""
    short = name.split(",")[0].strip()
    for variant in (name, short):
        if variant:
            text = re.sub(re.escape(variant), "~", text, flags=re.IGNORECASE)
    return text.replace("{this}", "~")


def _normalize(text: str, name: str) -> str:
    text = _strip_html(text)
    text = _drop_reminder_parens(text)
    text = _unify_typography(text)
    text = _tilde_name(text, name)
    text = text.lower()
    lines = []
    for line in text.split("\n"):
        line = _ABILITY_WORD_PREFIX.sub("", line.strip())
        lines.append(line)
    text = "\n".join(lines)
    text = _WHITESPACE.sub(" ", text).strip()
    return text


def normalize_oracle_text(text: str, name: str) -> str:
    """Normalise printed Oracle text for comparison."""
    return _normalize(text or "", name)


def normalize_engine_rules(lines: Sequence[str], name: str) -> str:
    """Normalise the engine's rules lines for comparison."""
    return _normalize("\n".join(lines or []), name)


# ---------------------------------------------------------------------------
# Face splitting (split / adventure / double-faced)
# ---------------------------------------------------------------------------

_ENGINE_FACE_SEP = "--------"


def split_oracle_faces(text: str) -> list[str]:
    """Split Oracle text into faces on a line that is exactly '//'."""
    faces: list[str] = []
    current: list[str] = []
    for line in (text or "").split("\n"):
        if line.strip() == "//":
            faces.append("\n".join(current))
            current = []
        else:
            current.append(line)
    faces.append("\n".join(current))
    return [f for f in faces if f.strip()]


def split_engine_faces(lines: Sequence[str]) -> list[str]:
    """Split engine rules lines into faces on the '--------' separator."""
    faces: list[str] = []
    current: list[str] = []
    for line in lines or []:
        if _ENGINE_FACE_SEP in line:
            # The separator line itself may carry trailing text (e.g. Fuse
            # reminder) on the same line; keep the text after the dashes.
            faces.append("\n".join(current))
            current = []
            _, _, after = line.partition(_ENGINE_FACE_SEP)
            # Strip leading dashes that may remain from a longer run.
            after = after.lstrip("-").strip()
            if after:
                current.append(after)
        else:
            current.append(line)
    faces.append("\n".join(current))
    return [f for f in faces if f.strip()]


# ---------------------------------------------------------------------------
# Numbers and keywords
# ---------------------------------------------------------------------------


_BRACED = re.compile(r"\{[^}]*\}")


def _dedup_sentences(text: str) -> str:
    """Drop exact-duplicate sentences (split-mana-ability noise).

    The engine lists "{T}: Add {W} or {U}" as two parallel abilities, each
    repeating "deals 1 damage to you"; the Oracle states it once. Counting
    each distinct sentence once keeps the number multiset comparable.
    """
    seen: set[str] = set()
    out: list[str] = []
    for sentence in text.split("."):
        key = sentence.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(sentence)
    return ".".join(out)


def number_multiset(text: str) -> Counter[str]:
    """Multiset of numbers in normalised text (as strings, order-free).

    Numbers inside {...} mana symbols are excluded: they are costs, and the
    engine lists adventure-card costs in the rules text where the Oracle
    keeps them in the mana_cost field. Duplicate sentences are counted once
    (split mana abilities repeat the damage line per color).
    """
    text = _BRACED.sub(" ", text)
    text = _dedup_sentences(text)
    return Counter(_NUMBER.findall(text))


def engine_keywords(rules_text: str, known: Sequence[str]) -> set[str]:
    """Keywords present in engine rules text.

    Matching is lenient: a keyword matches a whole word, a word starting
    with the keyword ("goad" in "goaded", "mill" in "mills") or a word
    ending with it ("cycling" in "plainscycling"). Multi-word phrases
    require an exact phrase match. A keyword ending in "cycling" also
    matches any *cycling word in the text ("landcycling" matches
    "Plainscycling"): the specific type implies the general mechanic.
    """
    found: set[str] = set()
    lowered = rules_text.lower()
    for kw in known:
        k = kw.lower().strip()
        if not k:
            continue
        if " " in k:
            # Multi-word phrase: exact match.
            pattern = r"(?<![a-z])" + re.escape(k) + r"(?![a-z])"
        elif k.endswith("cycling"):
            # *cycling family: any *cycling word in the text counts.
            pattern = r"(?<![a-z])[a-z]*cycling(?![a-z])"
        else:
            # Single word: allow affixes on either side.
            pattern = r"(?<![a-z])[a-z]*" + re.escape(k) + r"[a-z]*(?![a-z])"
        if re.search(pattern, lowered):
            found.add(kw)
    return found


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StructuralDiff:
    field: str
    oracle: str
    engine: str


@dataclass(frozen=True)
class CardDrift:
    name: str
    tier: str  # "A" | "B" | "C" | "OK" | "EXPORT_GAP"
    similarity: float
    structural: tuple[StructuralDiff, ...] = ()
    numbers_only_oracle: tuple[str, ...] = ()
    numbers_only_engine: tuple[str, ...] = ()
    keywords_only_oracle: tuple[str, ...] = ()
    keywords_only_engine: tuple[str, ...] = ()


_BASIC_LANDS = frozenset({"Plains", "Island", "Swamp", "Mountain", "Forest"})

# Structural fields compared for tier A, as (facts_key, oracle_key).
_STRUCTURAL_FIELDS: tuple[tuple[str, str], ...] = (
    ("mana_cost", "mana_cost"),
    ("mana_value", "mana_value"),
    ("types", "type_line"),  # compared via type_line containment, see below
    ("power", "power"),
    ("toughness", "toughness"),
    ("loyalty", "loyalty"),
)


def _fmt(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (list, tuple)):
        return ",".join(str(v) for v in value)
    return str(value)


def _norm_mana_cost(cost: str | None) -> str:
    """Normalise a mana cost: drop '{*}' face separators, sort symbols."""
    if not cost:
        return ""
    parts = [p for p in re.findall(r"\{[^}]*\}", cost) if p != "{*}"]
    return "".join(sorted(parts))


def _mana_cost_matches(oracle_cost: str | None, engine_cost: str | None) -> bool:
    """True if the mana costs match.

    For split/adventure/double-faced cards the engine cost contains '{*}'
    face separators; a match on any single face counts (the Oracle entry
    carries the front-face cost).
    """
    o_norm = _norm_mana_cost(oracle_cost)
    e_raw = str(engine_cost or "")
    if "{*}" not in e_raw:
        return o_norm == _norm_mana_cost(e_raw)
    return any(o_norm == _norm_mana_cost(face) for face in e_raw.split("{*}"))


def compare_card(
    oracle_entry: Mapping[str, Any],
    facts_entry: Mapping[str, Any],
    known_keywords: Sequence[str] = (),
) -> CardDrift:
    """Compare one card's Oracle entry with its engine facts entry."""
    name = str(oracle_entry.get("oracle_name") or oracle_entry.get("name") or "")

    structural: list[StructuralDiff] = []

    # --- Tier A: structural fields -------------------------------------
    if not _mana_cost_matches(
        str(oracle_entry.get("mana_cost") or ""),
        str(facts_entry.get("mana_cost") or ""),
    ):
        structural.append(
            StructuralDiff(
                "mana_cost",
                _norm_mana_cost(str(oracle_entry.get("mana_cost") or "")),
                _norm_mana_cost(str(facts_entry.get("mana_cost") or "")),
            )
        )

    for facts_key, oracle_key in (
        ("mana_value", "mana_value"),
        ("power", "power"),
        ("toughness", "toughness"),
        ("loyalty", "loyalty"),
    ):
        o_val = oracle_entry.get(oracle_key)
        e_val = facts_entry.get(facts_key)
        o_s, e_s = _fmt(o_val), _fmt(e_val)
        if o_s != e_s:
            # null engine power on a Vehicle/Spacecraft is an export gap:
            # the export query has no power column for those frames.
            subtypes = [str(s) for s in (facts_entry.get("subtypes") or [])]
            if (
                facts_key == "power"
                and e_val is None
                and o_val is not None
                and any(s.lower() in ("vehicle", "spacecraft") for s in subtypes)
            ):
                return CardDrift(
                    name=name,
                    tier="EXPORT_GAP",
                    similarity=1.0,
                    structural=(StructuralDiff("power", o_s, e_s),),
                )
            structural.append(StructuralDiff(facts_key, o_s, e_s))

    # Types: compare the oracle type_line against engine types/subtypes/
    # supertypes. Normalise both to word multisets.
    type_line = str(oracle_entry.get("type_line") or "")
    oracle_type_words = Counter(
        w for w in re.findall(r"[a-z]+", type_line.lower()) if w not in ("the",)
    )
    engine_type_words: Counter[str] = Counter()
    for key in ("supertypes", "types", "subtypes"):
        for t in facts_entry.get(key) or []:
            for w in re.findall(r"[a-z]+", str(t).lower()):
                engine_type_words[w] += 1
    # The em-dash separator and words like "legendary" appear on both sides;
    # compare the multisets loosely: a structural diff needs a word present
    # on one side only (beyond the dash).
    only_o = set(oracle_type_words) - set(engine_type_words) - {"—", "-"}
    only_e = set(engine_type_words) - set(oracle_type_words)
    # Filter out pure punctuation artefacts already handled above.
    only_o = {w for w in only_o if w not in ("—",)}
    if only_o or only_e:
        structural.append(
            StructuralDiff(
                "types",
                ",".join(sorted(only_o)) or "—",
                ",".join(sorted(only_e)) or "—",
            )
        )

    if structural:
        oracle_norm = normalize_oracle_text(str(oracle_entry.get("oracle_text") or ""), name)
        engine_norm = normalize_engine_rules(list(facts_entry.get("rules") or []), name)
        similarity = _similarity(oracle_norm, engine_norm)
        return CardDrift(name=name, tier="A", similarity=similarity, structural=tuple(structural))

    # --- Tier B: numbers / keywords ------------------------------------
    oracle_norm = normalize_oracle_text(str(oracle_entry.get("oracle_text") or ""), name)
    engine_norm = normalize_engine_rules(list(facts_entry.get("rules") or []), name)

    o_nums = number_multiset(oracle_norm)
    e_nums = number_multiset(engine_norm)
    numbers_only_oracle = tuple(sorted((o_nums - e_nums).elements()))
    numbers_only_engine = tuple(sorted((e_nums - o_nums).elements()))

    oracle_kw = {str(k).lower() for k in (oracle_entry.get("keywords") or [])}
    # Detect keywords in engine text with italic content preserved: ability
    # words (<i>Magecraft</i>) would otherwise be stripped before matching.
    engine_kw_text = _strip_tags_keep_content("\n".join(facts_entry.get("rules") or []))
    engine_kw_raw = engine_keywords(engine_kw_text, known_keywords or ())
    engine_kw = {k.lower() for k in engine_kw_raw}
    keywords_only_oracle = tuple(sorted(oracle_kw - engine_kw))
    keywords_only_engine = tuple(sorted(engine_kw - oracle_kw))

    if numbers_only_oracle or numbers_only_engine or keywords_only_oracle or keywords_only_engine:
        similarity = _similarity(oracle_norm, engine_norm)
        return CardDrift(
            name=name,
            tier="B",
            similarity=similarity,
            numbers_only_oracle=numbers_only_oracle,
            numbers_only_engine=numbers_only_engine,
            keywords_only_oracle=keywords_only_oracle,
            keywords_only_engine=keywords_only_engine,
        )

    # --- Tier C / OK: similarity ----------------------------------------
    # Compare face by face for split/adventure/double-faced cards.
    oracle_faces = split_oracle_faces(str(oracle_entry.get("oracle_text") or ""))
    engine_faces = split_engine_faces(list(facts_entry.get("rules") or []))
    if len(oracle_faces) > 1 or len(engine_faces) > 1:
        similarity = _face_similarity(oracle_faces, engine_faces, name)
    else:
        similarity = _similarity(oracle_norm, engine_norm)

    tier = "C" if similarity < 0.8 else "OK"
    return CardDrift(name=name, tier=tier, similarity=similarity)


def _similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    # Token-based Dice coefficient: order-insensitive, so "menace trample
    # mayhem" and "mayhem menace trample" compare as equal. difflib on the
    # raw string would punish mere reordering of keyword lines.
    a_tokens = _clean_tokens(a)
    b_tokens = _clean_tokens(b)
    if not a_tokens or not b_tokens:
        return 0.0
    a_set = Counter(a_tokens)
    b_set = Counter(b_tokens)
    intersection = sum((a_set & b_set).values())
    return 2.0 * intersection / (len(a_tokens) + len(b_tokens))


def _clean_tokens(text: str) -> list[str]:
    # Strip punctuation so "flying," matches "flying".
    out = []
    for t in text.split():
        t = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", t)
        if t:
            out.append(t)
    return out


def _face_similarity(oracle_faces: list[str], engine_faces: list[str], name: str) -> float:
    """Best similarity across face alignments.

    Face-by-face best-match handles reordered faces; concatenated comparison
    handles different groupings (e.g. the engine listing both split halves
    before the separator). Returns the maximum of both.
    """
    if not oracle_faces or not engine_faces:
        return 0.0
    o_norm = [normalize_oracle_text(f, name) for f in oracle_faces]
    e_norm = [normalize_engine_rules([f], name) for f in engine_faces]
    concat = _similarity(" ".join(o_norm), " ".join(e_norm))
    scores: list[float] = []
    for o in o_norm:
        best = max((_similarity(o, e) for e in e_norm), default=0.0)
        scores.append(best)
    facewise = sum(scores) / len(scores) if scores else 0.0
    return max(concat, facewise)


def is_basic_land(name: str) -> bool:
    return name in _BASIC_LANDS


__all__ = [
    "CardDrift",
    "StructuralDiff",
    "compare_card",
    "engine_keywords",
    "is_basic_land",
    "normalize_engine_rules",
    "normalize_oracle_text",
    "number_multiset",
    "split_engine_faces",
    "split_oracle_faces",
]
