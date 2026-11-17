"""Deck facts for the builder: the bracket check and the data gaps of one deck list.

Both are counts with names and their origin, never a verdict (#1404 options 1 and 10).

**Bracket check.** It counts what the published Commander Brackets talk about and names the
cards: Game Changers (the ``game_changer`` flag of the public card data), cards that give
extra turns, mass land denial candidates, tutors and two-card combos. Only the Game Changer
count has a published number per bracket; for the other groups the official pages state an
intent, not a number, so the page shows the count and the wording and draws no line. The
check never says which bracket a deck is in.

* Game Changers: card data flag. A card whose flag is unknown (no public card data) is
  counted apart as unknown, never as "no Game Changer".
* Extra turns and mass land denial: patterns over the oracle text, shown as candidates with
  the rule that found them. A pattern is not a rules decision; the names are there to check.
* Tutors: the public role ``tutor`` (Scryfall tagger). Cards without any role are unknown;
  the count says how many nonland cards carry role data at all.
* Two-card combos: the commander's stored combo list (``combos.deck_combos``), only combos
  complete in the deck with exactly two cards. Without a stored list the count is unknown.

**Data gaps.** Per card of the deck, which data the builder lacks and why: no public card
data, unknown mana value, no role, unknown land colours, no source deck names the card, no
EDHREC observation. A gap means "unknown", never 0.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable, Iterable, Mapping, Sequence

SCHEMA = "studio-deck-facts-1"

# Published Game Changer limits per bracket. Source: the Commander Brackets beta (Wizards of
# the Coast, 2025-02-11) and the updates of 2025-10-21 and 2026-02-09, which change the list
# but not these limits. ``None``: no limit.
GAME_CHANGER_LIMITS: tuple[tuple[str, int | None], ...] = (
    ("1", 0),
    ("2", 0),
    ("3", 3),
    ("4", None),
    ("5", None),
)
BRACKET_SOURCES: tuple[dict[str, str], ...] = (
    {
        "title": "Commander Brackets Beta Update, 21. Oktober 2025",
        "url": "https://magic.wizards.com/en/news/announcements/"
        "commander-brackets-beta-update-october-21-2025",
    },
    {
        "title": "Commander Brackets Beta Update, 9. Februar 2026",
        "url": "https://magic.wizards.com/en/news/announcements/"
        "commander-brackets-beta-update-february-9-2026",
    },
)
# What the official pages say about the groups without a number (wording of 2025-10-21).
GROUP_NOTES = {
    "extra_turns": "Die offiziellen Seiten nennen für Extrazüge keine Zahl je Bracket.",
    "mass_land_denial": (
        "Die offiziellen Seiten nennen für Massen-Landzerstörung keine Zahl je Bracket."
    ),
    "tutors": (
        "Seit dem Update vom 21. Oktober 2025 gibt es keine Tutor-Grenze mehr; die "
        "stärksten Tutoren sind Game Changer."
    ),
    "two_card_combos": (
        "Laut Update vom 21. Oktober 2025: keine spielbeendenden Kombos in den unteren "
        "Brackets, und die erwartete Spieldauer je Bracket bestimmt, welche Kombos passen."
    ),
}

_EXTRA_TURN = re.compile(r"\btakes? (?:an|one|two|three|x|that many) extra turns?\b", re.I)
_EXTRA_TURN_DENIED = re.compile(r"can't take extra turns", re.I)
# Each pattern carries the rule shown with every candidate it finds.
_LAND_DENIAL: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "zerstört/verbannt alle Länder",
        re.compile(r"\b(?:destroy|exile) all (?:(?!except\b)[\w-]+,? )*lands\b", re.I),
    ),
    (
        "schickt alle Länder zurück",
        re.compile(r"\breturn all (?:(?!except\b)[\w-]+,? )*lands\b", re.I),
    ),
    (
        "jeder opfert mehrere Länder",
        re.compile(
            r"\beach (?:player|opponent) sacrifices (?:two|three|four|five|six|seven|x|all|half)"
            r"(?: of their| the)? (?:[\w-]+ )*lands\b",
            re.I,
        ),
    ),
    ("Länder enttappen nicht", re.compile(r"\blands don't untap\b", re.I)),
    (
        "begrenzt das Enttappen",
        re.compile(r"\bcan't untap more than (?:one|two) (?:land|permanent)", re.I),
    ),
    (
        "macht nichtbasische Länder zu Standardländern",
        re.compile(r"\bnonbasic lands are (?:plains|islands|swamps|mountains|forests)\b", re.I),
    ),
)

GAP_REASONS = {
    "no_card_data": "keine öffentlichen Kartendaten (nur Sammlungsdatei)",
    "mana_value_unknown": "Manawert unbekannt",
    "no_role": "keine Rolle (Tagger)",
    "land_colours_unknown": "Farben des Landes unbekannt",
    "no_source_deck": "kein Quelldeck des Commanders nennt die Karte (Häufigkeit unbekannt)",
    "no_edhrec": "keine EDHREC-Beobachtung für den Commander",
    "thin_in_cohort": "dünn belegt (Karte in weniger als 30 Quelldecks der Gruppe)",
}
# A note about the sample size, not a missing datum: it does not count as a gap.
NOTE_REASONS = frozenset({"thin_in_cohort"})
THIN_BELOW = 30
THIN_COHORTS = ("tuned", "all")
# What data/research/edhrec_observations_chulane/edhrec_chulane_threshold_audit.json (snapshot
# 2026-11-12) proves for the Chulane page: EDHREC lists a card on a commander page only above a
# minimum share. It does not say how low a given card is, so the text names no number.
EDHREC_AUDITED_COMMANDER = "Chulane, Teller of Tales"
EDHREC_THRESHOLD_NOTE = (
    "EDHREC listet auf den Kartenlisten der Commander-Seite nur Karten über einer "
    "Mindestquote (Prüfdatei, Stand 2026-11-12); hier keine Zeile"
)
_BASIC_TYPES = ("Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes")

_Row = Mapping[str, object] | sqlite3.Row


def _get(row: _Row, key: str) -> object:
    try:
        return row[key]
    except (KeyError, IndexError):
        return None


def _text(row: _Row, key: str) -> str:
    value = _get(row, key)
    return "" if value is None else str(value)


def _front_type(row: _Row) -> str:
    return _text(row, "type_line").split(" // ")[0]


def _is_land(row: _Row) -> bool:
    return "Land" in _front_type(row)


def _deck_rows(rows: Iterable[_Row]) -> list[_Row]:
    return [row for row in rows if _text(row, "zone") != "commander"]


def _named(rows: Iterable[_Row]) -> list[dict[str, object]]:
    return sorted(
        (
            {
                "card_id": _text(row, "card_id"),
                "name": _text(row, "oracle_name"),
                "quantity": int(_text(row, "quantity") or "1"),
            }
            for row in rows
        ),
        key=lambda item: str(item["name"]),
    )


def _text_unknown(row: _Row) -> bool:
    """True when the oracle text of ``row`` cannot be read. An empty text is a fact when the
    card facts exist (``fact_source`` set, not the bare workbook): a vanilla creature has no
    rules text. Without card facts, or a non-creature without text, it stays unknown."""
    if _get(row, "oracle_text") is not None:
        return False
    source = _text(row, "fact_source")
    return not (source and source != "workbook" and "Creature" in _text(row, "type_line"))


def _qty(rows: Iterable[_Row]) -> int:
    return sum(int(_text(row, "quantity") or "1") for row in rows)


def extra_turn_cards(rows: Iterable[_Row]) -> list[_Row]:
    """Cards whose oracle text gives a player an extra turn."""
    found = []
    for row in rows:
        text = _text(row, "oracle_text")
        if _EXTRA_TURN.search(text) and not _EXTRA_TURN_DENIED.search(text):
            found.append(row)
    return found


def land_denial_cards(rows: Iterable[_Row]) -> list[tuple[_Row, str]]:
    """Mass land denial candidates with the first rule that matched."""
    found = []
    for row in rows:
        text = _text(row, "oracle_text")
        for rule, pattern in _LAND_DENIAL:
            if pattern.search(text):
                found.append((row, rule))
                break
    return found


def bracket_facts(
    rows: Sequence[_Row],
    *,
    roles: Mapping[str, Sequence[str]],
    combos: Mapping[str, object] | None,
) -> dict[str, object]:
    """The bracket check of one deck (see the module text). ``rows`` carry ``card_id``,
    ``zone``, ``quantity``, ``oracle_name``, ``type_line``, ``oracle_text`` and
    ``game_changer`` (``None`` = unknown). ``roles`` maps ``card_id`` to its roles; a card
    missing from it carries no role data. ``combos`` is ``combos.deck_combos`` or ``None``."""
    deck = _deck_rows(rows)
    everything = list(rows)
    changers = [row for row in everything if _get(row, "game_changer") in (1, True)]
    changer_unknown = [row for row in everything if _get(row, "game_changer") is None]
    count = _qty(changers)
    unknown = _qty(changer_unknown)
    limits = []
    for bracket, limit in GAME_CHANGER_LIMITS:
        if limit is None or count + unknown <= limit:
            status = "passt"
        elif count > limit:
            status = "über der Grenze"
        else:
            status = "unbekannt"
        limits.append({"bracket": bracket, "limit": limit, "status": status})

    # Text patterns can only read cards whose oracle text is known; the rest is unknown.
    with_text = [row for row in deck if not _text_unknown(row)]
    text_unknown = _qty(row for row in deck if _text_unknown(row))
    turns = extra_turn_cards(with_text)
    denial = land_denial_cards(with_text)

    nonland = [row for row in deck if not _is_land(row)]
    with_roles = [row for row in nonland if roles.get(_text(row, "card_id"))]
    tutors = [row for row in nonland if "tutor" in roles.get(_text(row, "card_id"), ())]
    land_search = [row for row in tutors if "land_ramp" in roles.get(_text(row, "card_id"), ())]

    if combos is None or not combos.get("listed"):
        two_card: dict[str, object] = {"count": None, "listed": 0, "combos": []}
    else:
        complete = combos.get("complete")
        pairs = [
            {"cards": list(entry["cards"]), "num_decks": entry.get("num_decks")}
            for entry in (complete if isinstance(complete, list) else [])
            if isinstance(entry, Mapping) and len(entry.get("cards") or ()) == 2
        ]
        two_card = {"count": len(pairs), "listed": combos.get("listed"), "combos": pairs}

    return {
        "schema": SCHEMA,
        "sources": list(BRACKET_SOURCES),
        "game_changers": {
            "count": count,
            "of": _qty(everything),
            "unknown": unknown,
            "cards": _named(changers),
            "unknown_cards": _named(changer_unknown),
            "limits": limits,
            "method": "Kartendaten-Feld game_changer (Scryfall), Commander eingeschlossen",
        },
        "extra_turns": {
            "count": _qty(turns),
            "of": _qty(with_text),
            "text_unknown": text_unknown,
            "cards": _named(turns),
            "method": "Kartentext-Muster „extra turn“ (Kandidaten, kein Regelurteil)",
            "note": GROUP_NOTES["extra_turns"],
        },
        "mass_land_denial": {
            "count": _qty(row for row, _ in denial),
            "of": _qty(with_text),
            "text_unknown": text_unknown,
            "cards": sorted(
                (
                    {
                        "card_id": _text(row, "card_id"),
                        "name": _text(row, "oracle_name"),
                        "quantity": int(_text(row, "quantity") or "1"),
                        "rule": rule,
                    }
                    for row, rule in denial
                ),
                key=lambda item: str(item["name"]),
            ),
            "method": "Kartentext-Muster (Kandidaten, kein Regelurteil)",
            "note": GROUP_NOTES["mass_land_denial"],
        },
        "tutors": {
            "count": _qty(tutors),
            "of": _qty(nonland),
            "cards": _named(tutors),
            "land_search": _qty(land_search),
            "land_search_cards": _named(land_search),
            "role_data": {"with_roles": _qty(with_roles), "of": _qty(nonland)},
            "method": (
                "öffentliche Rolle „tutor“ (Scryfall-Tagger); der Tagger zählt Land-Suche mit, "
                "darum steht „davon Land-Suche“ (zugleich Rolle land_ramp) getrennt"
            ),
            "note": GROUP_NOTES["tutors"],
        },
        "two_card_combos": {
            **two_card,
            "method": "gespeicherte Kombo-Liste des Commanders, vollständig im Deck, genau 2 Karten",
            "note": GROUP_NOTES["two_card_combos"],
        },
        "meaning": (
            "Zählung mit Namen, keine Einstufung: Nur für Game Changer gibt es eine "
            "veröffentlichte Zahl je Bracket. Welches Bracket ein Deck spielt, legt diese "
            "Seite nicht fest."
        ),
    }


def _land_colours_known(row: _Row) -> bool:
    if _get(row, "produced_mana") is not None:
        return True
    return any(word in _front_type(row).split() for word in _BASIC_TYPES)


def data_gaps(
    rows: Sequence[_Row],
    *,
    roles: Mapping[str, Sequence[str]],
    in_source_decks: Callable[[str], bool] | None,
    has_edhrec: Callable[[str, str], bool] | None,
    cohort_hits: Mapping[str, Mapping[str, int]] | None = None,
    cohort_sizes: Mapping[str, int] | None = None,
    edhrec_note: str | None = None,
) -> dict[str, object]:
    """Per card of the deck (the commander excluded), the data that is missing and why.

    ``in_source_decks(oracle_name)`` says whether any source deck of the commander names the
    card; ``has_edhrec(card_id, oracle_name)`` whether an EDHREC inclusion value is stored for it. A
    callable that is ``None`` means the store has no such source for the commander at all:
    that reason is then reported once as ``sources_missing`` and not per card.

    ``cohort_hits`` (``builder._corpus_hits``) and ``cohort_sizes`` (``builder.cohort_sizes``)
    switch on the note ``thin_in_cohort``: a non-basic card that some source deck names but
    fewer than 30 decks of the derived ``tuned`` group (brackets 4 and 5) or of ``all`` do.
    The groups are never added. A card no source deck names stays unknown (``no_source_deck``)
    and gets no count; 0 of N is a real count. ``edhrec_note`` replaces the text of
    ``no_edhrec`` where an audit supports it."""
    deck = _deck_rows(rows)
    gaps: list[dict[str, object]] = []
    by_reason = {key: 0 for key in GAP_REASONS}
    applicable = {key: 0 for key in GAP_REASONS}
    thin_on = cohort_hits is not None and cohort_sizes is not None
    for row in deck:
        card_id = _text(row, "card_id")
        land = _is_land(row)
        basic = bool(_get(row, "is_basic_land"))
        reasons: list[str] = []
        checks: list[tuple[str, bool]] = [
            ("no_card_data", _text(row, "fact_source") == "workbook"),
        ]
        if not land:
            checks.append(("mana_value_unknown", _get(row, "mana_value") is None))
            checks.append(("no_role", not roles.get(card_id)))
        else:
            checks.append(("land_colours_unknown", not _land_colours_known(row)))
        if not basic:
            if in_source_decks is not None:
                checks.append(("no_source_deck", not in_source_decks(_text(row, "oracle_name"))))
            if has_edhrec is not None:
                checks.append(("no_edhrec", not has_edhrec(card_id, _text(row, "oracle_name"))))
        for reason, missing in checks:
            applicable[reason] += 1
            if missing:
                by_reason[reason] += 1
                reasons.append(reason)
        thin: list[dict[str, object]] = []
        counts = (
            cohort_hits.get(_text(row, "oracle_name"))
            if cohort_hits is not None and not basic
            else None
        )
        if counts is not None and cohort_sizes is not None:
            applicable["thin_in_cohort"] += 1
            thin = [
                {"cohort": group, "n": counts.get(group, 0), "of": cohort_sizes[group]}
                for group in THIN_COHORTS
                if group in cohort_sizes and counts.get(group, 0) < THIN_BELOW
            ]
            if thin:
                by_reason["thin_in_cohort"] += 1
        if reasons or thin:
            item: dict[str, object] = {
                "card_id": card_id,
                "name": _text(row, "oracle_name"),
                "reasons": reasons,
            }
            if thin:
                item["thin"] = thin
            gaps.append(item)
    gaps.sort(key=lambda item: (-len(item["reasons"]), str(item["name"])))  # type: ignore[arg-type]
    sources_missing = [
        reason
        for reason, absent in (
            ("no_source_deck", in_source_decks is None),
            ("no_edhrec", has_edhrec is None),
        )
        if absent
    ]
    return {
        "schema": SCHEMA,
        "cards_checked": len(deck),
        "cards_with_gaps": sum(1 for item in gaps if item["reasons"]),
        "cards_with_thin": sum(1 for item in gaps if item.get("thin")),
        "thin_below": THIN_BELOW,
        "by_reason": {
            reason: {"count": by_reason[reason], "of": applicable[reason]}
            for reason in GAP_REASONS
            if reason not in sources_missing and (reason != "thin_in_cohort" or thin_on)
        },
        "reason_labels": {
            **GAP_REASONS,
            **({"no_edhrec": edhrec_note} if edhrec_note else {}),
        },
        "sources_missing": sources_missing,
        "gaps": gaps,
        "meaning": (
            "Fehlende Daten heißen unbekannt, nicht 0. Gezählt werden Karten (ohne Commander); "
            "der Nenner je Grund nennt, für wie viele Karten der Grund geprüft wurde "
            "(Rollen und Manawert nur Nicht-Länder, Quelldecks und EDHREC ohne Standardländer). "
            "„Dünn belegt“ ist ein Hinweis auf die Stichprobe (n von N Quelldecks je Gruppe, "
            "Gruppen nie addiert), keine fehlende Angabe."
        ),
    }


def edhrec_lookup(store: object, commanders: Sequence[str]) -> Callable[[str, str], bool] | None:
    """``has_edhrec(card_id, oracle_name)`` for the commanders, or ``None`` when the store holds
    no EDHREC value for them at all. Observations often carry no ``card_id``: they are then
    found by name, casefolded, through the spelling discipline of the card counts
    (``universe.spelling_owners``) and by the front face of ``A // B``."""
    from . import builder
    from .store import StudioStore
    from .universe import _card_name_index

    if not isinstance(store, StudioStore):
        raise TypeError("store must be a StudioStore")
    if not commanders:
        return None
    db = store.connection
    marks = ",".join("?" * len(commanders))
    raw_names = {
        str(row[0])
        for row in db.execute(
            "SELECT card_name FROM card_signal WHERE (signal = 'edhrec_commander_inclusion' "
            "OR signal LIKE 'edhrec_bracket_inclusion:%') "
            f"AND value IS NOT NULL AND commander_name IN ({marks})",
            list(commanders),
        )
    }
    bound, args = builder.bound_to("observation_cohort", "o.cohort", commanders)
    ids: set[str] = set()
    for row in db.execute(
        "SELECT DISTINCT o.card_id, o.card_name FROM observation o "
        f"WHERE o.metric = 'inclusion_pct' AND o.value IS NOT NULL{bound}",
        args,
    ):
        if row[0] is not None:
            ids.add(str(row[0]))
        raw_names.add(str(row[1]))
    if not ids and not raw_names:
        return None
    # A spelling counts for a card only when it names exactly that card: its full name, or a
    # front face no other card owns (``unique``). A front face several cards share names no
    # single card, so it credits none (an observation "Fire" is not one of "Fire // Ice").
    _by_oracle, unique = _card_name_index(store)
    names: set[str] = set()
    for raw in raw_names:
        key = raw.casefold()
        names.add(key)
        owner = unique.get(key)
        if owner is not None:
            names.add(owner.casefold())

    def has(card_id: str, name: str) -> bool:
        return card_id in ids or name.casefold() in names

    return has


def deck_facts(store: object, rows: Sequence[sqlite3.Row]) -> dict[str, object]:
    """Both checks for a deck read from the store (``decks.list_rows`` rows)."""
    from . import builder, combos
    from .store import StudioStore

    if not isinstance(store, StudioStore):
        raise TypeError("store must be a StudioStore")
    db = store.connection
    ids = [str(row["card_id"]) for row in rows]
    extra: dict[str, sqlite3.Row] = {}
    roles: dict[str, list[str]] = {}
    for start in range(0, len(ids), 500):
        chunk = ids[start : start + 500]
        marks = ",".join("?" * len(chunk))
        for row in db.execute(
            f"SELECT card_id, game_changer, fact_source FROM card_fact WHERE card_id IN ({marks})",
            chunk,
        ):
            extra[str(row["card_id"])] = row
        for row in db.execute(
            "SELECT c.card_id, r.role FROM card_fact c JOIN card_role r USING (oracle_id) "
            f"WHERE c.card_id IN ({marks}) ORDER BY r.role",
            chunk,
        ):
            roles.setdefault(str(row["card_id"]), []).append(str(row["role"]))
    full: list[dict[str, object]] = []
    for row in rows:
        item = {key: row[key] for key in row.keys()}  # noqa: SIM118 (sqlite3.Row)
        found = extra.get(str(row["card_id"]))
        item["game_changer"] = None if found is None else found["game_changer"]
        item["fact_source"] = None if found is None else found["fact_source"]
        full.append(item)
    commanders = [str(row["oracle_name"]) for row in rows if row["zone"] == "commander"]
    combo_view = combos.deck_combos(store, rows) if commanders else None
    hits = builder._corpus_hits(store, commanders) if commanders else {}
    has_edhrec = edhrec_lookup(store, commanders) if commanders else None
    sizes = builder.cohort_sizes(store, commanders) if hits else None
    return {
        "bracket": bracket_facts(full, roles=roles, combos=combo_view),
        "data_gaps": data_gaps(
            full,
            roles=roles,
            in_source_decks=(lambda name: name in hits) if hits else None,
            has_edhrec=has_edhrec,
            cohort_hits=hits if hits else None,
            cohort_sizes=sizes,
            edhrec_note=(
                EDHREC_THRESHOLD_NOTE if commanders == [EDHREC_AUDITED_COMMANDER] else None
            ),
        ),
    }
