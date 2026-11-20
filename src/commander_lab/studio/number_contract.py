"""The number contract of the Studio (B3, #1659; Charta v2 §4, ``charter_builder.md`` §5).

Every figure a builder route shows can also be sent as one contract object::

    {id, bezeichnung, wert, einheit, n, N, bezug, intervall, klasse, kohorte, quelle,
     stand_datum, stand_hash, basis_hash, pilot, piloten, data_class, hinweise}

Classes (``klasse``):

* ``EXAKT``: computed from the list itself (hypergeometry, castability, counts of the list).
* ``GEZÄHLT``: counted in a cohort (corpus, playgroup); always with ``N`` and ``kohorte``.
* ``SIMULIERT``: a simulated result (``data_class`` ``SIMULATED_RESULT``); always with ``N``,
  the deck state (``stand_hash``, ``None`` = unknown) and the pilot origin (``pilot``; until the
  experiment object B2 it is the constant ``"Konstante"``).
* ``URTEIL``: a model judgement (for example rubric v2 "Kartenverständnis").

``VORSCHLAG`` (E15 Q2) is not a number class and is refused. A missing ``wert`` is "unbekannt",
never 0; ``n`` without ``N`` is refused. ``n`` and ``N`` mean different things per figure (cards
of a cohort, games, pairs), so every ``N`` comes with ``bezug``: the noun and what ``n`` and ``N``
count, for example ``"Paare (abgeschlossen / geplant)"``. A share (``einheit`` ``Anteil``) lies
in 0..1. ``hinweise`` carries the status and warnings of the source (sample too small, stop
reason, bridge state) as text. The JavaScript twin is ``static/zahl.js``; both apply the same
rules with the same messages. Pure functions over plain data: no store, no ``sqlite3``. The route
helpers at the end turn existing answers into contract lists and leave out a figure whose source
data are inconsistent (the route never fails over it); the old fields stay unchanged.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

EXAKT = "EXAKT"
GEZAEHLT = "GEZÄHLT"
SIMULIERT = "SIMULIERT"
URTEIL = "URTEIL"
KLASSEN = (EXAKT, GEZAEHLT, SIMULIERT, URTEIL)
#: Units the display knows: a share 0..1 (shown as %), percentage points, a plain count.
EINHEITEN = ("Anteil", "pp", "Anzahl")
SIMULATED_RESULT = "SIMULATED_RESULT"
#: Pilot origin of every simulated figure until B2 (#1658) brings a pilot fingerprint.
PILOT_KONSTANTE = "Konstante"
SCHEMA = "studio-zahl-1"

_KEYS = frozenset(
    {
        "id",
        "bezeichnung",
        "wert",
        "einheit",
        "n",
        "N",
        "bezug",
        "intervall",
        "klasse",
        "kohorte",
        "quelle",
        "stand_datum",
        "stand_hash",
        "basis_hash",
        "pilot",
        "piloten",
        "data_class",
        "hinweise",
    }
)


def _is_number(value: object) -> bool:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:
        return False


def _is_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _texts(value: object) -> bool:
    return isinstance(value, list) and all(_text(item) for item in value)


def check(zahl: object) -> list[str]:
    """Every rule the object breaks (empty list = a valid contract)."""
    if not isinstance(zahl, Mapping):
        return ["keine Zahl-Struktur"]
    errors: list[str] = []
    unknown_keys = sorted(str(key) for key in zahl if key not in _KEYS)
    if unknown_keys:
        errors.append(f"unbekannte Felder: {', '.join(unknown_keys)}")
    klasse = zahl.get("klasse")
    if klasse == "VORSCHLAG":
        errors.append("VORSCHLAG ist keine Zahl-Klasse")
    elif klasse not in KLASSEN:
        errors.append("Zahl ohne gültige Klasse")
    if not _text(zahl.get("id")):
        errors.append("id fehlt")
    if not _text(zahl.get("bezeichnung")):
        errors.append("bezeichnung fehlt")
    einheit = zahl.get("einheit")
    if einheit not in EINHEITEN:
        errors.append("einheit fehlt oder unbekannt")
    if not _text(zahl.get("quelle")):
        errors.append("quelle fehlt")
    wert = zahl.get("wert")
    if wert is not None and not _is_number(wert):
        errors.append("wert ist keine endliche Zahl")
    n, total = zahl.get("n"), zahl.get("N")
    if n is not None and not _is_count(n):
        errors.append("n ist keine Anzahl")
    if total is not None and not _is_count(total):
        errors.append("N ist keine Anzahl")
    if n is not None and total is None:
        errors.append("n ohne N")
    if isinstance(n, int) and isinstance(total, int) and n > total:
        errors.append("n größer als N")
    if total is not None and not _text(zahl.get("bezug")):
        errors.append("N ohne Bezug")
    intervall = zahl.get("intervall")
    interval_ok = (
        isinstance(intervall, list)
        and len(intervall) == 2
        and all(_is_number(bound) for bound in intervall)
        and float(intervall[0]) <= float(intervall[1])
    )
    if intervall is not None and not interval_ok:
        errors.append("intervall ist kein [unten, oben]")
    if einheit == "Anteil":
        values = [wert] if _is_number(wert) else []
        if interval_ok and isinstance(intervall, list):
            values += intervall
        if any(not 0.0 <= float(str(value)) <= 1.0 for value in values):
            errors.append("Anteil außerhalb 0..1")
    for key in ("kohorte", "bezug", "stand_datum", "stand_hash", "basis_hash", "pilot"):
        value = zahl.get(key)
        if value is not None and not _text(value):
            errors.append(f"{key} ist kein Text")
    for key in ("piloten", "hinweise"):
        if zahl.get(key) is not None and not _texts(zahl.get(key)):
            errors.append(f"{key} ist keine Textliste")
    if klasse in (GEZAEHLT, SIMULIERT):
        if total is None:
            errors.append(f"{klasse} ohne N")
        if wert is not None and n is None:
            errors.append(f"{klasse} ohne n")
    if klasse == GEZAEHLT and not _text(zahl.get("kohorte")):
        errors.append("GEZÄHLT ohne Kohorte")
    if klasse == SIMULIERT:
        if zahl.get("data_class") != SIMULATED_RESULT:
            errors.append("SIMULIERT ohne data_class SIMULATED_RESULT")
        if "stand_hash" not in zahl:
            errors.append("SIMULIERT ohne Stand-Hash (leer = unbekannt)")
        if not _text(zahl.get("pilot")):
            errors.append("SIMULIERT ohne Pilot-Herkunft")
    elif zahl.get("data_class") is not None:
        errors.append("data_class nur bei SIMULIERT")
    return errors


def zahl(
    id: str,
    bezeichnung: str,
    wert: float | None,
    *,
    klasse: str,
    einheit: str,
    quelle: str,
    n: int | None = None,
    N: int | None = None,
    bezug: str | None = None,
    intervall: Sequence[float] | None = None,
    kohorte: str | None = None,
    stand_datum: str | None = None,
    stand_hash: str | None = None,
    basis_hash: str | None = None,
    gepaart: bool = False,
    pilot: str | None = None,
    piloten: Sequence[str] | None = None,
    hinweise: Sequence[str] | None = None,
) -> dict[str, object]:
    """One contract object; ``ValueError`` when it breaks a rule (never a silent 0).

    ``gepaart`` marks a simulated difference of two deck states: ``basis_hash`` is then always
    sent, ``None`` meaning the base state is unknown (for example a reference deck)."""
    built: dict[str, object] = {
        "id": id,
        "bezeichnung": bezeichnung,
        "wert": wert,
        "einheit": einheit,
        "n": n,
        "N": N,
        "bezug": bezug,
        "intervall": list(intervall) if intervall is not None else None,
        "klasse": klasse,
        "kohorte": kohorte,
        "quelle": quelle,
        "stand_datum": stand_datum,
    }
    if klasse == SIMULIERT:
        built["stand_hash"] = stand_hash
        built["pilot"] = pilot
        built["data_class"] = SIMULATED_RESULT
        if gepaart or basis_hash is not None:
            built["basis_hash"] = basis_hash
        if piloten:
            built["piloten"] = list(piloten)
    if hinweise:
        built["hinweise"] = list(hinweise)
    errors = check(built)
    if errors:
        raise ValueError(f"Zahl {id!r} verletzt den Vertrag: {'; '.join(errors)}")
    return built


# --- route helpers: existing answers -> contract lists ------------------------------------


def _try(
    out: list[dict[str, object]], id: str, bezeichnung: str, wert: float | None, **fields: object
) -> None:
    """Append one contract; a figure whose source data break the contract (for example more
    decks with the card than decks in the cohort) is left out: never shown, never a 500."""
    try:
        out.append(zahl(id, bezeichnung, wert, **fields))  # type: ignore[arg-type]
    except ValueError:
        return


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _float_or_none(value: object) -> float | None:
    if isinstance(value, int | float) and _is_number(value):
        return float(value)
    return None


def _interval(value: object) -> list[float] | None:
    if (
        isinstance(value, list)
        and len(value) == 2
        and all(_is_number(bound) for bound in value)
        and float(value[0]) <= float(value[1])
    ):
        return [float(value[0]), float(value[1])]
    return None


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _names(value: object) -> list[str]:
    return [str(item) for item in _list(value) if _text(item)]


def diff_zahlen(diff: Mapping[str, object]) -> list[dict[str, object]]:
    """Contracts for ``deck_diff.diff_impact``: list counts (EXAKT) and the source-deck share of
    each added, removed or changed card (GEZÄHLT, only where the cohort size ``of`` is known).

    Removed cards are counted in the source decks of the base's commander, added and changed
    cards in those of the current list's commander; the side and the commander stand in
    ``kohorte`` and ``quelle``, so two populations never share one label."""
    out: list[dict[str, object]] = []
    list_source = "Deckliste (Basis und aktuell)"
    overlap = _mapping(diff.get("overlap"))
    for key, label in (
        ("shared_slots", "Gemeinsame Kartenplätze"),
        ("base_slots", "Kartenplätze Basis"),
        ("target_slots", "Kartenplätze aktuell"),
    ):
        if key in overlap:
            _try(
                out,
                f"overlap.{key}",
                label,
                _int_or_none(overlap.get(key)),
                klasse=EXAKT,
                einheit="Anzahl",
                quelle=list_source,
            )
    for key, entry in _mapping(diff.get("curve_deltas")).items():
        sides = _mapping(entry)
        for side, label in (("base", "Basis"), ("target", "aktuell")):
            _try(
                out,
                f"curve.{key}.{side}",
                f"Karten mit Manawert {key}{'+' if key == '7' else ''} ({label})",
                _int_or_none(sides.get(side)),
                klasse=EXAKT,
                einheit="Anzahl",
                quelle=list_source,
            )
    for colour, entry in _mapping(diff.get("colour_deltas")).items():
        row = _mapping(entry)
        for key, label in (
            ("base_pips", "Symbole Basis"),
            ("target_pips", "Symbole aktuell"),
            ("base_sources", "Land-Quellen Basis"),
            ("target_sources", "Land-Quellen aktuell"),
        ):
            _try(
                out,
                f"colour.{colour}.{key}",
                f"{label} ({colour})",
                _int_or_none(row.get(key)),
                klasse=EXAKT,
                einheit="Anzahl",
                quelle=list_source,
            )
    combo = _mapping(diff.get("combo_delta"))
    for key, listed_key, label in (
        ("base_complete", "base_listed", "Vollständige gelistete Kombos Basis"),
        ("target_complete", "listed", "Vollständige gelistete Kombos aktuell"),
    ):
        if key in combo:
            listed = _int_or_none(combo.get(listed_key))
            complete = _int_or_none(combo.get(key))
            _try(
                out,
                f"combos.{key}",
                label,
                complete,
                klasse=EXAKT,
                einheit="Anzahl",
                quelle="Deckliste gegen die gespeicherte Kombo-Liste",
                n=complete if listed else None,
                N=listed if listed else None,
                bezug="Kombos (vollständig / gelistet)" if listed else None,
            )
    cohort = _mapping(diff.get("cohort"))
    cohort_key = str(cohort.get("key") or "")
    commanders = _mapping(diff.get("commanders"))
    for group in ("added", "removed", "changed"):
        side, side_text = ("base", "der Basis") if group == "removed" else ("target", "aktuell")
        names = " + ".join(_names(commanders.get(side))) or "Commander unbekannt"
        for item in _list(diff.get(group)):
            card = _mapping(item)
            of = _int_or_none(card.get("of"))
            if of is None or not cohort_key:
                continue  # no source decks of the commander: no number exists, nothing is shown
            decks = _int_or_none(card.get("decks"))
            _try(
                out,
                f"freq.{group}.{card.get('card_id')}",
                f"Quelldecks mit {card.get('name')}",
                (decks / of) if decks is not None and of else None,
                klasse=GEZAEHLT,
                einheit="Anteil",
                quelle=f"Korpus-Quelldecks des Commanders {side_text} ({names})",
                n=decks,
                N=of,
                bezug="Quelldecks (mit der Karte / Kohorte)",
                kohorte=f"{cohort_key} · {names}",
            )
    return out


def outcomes_zahlen(table: Mapping[str, object]) -> list[dict[str, object]]:
    """Contracts for ``/api/outcomes``: per card of the table the rate with and without the card
    in the first dealt hand and their difference (SIMULIERT), with the card's status and reason
    and the table's warnings as ``hinweise``. The deck state is unknown (``None``) until the
    game logs carry the deck hash per seat (B1, #1657)."""
    out: list[dict[str, object]] = []
    deck_id = str(table.get("deck_id") or "")
    pilots = _names(table.get("pilots"))
    source = "Studio-Spielprotokolle (erste gezogene Hand)"
    table_notes = _names(table.get("warnings"))
    states = _names(table.get("bridge_qualification_states"))
    if states:
        table_notes.append(f"Bridge-Zustand: {', '.join(states)}")
    for item in _list(table.get("cards")):
        card = _mapping(item)
        name = str(card.get("card") or "")
        total = _int_or_none(card.get("games_total"))
        if not name or total is None:
            continue
        notes = [f"Status {card.get('status')}"] if _text(card.get("status")) else []
        if _text(card.get("reason")):
            notes.append(str(card.get("reason")))
        notes += table_notes
        common: dict[str, object] = {
            "klasse": SIMULIERT,
            "quelle": source,
            "N": total,
            "kohorte": f"Deck {deck_id}" if deck_id else None,
            "stand_hash": None,
            "pilot": PILOT_KONSTANTE,
            "piloten": pilots,
            "hinweise": notes,
        }
        _try(
            out,
            f"outcome.{name}.rate_in",
            f"Siegquote mit {name} in der ersten Hand",
            _float_or_none(card.get("rate_in")),
            einheit="Anteil",
            n=_int_or_none(card.get("games_in_first_hand")),
            bezug="Partien (mit der Karte in der ersten Hand / alle)",
            intervall=_interval(card.get("rate_in_ci95")),
            **common,
        )
        _try(
            out,
            f"outcome.{name}.rate_not",
            f"Siegquote ohne {name} in der ersten Hand",
            _float_or_none(card.get("rate_not")),
            einheit="Anteil",
            n=_int_or_none(card.get("games_not_in_first_hand")),
            bezug="Partien (ohne die Karte in der ersten Hand / alle)",
            intervall=_interval(card.get("rate_not_ci95")),
            **common,
        )
        difference = _float_or_none(card.get("difference_pp"))
        _try(
            out,
            f"outcome.{name}.difference_pp",
            f"Differenz mit/ohne {name} in der ersten Hand",
            difference,
            einheit="pp",
            n=total if difference is not None else None,
            bezug="Partien (verglichen / alle)",
            intervall=_interval(card.get("difference_ci95_pp")),
            **common,
        )
    return out


def series_zahlen(
    payload: Mapping[str, object], hashes: Mapping[str, str]
) -> list[dict[str, object]]:
    """Contracts for ``/api/decks/{id}/series``: the stored difference B - A of every series that
    counts as a result (SIMULIERT, n = completed pairs, N = planned pairs). A series that does not
    count, or whose planned pairs are unknown, gets no contract: its number does not exist.
    ``hashes`` maps revision ids to deck hashes; a reference deck has none (``None`` = unknown)."""
    out: list[dict[str, object]] = []
    for item in _list(payload.get("series")):
        series = _mapping(item)
        planned = _int_or_none(series.get("pairs_planned"))
        if not series.get("counts_as_result") or planned is None:
            continue
        created = series.get("created_at")
        notes = [f"Stopp: {series.get('stop_reason')}"] if _text(series.get("stop_reason")) else []
        if _text(series.get("slot_alignment_state")):
            notes.append(f"Ausrichtung: {series.get('slot_alignment_state')}")
        states = _names(series.get("bridge_qualification_states"))
        if states:
            notes.append(f"Bridge-Zustand: {', '.join(states)}")
        _try(
            out,
            f"series.{series.get('series_id')}.difference_pp",
            "Differenz (B - A) der Paar-Serie",
            _float_or_none(series.get("difference_pp")),
            klasse=SIMULIERT,
            einheit="pp",
            quelle="gespeicherte Paar-Serie (gleiche Seeds, Sitze und Gegner-Tisch)",
            n=_int_or_none(series.get("pairs_completed")),
            N=planned,
            bezug="Paare (abgeschlossen / geplant)",
            intervall=_interval(series.get("difference_ci95_pp")),
            kohorte=f"Tisch {series.get('pod')}" if _text(series.get("pod")) else None,
            stand_datum=created[:10] if isinstance(created, str) and created else None,
            stand_hash=hashes.get(str(series.get("variant_ref"))),
            basis_hash=hashes.get(str(series.get("base_ref"))),
            gepaart=True,
            pilot=PILOT_KONSTANTE,
            piloten=_names(series.get("pilots")),
            hinweise=notes,
        )
    return out


def castability_zahlen(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Contracts for ``/api/castability``: every probability is exact (hypergeometric)."""
    out: list[dict[str, object]] = []
    source = "Exakte Hypergeometrie aus der Deckliste (Karsten 2022)"
    for item in _list(payload.get("requirements")):
        requirement = _mapping(item)
        key = f"{requirement.get('label')}.{requirement.get('turn')}"
        for field, label in (
            ("p_land_drops", "Land-Drops bis Zug"),
            ("p_colours_given_lands", "Farben bei genug Land-Drops"),
        ):
            _try(
                out,
                f"cast.{key}.{field}",
                f"{label} ({requirement.get('label')}, Zug {requirement.get('turn')})",
                _float_or_none(requirement.get(field)),
                klasse=EXAKT,
                einheit="Anteil",
                quelle=source,
            )
    hand = _mapping(payload.get("opening_hand"))
    if hand:
        _try(
            out,
            "cast.opening_hand.p_keepable",
            "Spielbare Starthand",
            _float_or_none(hand.get("p_keepable")),
            klasse=EXAKT,
            einheit="Anteil",
            quelle=source,
        )
    roles = _mapping(payload.get("hand_roles"))
    for item in _list(roles.get("roles")):
        role = _mapping(item)
        for hand_item in _list(role.get("hands")):
            draws = _mapping(hand_item)
            for field, label in (("p_at_least_1", "mindestens eine"), ("p_none", "keine")):
                _try(
                    out,
                    f"cast.role.{role.get('role')}.{draws.get('draws')}.{field}",
                    f"{label} Karte der Rolle {role.get('role')} in {draws.get('draws')} Karten",
                    _float_or_none(draws.get(field)),
                    klasse=EXAKT,
                    einheit="Anteil",
                    quelle="Exakte Hypergeometrie aus der Deckliste und den Rollen-Marken",
                )
    return out
