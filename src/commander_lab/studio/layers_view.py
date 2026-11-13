"""The rating layers of the tier list as the page shows them: store access around ``layers.py``.

Reads the oracle text of the pool cards (``card_fact``, all faces) and the Playgroup atlas rows
(``playgroup_card_atlas``, multiplayer) and hands both to the pure ``layers.compute_layers``.

An atlas row belongs to the pool card that has its **oracle id**; failing that, to the card
whose exact oracle name (or engine name) it is; failing that, to the card whose FRONT face it
is (the same ``name_claims`` discipline as every signal; a name several cards claim at the best
level belongs to none). Only atlas rows of the commander's own legal pool can match.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping

from .layers import AtlasRecord, LayerCard
from .store import StudioStore

# claim key -> [(claim kind, card id)], as built by ``strength_view._claim_index``
Claims = Mapping[str, list[tuple[int, str]]]

_ORACLE_ID_KIND = -1


def pool_texts(store: StudioStore, card_ids: Collection[str]) -> dict[str, str | None]:
    """The oracle text of every given card, all faces joined; ``None`` when the store has none."""
    wanted = set(card_ids)
    return {
        str(row["card_id"]): row["oracle_text"]
        for row in store.connection.execute("SELECT card_id, oracle_text FROM card_fact")
        if str(row["card_id"]) in wanted
    }


def _optional_int(value: object) -> int | None:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _optional_float(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def atlas_records(
    store: StudioStore, oracle_ids: Mapping[str, str | None], claims: Claims
) -> dict[str, AtlasRecord]:
    """The atlas record of every pool card that has one (card id -> record).

    ``oracle_ids`` maps a pool card id to its oracle id. When several rows resolve to one
    card, the oracle id match wins, then the better name claim, then the smaller stored name."""
    by_oracle = {oracle: card for card, oracle in oracle_ids.items() if oracle}
    best: dict[str, tuple[int, str, AtlasRecord]] = {}
    rows = store.connection.execute(
        "SELECT oracle_id, card_name, on_curve_pct, on_curve_count, on_curve_denominator, "
        "drawn_to_played_pct, ever_drawn_n, first_cast_n, battlefield_survival_pct, "
        "reached_battlefield_n, still_on_board_at_end_n, insufficient_sample "
        "FROM playgroup_card_atlas WHERE format_mode = 'multiplayer' ORDER BY card_name"
    ).fetchall()
    for row in rows:
        name = str(row["card_name"])
        card_id = by_oracle.get(str(row["oracle_id"]))
        kind = _ORACLE_ID_KIND
        if card_id is None:
            found = claims.get(name.casefold())
            if not found:
                continue
            kind = min(item[0] for item in found)
            owners = sorted({card for item_kind, card in found if item_kind == kind})
            if len(owners) > 1:
                continue
            card_id = owners[0]
        record = AtlasRecord(
            on_curve_pct=_optional_float(row["on_curve_pct"]),
            on_curve_count=_optional_int(row["on_curve_count"]),
            on_curve_denominator=_optional_int(row["on_curve_denominator"]),
            drawn_to_played_pct=_optional_float(row["drawn_to_played_pct"]),
            ever_drawn_n=_optional_int(row["ever_drawn_n"]),
            first_cast_n=_optional_int(row["first_cast_n"]),
            battlefield_survival_pct=_optional_float(row["battlefield_survival_pct"]),
            reached_battlefield_n=_optional_int(row["reached_battlefield_n"]),
            still_on_board_at_end_n=_optional_int(row["still_on_board_at_end_n"]),
            insufficient_sample=bool(row["insufficient_sample"]),
        )
        current = best.get(card_id)
        if current is None or (kind, name) < (current[0], current[1]):
            best[card_id] = (kind, name, record)
    return {card_id: item[2] for card_id, item in best.items()}


def layer_cards(
    store: StudioStore,
    names: Mapping[str, str],
    type_lines: Mapping[str, str],
    unranked: Mapping[str, str],
) -> dict[str, LayerCard]:
    """The ``LayerCard`` of every pool card (``names``: card id -> display name)."""
    texts = pool_texts(store, names)
    return {
        card_id: LayerCard(
            name=name,
            text=texts.get(card_id),
            type_line=type_lines.get(card_id, ""),
            unranked=unranked.get(card_id),
        )
        for card_id, name in names.items()
    }
