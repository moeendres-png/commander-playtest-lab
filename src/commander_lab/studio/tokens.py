"""Local Scryfall-derived token overview per deck (#1450).

Derives which tokens a deck's cards create strictly from the local Scryfall bulk snapshot
(``scryfall_card_token`` + ``scryfall_token``), offline and with zero network calls at runtime.
Cards whose token creation cannot be resolved from the local snapshot (missing oracle text or
oracle text mentioning token creation without ``all_parts`` token links) are reported explicitly
as ``UNKNOWN`` in ``unresolved_creators`` and never guessed or counted as zero.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from .decks import RevisionCard
from .store import DataClass, StudioStore

TOKEN_OVERVIEW_SCHEMA = "commander_studio.token_overview.v1"

# Matches cards whose oracle text indicates token creation when no Scryfall all_parts link exists.
_TOKEN_CREATION_RE = re.compile(
    r"\b(?:create|creates|creating)\b[^.;\n]*\btokens?\b"
    r"|\bput\b[^.;\n]*\btokens?\b[^.;\n]*\bonto the battlefield\b"
    r"|\binvestigate\b|\bamass\b|\bincubate\b|\bliving weapon\b"
    r"|\bfor mirrodin!\b|\bjob select\b|\boffspring\b|\bfabricat(?:e|es)\b"
    r"|\bafterlife\b|\bembalm\b|\beternalize\b|\bencore\b|\bmyriad\b|\bsquad\b",
    re.IGNORECASE,
)


def deck_tokens(store: StudioStore, cards: Sequence[RevisionCard]) -> dict[str, object]:
    """Return the local token overview for ``cards`` with explicit denominators and UNKNOWN list."""
    db = store.connection
    merged_qty: dict[str, int] = {}
    zone_by_cid: dict[str, str] = {}
    for entry in cards:
        if entry.quantity <= 0:
            continue
        merged_qty[entry.card_id] = merged_qty.get(entry.card_id, 0) + entry.quantity
        if entry.zone == "commander" or entry.card_id not in zone_by_cid:
            zone_by_cid[entry.card_id] = entry.zone

    if not merged_qty:
        return {
            "schema": TOKEN_OVERVIEW_SCHEMA,
            "data_class": DataClass.DERIVED_DESCRIPTIVE.value,
            "tokens": [],
            "unresolved_creators": [],
            "counts": {
                "deck_cards_with_oracle": {"numerator": 0, "denominator": 0},
                "resolved_creator_cards": {"numerator": 0, "denominator": 0},
                "distinct_tokens": 0,
                "unresolved_creator_cards": 0,
            },
        }

    card_ids = sorted(merged_qty.keys())
    marks = ", ".join("?" for _ in card_ids)
    fact_rows = db.execute(
        f"SELECT card_id, oracle_name, oracle_id, type_line, oracle_text, fact_source "
        f"FROM card_fact WHERE card_id IN ({marks})",
        card_ids,
    ).fetchall()
    fact_by_cid = {str(r["card_id"]): r for r in fact_rows}

    oracle_ids = sorted(
        {
            str(r["oracle_id"])
            for r in fact_rows
            if r["oracle_id"] is not None and str(r["oracle_id"])
        }
    )

    links_by_oracle: dict[str, list[dict[str, object]]] = {}
    if oracle_ids:
        omarks = ", ".join("?" for _ in oracle_ids)
        link_rows = db.execute(
            f"SELECT ct.oracle_id, ct.token_scryfall_id, ct.token_name, ct.token_type_line, "
            f"ct.token_uri, t.scryfall_id AS matched_id, t.type_line AS full_type_line, "
            f"t.power, t.toughness, t.colors, t.oracle_text AS token_oracle_text, t.image_front "
            f"FROM scryfall_card_token ct "
            f"LEFT JOIN scryfall_token t ON t.scryfall_id = ct.token_scryfall_id "
            f"WHERE ct.oracle_id IN ({omarks}) "
            f"ORDER BY ct.token_name, ct.token_scryfall_id",
            oracle_ids,
        ).fetchall()

        # Fallback lookup by token name when the exact token printing id was not in scryfall_token
        fallback_by_name: dict[str, dict[str, object]] = {}
        missing_names = sorted(
            {str(r["token_name"]) for r in link_rows if r["matched_id"] is None and r["token_name"]}
        )
        if missing_names:
            nmarks = ", ".join("?" for _ in missing_names)
            for trow in db.execute(
                f"SELECT scryfall_id, name, type_line, power, toughness, colors, "
                f"oracle_text, image_front FROM scryfall_token WHERE name IN ({nmarks}) "
                f"ORDER BY scryfall_id",
                missing_names,
            ).fetchall():
                tname = str(trow["name"])
                if tname not in fallback_by_name:
                    fallback_by_name[tname] = dict(trow)

        for r in link_rows:
            oid = str(r["oracle_id"])
            tname = str(r["token_name"])
            if r["matched_id"] is not None:
                type_line = str(r["full_type_line"] or r["token_type_line"] or "")
                power = str(r["power"]) if r["power"] is not None else None
                toughness = str(r["toughness"]) if r["toughness"] is not None else None
                colors = str(r["colors"] or "")
                oracle_text = str(r["token_oracle_text"] or "")
                image_front = str(r["image_front"]) if r["image_front"] is not None else None
                detail_status = "FULL"
            elif tname in fallback_by_name:
                fb = fallback_by_name[tname]
                type_line = str(fb.get("type_line") or r["token_type_line"] or "")
                power = str(fb["power"]) if fb.get("power") is not None else None
                toughness = str(fb["toughness"]) if fb.get("toughness") is not None else None
                colors = str(fb.get("colors") or "")
                oracle_text = str(fb.get("oracle_text") or "")
                image_front = str(fb["image_front"]) if fb.get("image_front") is not None else None
                detail_status = "FULL"
            else:
                type_line = str(r["token_type_line"] or "")
                power = None
                toughness = None
                colors = ""
                oracle_text = ""
                image_front = None
                detail_status = "PARTIAL_ALL_PARTS"

            links_by_oracle.setdefault(oid, []).append(
                {
                    "token_scryfall_id": str(r["token_scryfall_id"] or ""),
                    "name": tname,
                    "type_line": type_line,
                    "power": power,
                    "toughness": toughness,
                    "colors": colors,
                    "oracle_text": oracle_text,
                    "image_front": image_front,
                    "detail_status": detail_status,
                }
            )

    token_groups: dict[tuple[str, str, str | None, str | None, str, str], dict[str, object]] = {}
    token_creators: dict[
        tuple[str, str, str | None, str | None, str, str], dict[str, dict[str, object]]
    ] = {}
    resolved_creator_cids: set[str] = set()
    unresolved_creators: list[dict[str, object]] = []
    cards_with_oracle = 0

    for cid in card_ids:
        qty = merged_qty[cid]
        zone = zone_by_cid[cid]
        fact = fact_by_cid.get(cid)
        if fact is None:
            unresolved_creators.append(
                {
                    "card_id": cid,
                    "name": cid,
                    "quantity": qty,
                    "zone": zone,
                    "status": DataClass.UNKNOWN.value,
                    "reason_code": "CARD_NOT_IN_STORE",
                    "reason": "Karte nicht im lokalen Store gefunden",
                }
            )
            continue

        cname = str(fact["oracle_name"])
        oid = str(fact["oracle_id"]) if fact["oracle_id"] is not None else ""
        otext = str(fact["oracle_text"]) if fact["oracle_text"] is not None else None
        fsource = str(fact["fact_source"] or "workbook")

        if fsource == "scryfall" or (otext is not None and otext.strip() != ""):
            cards_with_oracle += 1

        token_list = links_by_oracle.get(oid, []) if oid else []
        if token_list:
            resolved_creator_cids.add(cid)
            for tok in token_list:
                key = (
                    str(tok["name"]),
                    str(tok["type_line"]),
                    str(tok["power"]) if tok["power"] is not None else None,
                    str(tok["toughness"]) if tok["toughness"] is not None else None,
                    str(tok["colors"]),
                    str(tok["oracle_text"]),
                )
                if key not in token_groups:
                    pwr = key[2]
                    tgh = key[3]
                    token_groups[key] = {
                        "name": key[0],
                        "type_line": key[1],
                        "power": pwr,
                        "toughness": tgh,
                        "pt": f"{pwr}/{tgh}" if pwr is not None and tgh is not None else None,
                        "colors": key[4],
                        "oracle_text": key[5],
                        "image_front": tok["image_front"],
                        "detail_status": tok["detail_status"],
                    }
                elif (
                    token_groups[key].get("image_front") is None and tok["image_front"] is not None
                ):
                    token_groups[key]["image_front"] = tok["image_front"]
                creators_for_key = token_creators.setdefault(key, {})
                creators_for_key[cid] = {
                    "card_id": cid,
                    "name": cname,
                    "quantity": qty,
                    "zone": zone,
                }
            continue

        # No Scryfall all_parts token link for this card: check whether its token status is UNKNOWN
        if otext is None or (fsource != "scryfall" and otext.strip() == ""):
            unresolved_creators.append(
                {
                    "card_id": cid,
                    "name": cname,
                    "quantity": qty,
                    "zone": zone,
                    "status": DataClass.UNKNOWN.value,
                    "reason_code": "NO_ORACLE_TEXT",
                    "reason": "Kein Oracle-Text im lokalen Scryfall-Snapshot hinterlegt",
                }
            )
        elif _TOKEN_CREATION_RE.search(otext):
            unresolved_creators.append(
                {
                    "card_id": cid,
                    "name": cname,
                    "quantity": qty,
                    "zone": zone,
                    "status": DataClass.UNKNOWN.value,
                    "reason_code": "ORACLE_MENTIONS_TOKEN_WITHOUT_ALL_PARTS",
                    "reason": (
                        "Oracle-Text erwähnt Token-Erzeugung, aber keine Token-Verknüpfung "
                        "(all_parts) im lokalen Scryfall-Snapshot"
                    ),
                }
            )

    tokens_out: list[dict[str, object]] = []
    for key in sorted(token_groups.keys(), key=lambda k: (k[0].casefold(), k[1].casefold())):
        grp = dict(token_groups[key])
        creating_list = sorted(
            token_creators.get(key, {}).values(),
            key=lambda item: str(item["name"]).casefold(),
        )
        grp["creating_cards"] = creating_list
        grp["creator_count"] = len(creating_list)
        grp["creator_cards_total_qty"] = sum(
            int(item["quantity"])  # type: ignore[call-overload]
            for item in creating_list
        )
        tokens_out.append(grp)

    unresolved_creators.sort(key=lambda item: str(item["name"]).casefold())
    total_creator_candidates = len(resolved_creator_cids) + len(unresolved_creators)

    return {
        "schema": TOKEN_OVERVIEW_SCHEMA,
        "data_class": DataClass.DERIVED_DESCRIPTIVE.value,
        "tokens": tokens_out,
        "unresolved_creators": unresolved_creators,
        "counts": {
            "deck_cards_with_oracle": {
                "numerator": cards_with_oracle,
                "denominator": len(card_ids),
            },
            "resolved_creator_cards": {
                "numerator": len(resolved_creator_cids),
                "denominator": total_creator_candidates,
            },
            "distinct_tokens": len(tokens_out),
            "unresolved_creator_cards": len(unresolved_creators),
        },
    }


def revision_tokens(store: StudioStore, revision_id: str) -> dict[str, object]:
    """Return the local token overview for a stored deck revision."""
    rows = store.connection.execute(
        "SELECT card_id, quantity, zone FROM deck_revision_card WHERE revision_id = ?",
        (revision_id,),
    ).fetchall()
    if not rows:
        exists = store.connection.execute(
            "SELECT 1 FROM deck_revision WHERE revision_id = ?", (revision_id,)
        ).fetchone()
        if exists is None:
            raise KeyError(revision_id)
    cards = [RevisionCard(str(r["card_id"]), int(r["quantity"]), str(r["zone"])) for r in rows]
    result = deck_tokens(store, cards)
    result["revision_id"] = revision_id
    return result
