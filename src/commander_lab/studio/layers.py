"""Bewertungsebenen: additional, objectively derivable rating layers of the tier list.

Every layer is a separate, honestly labelled column next to the strength tier. A layer never
changes the tier on its own: it joins the strength index only when the Owner gives it a weight
(default and recommendation: 0 for every layer), and then as one more rank-based component.

The module is pure: card facts and Playgroup atlas records in, layer values out. No store, no
clock, no network. The store side (reading the oracle texts and the atlas rows) lives in
``layers_view.py``.

Layers (key, label, what it is):

``pod_scaling`` "Großpod-Wirkung" is DERIVED from the oracle text by fixed rules (see
``classify_pod_scaling``): no measurement. Its rank value is the ordinal of its class.

``tempo`` "Tempo": the Playgroup ``on_curve_pct``, the share of the games in which the card
was cast on its mana value turn. Denominator: ``on_curve_denominator`` (the games in which the
card was cast at all).

``playability`` "Ausspielquote": the Playgroup ``drawn_to_played_pct``, the share of the games
in which the card was drawn and then cast. The true denominator of that share is the funnel
count ``ever_drawn_n`` (games in which the card was drawn), not ``first_cast_n`` (the games in
which it was cast, which is the numerator). A record without ``ever_drawn_n`` has no value
(``NO_COUNT``): no other count stands in for the denominator.

``staying`` "Standfestigkeit": the Playgroup ``battlefield_survival_pct``, the share of the
cards that reached the battlefield and were still there at the end of the game. Denominator:
``reached_battlefield_n``. Permanents only; an instant or sorcery has no value.

``win_gap`` "Sieg-Abstand": the observed Playgroup win-rate gap exactly as the strength index
reads it (``strength.observed_gap``: same minimum sample, same shrinkage). It is shown as a
column only and has no weight of its own, because the index already counts it as the component
``playgroup_observed``: a second weight would count it twice.

The three measured share layers (tempo, playability, staying) count a value only from
``MIN_SAMPLE`` games and only when the record is not flagged ``insufficient_sample``. The
share becomes its 95 % Wilson lower bound (``strength.wilson_lower``); the raw share, the
sample and the bound are all kept. A missing or thin value is UNKNOWN with a reason, never 0.
The percentile rank (0..100) is taken among the ranked pool cards that have a value, ties share
the mean rank (``strength.percentile_ranks``). The commander and basic lands get no value.

All Playgroup values are correlations observed in other players' multiplayer games: no
causal card strength, no win rate of the Owner's own games, and no per-pod-size breakdown
exists in the source.
"""

from __future__ import annotations

import math
import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import TypedDict

from .strength import (
    DEFAULT_POD_SIZE,
    LAYER_KEYS,
    LAYER_LABELS,
    OBSERVED_MIN_SAMPLE,
    POD_SIZE_MAX,
    POD_SIZE_MIN,
    Observation,
    layer_component,
    observed_gap,
    percentile_ranks,
    wilson_lower,
)

SCHEMA = "studio-layers-1"
MIN_SAMPLE = 25
POD_MIN = POD_SIZE_MIN
POD_MAX = POD_SIZE_MAX
POD_DEFAULT = DEFAULT_POD_SIZE

# Status of one layer value of one card.
OK = "OK"
UNKNOWN = "UNKNOWN"
NOT_APPLICABLE = "NOT_APPLICABLE"

# Reasons of an UNKNOWN or NOT_APPLICABLE value.
NO_RECORD = "NO_RECORD"
NO_VALUE_PUBLISHED = "NO_VALUE_PUBLISHED"
NO_COUNT = "NO_COUNT"
SAMPLE_TOO_SMALL = "SAMPLE_TOO_SMALL"
INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
NOT_A_PERMANENT = "NOT_A_PERMANENT"
NOT_RANKED = "NOT_RANKED"

REASON_TEXT: dict[str, str] = {
    NO_RECORD: "keine Zeile der Quelle für diese Karte",
    NO_VALUE_PUBLISHED: "die Quelle nennt keinen Wert (unbekannt, nicht 0)",
    NO_COUNT: "die Quelle nennt Zähler oder Nenner nicht (unbekannt, nicht 0)",
    SAMPLE_TOO_SMALL: f"weniger als {MIN_SAMPLE} Partien (unbekannt, nicht 0)",
    INSUFFICIENT_SAMPLE: "die Quelle markiert die Stichprobe als zu klein (unbekannt, nicht 0)",
    NOT_A_PERMANENT: "Spontanzauber oder Hexerei: kein Dauerhaft-Wert",
    NOT_RANKED: "Commander und Standardländer bekommen keinen Wert",
}

# Pod scaling classes, strongest first; the rank value is the ordinal (higher = scales more).
SCALES = "SCALES"
OPPONENT_TRIGGER = "OPPONENT_TRIGGER"
NEUTRAL = "NEUTRAL"
SINGLE_TARGET = "SINGLE_TARGET"
POD_CLASSES = (SCALES, OPPONENT_TRIGGER, NEUTRAL, SINGLE_TARGET)
POD_CLASS_RANK: dict[str, int] = {
    SCALES: 3,
    OPPONENT_TRIGGER: 2,
    NEUTRAL: 1,
    SINGLE_TARGET: 0,
}
POD_CLASS_LABELS: dict[str, str] = {
    SCALES: "wirkt auf jeden Gegner",
    OPPONENT_TRIGGER: "löst bei Aktionen der Gegner aus",
    NEUTRAL: "neutral",
    SINGLE_TARGET: "nur ein einzelnes Ziel",
}
POD_CLASS_HELP: dict[str, str] = {
    SCALES: "Die Wirkung gilt je Gegner oder je Spieler: je größer die Runde, desto mehr.",
    OPPONENT_TRIGGER: "Die Karte löst bei Handlungen der Gegner aus: mehr Gegner, mehr Auslöser.",
    NEUTRAL: "Kein Hinweis im Regeltext, dass die Rundengröße etwas ändert.",
    SINGLE_TARGET: "Die einzige Wechselwirkung ist ein einzelnes Ziel (Entfernung, Konter, ein Spieler).",
}
SYMMETRIC = "SYMMETRIC"
FLAG_LABELS: dict[str, str] = {SYMMETRIC: "symmetrisch (trifft auch dich)"}
POD_DERIVED_NOTE = "aus dem Regeltext abgeleitet, keine Messung"

# ---------- pod scaling: fixed rules on the oracle text ----------

_REMINDER = re.compile(r"\([^)]*\)")

# Triggers on what other players do. They are matched first and removed from the text, so the
# scaling phrases below do not see the "each player" of "at the beginning of each player's".
_TRIGGER_PATTERNS: tuple[tuple[str, re.Pattern[str], bool], ...] = (
    ("whenever an opponent", re.compile(r"\bwhenever an opponent\b"), False),
    ("if an opponent would", re.compile(r"\bif an opponent would\b"), False),
    ("at the beginning of each upkeep", re.compile(r"\bat the beginning of each upkeep\b"), True),
    (
        "at the beginning of each end step",
        re.compile(r"\bat the beginning of each end step\b"),
        True,
    ),
    ("whenever a player", re.compile(r"\bwhenever a player\b"), True),
    (
        "whenever ... an opponent controls",
        re.compile(r"\bwhenever [^,.:;\n]*?\ban opponent controls\b"),
        False,
    ),
    (
        "at the beginning of each opponent's",
        re.compile(r"\bat the beginning of each opponent's\b"),
        False,
    ),
    (
        "at the beginning of each other player's",
        re.compile(r"\bat the beginning of each other player's\b"),
        False,
    ),
    (
        "at the beginning of each player's",
        re.compile(r"\bat the beginning of each player's\b"),
        True,
    ),
)

# The start of a keyword line up to one keyword of it: "myriad", "flying, myriad".
_KEYWORD_LINE = r"^(?:[a-z']+(?: [a-z']+)*, )*"
# ... and what may follow the keyword: the next keyword, a cost, the end of the line. Running
# text ("Myriad Landscape enters tapped", "When this enters, extort ...") is no keyword.
_KEYWORD_END = r"(?=[ \t]*(?:,|$|\{|\u2014))"

# Effects that apply per opponent or per player. ``each player`` also hits you (SYMMETRIC).
_SCALE_PATTERNS: tuple[tuple[str, re.Pattern[str], bool], ...] = (
    ("each of your opponents", re.compile(r"\beach of your opponents\b"), False),
    ("for each opponent", re.compile(r"\bfor each opponent\b"), False),
    ("number of opponents", re.compile(r"\bnumber of opponents\b"), False),
    ("each opponent", re.compile(r"\beach opponent\b"), False),
    ("each other player", re.compile(r"\beach other player\b"), False),
    ("each player", re.compile(r"\beach player\b"), True),
    # counting what the opponents control grows with their number
    (
        "number of … your opponents control",
        re.compile(r"\bnumber of [^.\n]*?\byour opponents control\b"),
        False,
    ),
    (
        "for each … your opponents control",
        re.compile(r"\bfor each [^.\n]*?\byour opponents control\b"),
        False,
    ),
    # an effect on the permanents of all opponents ("Creatures your opponents control get
    # -1/-1"). A protective clause ("spells or abilities your opponents control") is no match.
    (
        "… your opponents control",
        re.compile(
            r"\b(?:creatures|permanents|artifacts|enchantments|lands|planeswalkers|tokens)"
            r" your opponents control\b"
        ),
        False,
    ),
    ("your opponents", re.compile(r"\byour opponents\b(?! control)"), False),
    # keywords whose per-opponent meaning sits in the (stripped) reminder text
    # (also inside a comma separated keyword line: "Flying, myriad")
    ("Extort", re.compile(rf"{_KEYWORD_LINE}extort\b{_KEYWORD_END}", re.M), False),
    ("Myriad", re.compile(rf"{_KEYWORD_LINE}myriad\b{_KEYWORD_END}", re.M), False),
    ("Melee", re.compile(rf"{_KEYWORD_LINE}melee\b{_KEYWORD_END}", re.M), False),
    ("Overload", re.compile(rf"{_KEYWORD_LINE}overload\b{_KEYWORD_END}", re.M), False),
    ("can't attack you unless", re.compile(r"\bcan't attack you unless\b"), False),
    ("creatures can't attack you", re.compile(r"\bcreatures can't attack you\b"), False),
)

# "target player" alone is no interaction with one opponent: it is often aimed at yourself
# ("Target player draws two cards"), so it stays neutral.
_SINGLE_PLAYER = (("target opponent", re.compile(r"\btarget opponent\b")),)
_OBJECT = (
    r"(?:(?:non\w+|legendary|tapped|untapped|attacking|blocking|artifact|enchantment|"
    r"planeswalker|land|creature|permanent|spell|battle)\s+)*"
    r"(?:creature|permanent|spell|artifact|enchantment|planeswalker|battle)"
)
# One removal or counter effect on one target: destroy, exile, counter, bounce, damage, steal,
# a -X/-X effect. A pump spell or an Aura on "target creature" is not one of them.
_SINGLE_REMOVAL = re.compile(
    rf"\b(?:destroy|exile|counter|gain control of) target {_OBJECT}(?! you control| you own| card)"
    rf"|\breturn target (?![^.\n]*?\byou (?:control|own)\b)[^.\n]*? to its owner's hand"
    rf"|\bdeals? (?:\d+|x) damage to (?:any target|target {_OBJECT})"
    rf"|\btarget {_OBJECT} gets -"
)


class PodScaling(TypedDict):
    cls: str
    label: str
    rank: int
    flag: str | None
    phrases: list[str]
    note: str


def _clean(text: str) -> str:
    return _REMINDER.sub(" ", text).lower().replace("\u2019", "'")


def classify_pod_scaling(text: str) -> PodScaling:
    """The Großpod-Wirkung class of an oracle text (all faces joined by the caller).

    Fixed rules, applied to the lower-cased text with the reminder text in parentheses
    removed. The strongest class that applies wins, in this order:

    1. ``SCALES``: "each opponent", "each other player", "each player", "for each opponent",
       "number of opponents", "each of your opponents", "your opponents" and an effect on
       the permanents "your opponents control" (a protective clause on "spells or abilities
       your opponents control" does not count), and the keywords extort, myriad, melee and
       overload.
    2. ``OPPONENT_TRIGGER``: "whenever an opponent", "whenever a player", "whenever ... an
       opponent controls", "at the beginning of each opponent's/player's/other player's ...".
    3. ``SINGLE_TARGET``: no clause of 1 or 2, and the card names "target opponent", or has one removal or counter effect on one target (destroy, exile,
       counter, return, gain control, damage, -X/-X on "target creature/permanent/spell/...").
    4. ``NEUTRAL``: nothing of the above.

    A mode of a modal card counts like a sentence: one scaling mode makes the card SCALES, so
    "target opponent" inside a card that also has a scaling clause stays SCALES. The extra flag
    ``SYMMETRIC`` is set when a matched phrase hits you as well ("each player", "whenever a
    player", "at the beginning of each player's"). ``phrases`` lists every matched phrase, the
    reason the page shows. This is a rule on text, not a measurement: it cannot see what a
    card does through a keyword or a static ability it does not spell out.
    """
    cleaned = _clean(text)
    phrases: list[str] = []
    symmetric = False
    triggers: list[str] = []
    remaining = cleaned
    for name, pattern, hits_you in _TRIGGER_PATTERNS:
        if pattern.search(remaining):
            triggers.append(name)
            symmetric = symmetric or hits_you
            remaining = pattern.sub(" ", remaining)
    scales: list[str] = []
    for name, pattern, hits_you in _SCALE_PATTERNS:
        if pattern.search(remaining):
            scales.append(name)
            symmetric = symmetric or hits_you
            remaining = pattern.sub(" ", remaining)
    singles = [name for name, pattern in _SINGLE_PLAYER if pattern.search(cleaned)]
    removal = _SINGLE_REMOVAL.search(cleaned)
    if removal:
        singles.append(removal.group(0))
    if scales:
        cls, phrases = SCALES, [*scales, *triggers]
    elif triggers:
        cls, phrases = OPPONENT_TRIGGER, triggers
    elif singles:
        cls, phrases = SINGLE_TARGET, singles
    else:
        cls, phrases = NEUTRAL, []
    flag = SYMMETRIC if symmetric and cls in (SCALES, OPPONENT_TRIGGER) else None
    return {
        "cls": cls,
        "label": POD_CLASS_LABELS[cls],
        "rank": POD_CLASS_RANK[cls],
        "flag": flag,
        "phrases": phrases,
        "note": POD_DERIVED_NOTE,
    }


def pod_factor(cls: str, pod_size: int) -> str | None:
    """The plain factor for a pod of ``pod_size`` players: only a scaling card has one."""
    if cls != SCALES:
        return None
    if not POD_MIN <= pod_size <= POD_MAX:
        raise ValueError(f"pod size must be between {POD_MIN} and {POD_MAX}")
    return f"wirkt auf {pod_size - 1} Gegner"


# ---------- measured layers and the result ----------

NO_TEXT = "NO_TEXT"
REASON_TEXT[NO_TEXT] = "kein Regeltext im Store (unbekannt, nicht neutral)"

KIND_MEASURED = "measured"
KIND_DERIVED = "derived"
WIN_GAP = "win_gap"
ALL_LAYER_KEYS = (*LAYER_KEYS, WIN_GAP)
LABELS: dict[str, str] = {**LAYER_LABELS, WIN_GAP: "Sieg-Abstand"}
SOURCES: dict[str, str] = {
    "pod_scaling": "Regeltext der Karte (Oracle), feste Regeln",
    "tempo": "Playgroup Card Atlas: on_curve_pct",
    "playability": "Playgroup Card Atlas: drawn_to_played_pct",
    "staying": "Playgroup Card Atlas: battlefield_survival_pct",
    WIN_GAP: "Playgroup Card Atlas: beobachteter Siegraten-Abstand (wie im Index)",
}
KINDS: dict[str, str] = {
    "pod_scaling": KIND_DERIVED,
    "tempo": KIND_MEASURED,
    "playability": KIND_MEASURED,
    "staying": KIND_MEASURED,
    WIN_GAP: KIND_MEASURED,
}
DENOMINATORS: dict[str, str] = {
    "pod_scaling": "kein Nenner (Regel auf dem Text)",
    "tempo": "on_curve_denominator: Partien, in denen die Karte gewirkt wurde",
    "playability": "ever_drawn_n: Partien, in denen die Karte gezogen wurde",
    "staying": "reached_battlefield_n: Karten, die das Schlachtfeld erreicht haben",
    WIN_GAP: "winrate_when_cast_n: Partien, in denen die Karte gewirkt wurde",
}
DESCRIPTIONS: dict[str, str] = {
    "pod_scaling": (
        "Wie sehr der Regeltext mit der Rundengröße wächst. Aus dem Text abgeleitet, keine Messung."
    ),
    "tempo": "Anteil der Partien, in denen die Karte zu ihrem Manawert-Zug gewirkt wurde.",
    "playability": "Anteil der gezogenen Karten, die auch gewirkt wurden.",
    "staying": "Anteil der Karten auf dem Schlachtfeld, die am Spielende noch dort lagen.",
    WIN_GAP: (
        "Beobachteter Unterschied der Siegrate, wenn die Karte gewirkt wurde (Prozentpunkte, "
        "bei kleiner Stichprobe zur Null gedämpft)."
    ),
}
MEASURED_NOTE = (
    "Beobachteter Zusammenhang aus fremden Mehrspieler-Partien (Playgroup.gg), keine "
    "kausale Kartenstärke; es gibt keine Aufteilung nach Rundengröße."
)
POD_NOTE = (
    "Die Rundengröße ändert nur die gezeigte Zahl der Gegner bei „Großpod-Wirkung“, "
    "nicht die Klasse, keinen Rang und keinen Index."
)
PERMANENT_TYPES = ("Creature", "Artifact", "Enchantment", "Land", "Planeswalker", "Battle")
_DISCREPANCY_PP = 1.0


@dataclass(frozen=True)
class AtlasRecord:
    """The fields of one Playgroup atlas row the layers read (percent values as published)."""

    on_curve_pct: float | None = None
    on_curve_count: int | None = None
    on_curve_denominator: int | None = None
    drawn_to_played_pct: float | None = None
    ever_drawn_n: int | None = None
    first_cast_n: int | None = None
    battlefield_survival_pct: float | None = None
    reached_battlefield_n: int | None = None
    still_on_board_at_end_n: int | None = None
    insufficient_sample: bool = False


@dataclass(frozen=True)
class LayerCard:
    """What a layer needs of one pool card. ``text`` is the oracle text of all faces (``None``
    when the store has none); ``unranked`` is the reason the card gets no value (commander,
    basic land), ``None`` for a ranked card."""

    name: str
    text: str | None
    type_line: str
    unranked: str | None = None


class LayerValue(TypedDict):
    layer: str
    value: float | None
    raw: float | None
    wilson: float | None
    n: int | None
    percentile: float | None
    status: str
    reason: str
    note: str
    detail: dict[str, object] | None


class LayerSummary(TypedDict):
    key: str
    label: str
    kind: str
    source: str
    denominator: str
    description: str
    weight_allowed: bool
    pool_cards: int
    with_value: int
    unknown: int
    not_applicable: int
    source_discrepancies: int
    min_sample: int | None


class LayerResult(TypedDict):
    schema: str
    pod_size: int
    pod_note: str
    measured_note: str
    layers: list[LayerSummary]
    cards: dict[str, dict[str, LayerValue]]


def is_permanent(type_line: str) -> bool:
    """Whether any face of the type line is a permanent type (instants and sorceries are not)."""
    return any(kind in type_line for kind in PERMANENT_TYPES)


def _value(
    layer: str,
    status: str,
    reason: str = "",
    *,
    value: float | None = None,
    raw: float | None = None,
    wilson: float | None = None,
    n: int | None = None,
    note: str = "",
    detail: dict[str, object] | None = None,
) -> LayerValue:
    return {
        "layer": layer,
        "value": value,
        "raw": raw,
        "wilson": wilson,
        "n": n,
        "percentile": None,
        "status": status,
        "reason": reason,
        "note": note or REASON_TEXT.get(reason, ""),
        "detail": detail,
    }


def share_layer(
    layer: str,
    pct: float | None,
    sample: int | None,
    *,
    insufficient: bool,
    cross_check: tuple[int, int] | None = None,
    sample_note: str = "",
    published_pct: float | None = None,
) -> LayerValue:
    """A share layer value from the published percent and its sample.

    Unknown (with the reason, never 0) when the percent is missing, the sample is below
    ``MIN_SAMPLE`` games or the source flags the record as ``insufficient_sample``. Otherwise
    ``raw`` is the published share (0..1), ``n`` the sample and ``wilson`` the 95 % Wilson lower
    bound, which is the ranking ``value``. The source publishes whole percents, so the count
    behind the bound is ``round(share * n)``. ``cross_check`` is the (count, sample) the record
    itself carries: when its share differs from the published percent by more than one
    percentage point the value stays and the row says so. ``published_pct`` is a percent the
    source printed next to a share that ``pct`` was computed from count and sample: it is only
    named in the note ("Quelle nennt X %") when it differs by more than one point."""
    if pct is None or not math.isfinite(pct):
        return _value(layer, UNKNOWN, NO_VALUE_PUBLISHED)
    if sample is None or sample < MIN_SAMPLE:
        return _value(layer, UNKNOWN, SAMPLE_TOO_SMALL, n=sample)
    if insufficient:
        return _value(layer, UNKNOWN, INSUFFICIENT_SAMPLE, n=sample)
    share = min(1.0, max(0.0, pct / 100.0))
    bound = wilson_lower(min(sample, max(0, round(share * sample))), sample)
    notes = [sample_note] if sample_note else []
    discrepancy = False
    detail: dict[str, object] | None = None
    if published_pct is not None and abs(published_pct - pct) > _DISCREPANCY_PP:
        notes.append(f"Quelle nennt {published_pct:g} %")
        detail = {"published_pct": published_pct}
    if cross_check is not None:
        count, total = cross_check
        if total > 0 and abs(100.0 * count / total - pct) > _DISCREPANCY_PP:
            discrepancy = True
            notes.append(
                f"Quelle: Prozentwert {pct:g} % passt nicht zu {count}/{total} "
                f"({100.0 * count / total:.1f} %); der veröffentlichte Prozentwert wird verwendet"
            )
    return _value(
        layer,
        OK,
        value=bound,
        raw=share,
        wilson=bound,
        n=sample,
        note="; ".join(notes),
        detail={"discrepancy": True} if discrepancy else detail,
    )


def _measured(layer: str, card: LayerCard, record: AtlasRecord | None) -> LayerValue:
    if record is None:
        return _value(layer, UNKNOWN, NO_RECORD)
    if layer == "tempo":
        # The share is the record's own count over its denominator: that is what the Wilson bound
        # and n belong to. The percent the source printed is only named when it differs.
        count, total = record.on_curve_count, record.on_curve_denominator
        if count is None or total is None or total <= 0 or not 0 <= count <= total:
            return _value(layer, UNKNOWN, NO_COUNT)
        return share_layer(
            layer,
            100.0 * count / total,
            total,
            insufficient=record.insufficient_sample,
            published_pct=record.on_curve_pct,
        )
    if layer == "playability":
        # The share of drawn cards that were cast: its denominator is the funnel count of the
        # games in which the card was drawn (ever_drawn_n), its numerator first_cast_n. A
        # record without ever_drawn_n has no denominator (first_cast_n is the numerator, never
        # a sample size): the value is unknown.
        if record.ever_drawn_n is None:
            return _value(layer, UNKNOWN, NO_COUNT)
        play_cross = (
            (record.first_cast_n, record.ever_drawn_n) if record.first_cast_n is not None else None
        )
        return share_layer(
            layer,
            record.drawn_to_played_pct,
            record.ever_drawn_n,
            insufficient=record.insufficient_sample,
            cross_check=play_cross,
        )
    if not is_permanent(card.type_line):
        return _value(layer, NOT_APPLICABLE, NOT_A_PERMANENT)
    if record.battlefield_survival_pct is not None and record.reached_battlefield_n is None:
        return _value(layer, UNKNOWN, NO_COUNT)
    cross = (
        (record.still_on_board_at_end_n, record.reached_battlefield_n)
        if record.still_on_board_at_end_n is not None and record.reached_battlefield_n is not None
        else None
    )
    return share_layer(
        layer,
        record.battlefield_survival_pct,
        record.reached_battlefield_n,
        insufficient=record.insufficient_sample,
        cross_check=cross,
    )


def _pod_value(card: LayerCard, pod_size: int) -> LayerValue:
    if card.text is None:
        return _value("pod_scaling", UNKNOWN, NO_TEXT)
    found = classify_pod_scaling(card.text)
    flag = found["flag"]
    detail: dict[str, object] = {
        "class": found["cls"],
        "label": found["label"],
        "flag": flag,
        "flag_label": FLAG_LABELS[flag] if flag else None,
        "phrases": found["phrases"],
        "factor": pod_factor(found["cls"], pod_size),
        "help": POD_CLASS_HELP[found["cls"]],
    }
    why = ", ".join(f"„{item}“" for item in found["phrases"])
    note = found["label"] + (f" ({why})" if why else "") + f": {POD_DERIVED_NOTE}"
    return _value("pod_scaling", OK, value=float(found["rank"]), note=note, detail=detail)


def _gap_value(observation: Observation | None) -> LayerValue:
    if observation is None:
        return _value(
            WIN_GAP,
            UNKNOWN,
            NO_RECORD,
            note=(
                "keine Zeile gespeichert (die Quelle nennt keinen Wert oder weniger als "
                f"{OBSERVED_MIN_SAMPLE} Partien mit der Karte)"
            ),
        )
    shrunk = observed_gap(observation)
    if shrunk is None:
        return _value(WIN_GAP, UNKNOWN, SAMPLE_TOO_SMALL, n=observation.denominator)
    return _value(
        WIN_GAP,
        OK,
        value=shrunk,
        raw=observation.value,
        n=observation.denominator,
        note="Prozentpunkte; wie im Stärke-Index zur Null gedämpft, kein eigenes Gewicht",
    )


def _rank(values: dict[str, LayerValue]) -> None:
    """Fill the percentile (0..100, ties share the mean rank) of the valued cards in place."""
    ranks = percentile_ranks(
        {card: item["value"] for card, item in values.items() if item["value"] is not None}
    )
    for card, rank in ranks.items():
        values[card]["percentile"] = round(100.0 * rank, 1)


def _summary(layer: str, items: list[LayerValue]) -> LayerSummary:
    return {
        "key": layer,
        "label": LABELS[layer],
        "kind": KINDS[layer],
        "source": SOURCES[layer],
        "denominator": DENOMINATORS[layer],
        "description": DESCRIPTIONS[layer],
        "weight_allowed": layer in LAYER_KEYS,
        "pool_cards": len(items),
        "with_value": sum(1 for item in items if item["status"] == OK),
        "unknown": sum(1 for item in items if item["status"] == UNKNOWN),
        "not_applicable": sum(1 for item in items if item["status"] == NOT_APPLICABLE),
        "source_discrepancies": sum(
            1
            for item in items
            if item["detail"] is not None
            and (item["detail"].get("discrepancy") or "published_pct" in item["detail"])
        ),
        "min_sample": None if layer == "pod_scaling" else MIN_SAMPLE,
    }


def compute_layers(
    cards: Mapping[str, LayerCard],
    atlas: Mapping[str, AtlasRecord],
    gap: Mapping[str, Observation],
    pod_size: int = POD_DEFAULT,
) -> LayerResult:
    """Every layer for every pool card (card key -> layer -> value) and a summary per layer.

    ``atlas`` and ``gap`` map a card key to its atlas record or Playgroup gap observation; a
    card without an entry is ``NO_RECORD``. The commander and basic lands (``unranked``) get no
    value and take no rank away from the others; the summaries count the ranked cards only."""
    if not POD_MIN <= pod_size <= POD_MAX:
        raise ValueError(f"pod size must be between {POD_MIN} and {POD_MAX}")
    result: dict[str, dict[str, LayerValue]] = {card_id: {} for card_id in cards}
    summaries: list[LayerSummary] = []
    for layer in ALL_LAYER_KEYS:
        valued: dict[str, LayerValue] = {}
        ranked: list[LayerValue] = []
        for card_id, card in cards.items():
            if card.unranked is not None:
                item = _value(layer, NOT_APPLICABLE, NOT_RANKED)
            elif layer == "pod_scaling":
                item = _pod_value(card, pod_size)
            elif layer == WIN_GAP:
                item = _gap_value(gap.get(card_id))
            else:
                item = _measured(layer, card, atlas.get(card_id))
            result[card_id][layer] = item
            if card.unranked is None:
                ranked.append(item)
            if item["status"] == OK:
                valued[card_id] = item
        _rank(valued)
        summaries.append(_summary(layer, ranked))
    return {
        "schema": SCHEMA,
        "pod_size": pod_size,
        "pod_note": POD_NOTE,
        "measured_note": MEASURED_NOTE,
        "layers": summaries,
        "cards": result,
    }


def index_observations(
    result: LayerResult, layers: Collection[str]
) -> dict[str, dict[str, Observation]]:
    """The observations of the given weighted layers for ``score_pool`` (card key -> component
    -> observation), valued cards only. A share layer carries its Wilson bound as the value."""
    found: dict[str, dict[str, Observation]] = {}
    for card_id, per_layer in result["cards"].items():
        for layer in layers:
            item = per_layer[layer]
            if item["status"] != OK or item["value"] is None:
                continue
            numerator = None
            if item["n"] is not None and item["raw"] is not None:
                numerator = round(item["raw"] * item["n"])
            found.setdefault(card_id, {})[layer_component(layer)] = Observation(
                item["value"], numerator, item["n"]
            )
    return found
