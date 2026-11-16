"""Combo shells (#1366): deduplicate Commander Spellbook variants onto the
combo they belong to.

The spellbook file (``spellbook_card_links.csv``) counts *variants*: every
concrete way to assemble a combo, so one combo whose flexible slot has 19
printed equivalents inflates a card's count 19-fold (Pitiless Plunderer:
3,282 variants). The bulk export names the combo behind each variant in the
variant's ``of`` field; that combo is the *shell* of this module. Counting
distinct shells instead of variants removes exactly the inflation the
spellbook itself considers identical — same recipe, same produced features,
same colour identity. Shells are not merged any further: two shells that
differ only in one swapped card (Cloudshift vs. Essence Flux) stay two
shells, because the source keeps them apart (different identity or results).

A variant qualifies for a commander when its own colour identity fits the
commander's identity (the identity varies *between the variants of one
shell*, so the test is per variant, never per shell) and every card it uses
is in the commander's legal pool. Generic template slots (``requires``) have
no concrete card: they cannot fail the pool test, but they count towards the
combo's card count, like the importer already counts them for variants.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, replace

# Chulane, Teller of Tales — the one commander this package scopes to (#1363).
CHULANE_IDENTITY = frozenset({"W", "U", "G"})
CHULANE_NAME = "Chulane, Teller of Tales"
# The export writes the identity of a colourless variant as "C": no colour at all.
COLOURLESS = "C"


@dataclass(frozen=True)
class VariantFacts:
    """The shell facts of one spellbook variant, read from the bulk export."""

    shell_id: int
    card_names: tuple[str, ...]
    card_count: int
    identity: frozenset[str] | None
    with_commander: bool


@dataclass(frozen=True)
class ShellCounts:
    """Distinct qualifying shells of one card, split by shape."""

    shells: int
    two_card: int
    three_plus: int
    with_commander: int
    shell_ids: tuple[int, ...]


def _combo_ids(record: Mapping[str, object]) -> tuple[int, ...]:
    """The ids of the combos a bulk variant record belongs to (``of``)."""
    of = record.get("of")
    if not isinstance(of, list):
        return ()
    return tuple(
        cid
        for entry in of
        if isinstance(entry, Mapping)
        and isinstance(cid := entry.get("id"), int)
        and not isinstance(cid, bool)
    )


def _shell_roots(records: Iterable[Mapping[str, object]]) -> dict[int, int]:
    """Combo id → shell id. A variant can belong to several combos (a specific
    recipe and the generic one it instantiates); combos that share a variant are
    one shell, and the shell is named by the smallest combo id of the group, so
    the result does not depend on the order of ``of`` or of the variants."""
    parent: dict[int, int] = {}

    def find(node: int) -> int:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for record in records:
        ids = _combo_ids(record)
        for other in ids[1:]:
            low, high = sorted((find(ids[0]), find(other)))
            parent[high] = low
        for node in ids:
            find(node)
    return {node: find(node) for node in list(parent)}


def _facts(record: Mapping[str, object], shell: int) -> VariantFacts:
    """The facts of one bulk variant record, assigned to ``shell``."""
    uses = record.get("uses")
    requires = record.get("requires")
    uses = uses if isinstance(uses, list) else []
    requires = requires if isinstance(requires, list) else []
    names: list[str] = []
    commander = False
    for entry in uses:
        if not isinstance(entry, Mapping):
            continue
        card = entry.get("card")
        if isinstance(card, Mapping) and isinstance(card.get("name"), str):
            names.append(card["name"])
        if entry.get("mustBeCommander") is True:
            commander = True
    for entry in requires:
        if isinstance(entry, Mapping) and entry.get("mustBeCommander") is True:
            commander = True
    raw_identity = record.get("identity")
    cleaned_identity = raw_identity.strip() if isinstance(raw_identity, str) else ""
    identity = frozenset(cleaned_identity) - {COLOURLESS} if cleaned_identity else None
    return VariantFacts(
        shell_id=shell,
        card_names=tuple(names),
        card_count=len(uses) + len(requires),
        identity=identity,
        with_commander=commander,
    )


def build_variant_index(
    records: Iterable[Mapping[str, object]],
    aliases: Iterable[Mapping[str, object]],
) -> dict[str, VariantFacts]:
    """Variant id → facts, for the bulk export's variants and its alias table.

    The link file is a snapshot: a variant it names may since have been
    renamed, which the export's ``aliases`` map to the current id (a retired
    variant has no successor and resolves to nothing)."""
    records = list(records)
    roots = _shell_roots(records)
    index: dict[str, VariantFacts] = {}
    for record in records:
        variant_id = record.get("id")
        ids = _combo_ids(record)
        if isinstance(variant_id, str) and ids:
            index[variant_id] = _facts(record, roots[ids[0]])
    for alias in aliases:
        old = alias.get("id")
        successor = alias.get("variant")
        if not isinstance(old, str) or not isinstance(successor, Mapping):
            continue
        new = successor.get("id")
        if isinstance(new, str) and new in index:
            index.setdefault(old, index[new])
    return index


def count_shells(
    variant_ids: Iterable[str],
    index: Mapping[str, VariantFacts],
    pool: Collection[str],
    *,
    identity: frozenset[str] = CHULANE_IDENTITY,
    commander: str = CHULANE_NAME,
) -> ShellCounts:
    """The distinct shells of one card: a shell counts once, however many of
    the card's variants belong to it, and only through a variant that fits the
    commander's identity with every used card in the pool. The card count of a
    shell is the smallest count among its qualifying variants (the slots of a
    shell are fixed, so its variants agree; the minimum keeps a disagreeing
    snapshot deterministic). A shell involves the commander when a qualifying
    variant flags a card as ``mustBeCommander`` or uses the commander's own
    card: she is in the command zone, so such a combo needs her."""
    by_shell: dict[int, VariantFacts] = {}
    for variant_id in variant_ids:
        facts = index.get(variant_id.strip())
        if facts is None:
            continue
        if facts.identity is None or not facts.identity <= identity:
            continue
        if any(name not in pool for name in facts.card_names):
            continue
        facts = replace(facts, with_commander=facts.with_commander or commander in facts.card_names)
        current = by_shell.get(facts.shell_id)
        if current is None:
            by_shell[facts.shell_id] = facts
        elif facts.card_count < current.card_count:
            by_shell[facts.shell_id] = replace(
                facts, with_commander=facts.with_commander or current.with_commander
            )
        elif facts.with_commander and not current.with_commander:
            by_shell[facts.shell_id] = replace(current, with_commander=True)
    shells = tuple(sorted(by_shell))
    return ShellCounts(
        shells=len(shells),
        two_card=sum(1 for facts in by_shell.values() if facts.card_count == 2),
        three_plus=sum(1 for facts in by_shell.values() if facts.card_count >= 3),
        with_commander=sum(1 for facts in by_shell.values() if facts.with_commander),
        shell_ids=shells,
    )


TEMPLATE_SCHEMA = "studio-spellbook-templates-1"


def _produces_names(record: Mapping[str, object]) -> list[str]:
    produces = record.get("produces")
    if not isinstance(produces, list):
        return []
    out: list[str] = []
    for entry in produces:
        if not isinstance(entry, Mapping):
            continue
        feature = entry.get("feature")
        if isinstance(feature, Mapping) and isinstance(feature.get("name"), str):
            name = feature["name"].strip()
            if name and name not in out:
                out.append(name)
    return out


def build_template_snapshot(
    records: Iterable[Mapping[str, object]],
    pool: Collection[str],
    *,
    identity: frozenset[str] = CHULANE_IDENTITY,
    commander: str = CHULANE_NAME,
    version: str | None = None,
    timestamp: str | None = None,
    bulk_sha256: str | None = None,
) -> dict[str, object]:
    """Extract pool-qualifying Spellbook shells and template-slot shells (#1417, B-7).

    Keeps:
    1. ``pool_shells``: every Spellbook variant fitting ``identity`` whose concrete ``uses``
       are all in ``pool`` (deduped by shell + concrete card set).
    2. ``template_shells``: every Spellbook variant fitting ``identity`` that carries at
       least one ``requires`` template slot and has at least one ``uses`` card in ``pool``
       (ordered fewest missing concrete cards first, deterministic tie-break).
    """
    record_list = list(records)
    roots = _shell_roots(record_list)
    pool_cf = {str(name).casefold(): str(name) for name in pool}
    for name in list(pool):
        text = str(name)
        if " // " in text:
            pool_cf.setdefault(text.split(" // ")[0].casefold(), text)

    pool_entries: dict[tuple[int, tuple[str, ...]], dict[str, object]] = {}
    template_entries: dict[tuple[int, tuple[str, ...], tuple[str, ...]], dict[str, object]] = {}

    for record in record_list:
        variant_id = record.get("id")
        ids = _combo_ids(record)
        if not isinstance(variant_id, str) or not ids:
            continue
        raw_identity = record.get("identity")
        cleaned_identity = raw_identity.strip() if isinstance(raw_identity, str) else ""
        if not cleaned_identity:
            continue
        var_identity = frozenset(cleaned_identity) - {COLOURLESS}
        if not var_identity <= identity:
            continue
        uses_raw = record.get("uses")
        requires_raw = record.get("requires")
        uses_list = uses_raw if isinstance(uses_raw, list) else []
        requires_list = requires_raw if isinstance(requires_raw, list) else []
        uses_names: list[str] = []
        with_cmd = False
        for entry in uses_list:
            if not isinstance(entry, Mapping):
                continue
            card = entry.get("card")
            if isinstance(card, Mapping) and isinstance(card.get("name"), str):
                cname = card["name"].strip()
                if cname:
                    uses_names.append(pool_cf.get(cname.casefold(), cname))
            if entry.get("mustBeCommander") is True:
                with_cmd = True
        if not uses_names:
            continue
        if commander in uses_names:
            with_cmd = True
        in_pool = [name for name in uses_names if name.casefold() in pool_cf]
        missing = [name for name in uses_names if name.casefold() not in pool_cf]
        shell_id = roots[ids[0]]
        produces = _produces_names(record)

        if not requires_list:
            if not missing:
                pkey = (shell_id, tuple(sorted(uses_names)))
                if pkey not in pool_entries:
                    pool_entries[pkey] = {
                        "shell_id": shell_id,
                        "variant_id": variant_id,
                        "uses": uses_names,
                        "with_commander": with_cmd,
                        "identity": "".join(sorted(var_identity)) or COLOURLESS,
                        "produces": produces,
                    }
            continue

        if not in_pool:
            continue
        parsed_reqs: list[dict[str, object]] = []
        req_sig: list[str] = []
        for req in requires_list:
            if not isinstance(req, Mapping):
                continue
            tpl = req.get("template")
            if not isinstance(tpl, Mapping):
                continue
            t_id = tpl.get("id")
            t_name = str(tpl.get("name") or "").strip() or f"Template {t_id}"
            raw_query = tpl.get("scryfallQuery")
            query = (
                str(raw_query).strip() if isinstance(raw_query, str) and raw_query.strip() else None
            )
            api_url = str(tpl.get("scryfallApi") or "").strip() or None
            qty_val = req.get("quantity")
            qty = int(qty_val) if isinstance(qty_val, int) and not isinstance(qty_val, bool) else 1
            if req.get("mustBeCommander") is True:
                with_cmd = True
            zones = req.get("zoneLocations")
            parsed_reqs.append(
                {
                    "template_id": t_id if isinstance(t_id, int) else None,
                    "name": t_name,
                    "scryfall_query": query,
                    "scryfall_api": api_url,
                    "quantity": qty,
                    "must_be_commander": bool(req.get("mustBeCommander") is True),
                    "zone_locations": [str(z) for z in zones] if isinstance(zones, list) else [],
                }
            )
            req_sig.append(f"{t_id}:{t_name}")
        if not parsed_reqs:
            continue
        tkey = (shell_id, tuple(sorted(uses_names)), tuple(sorted(req_sig)))
        if tkey not in template_entries:
            template_entries[tkey] = {
                "shell_id": shell_id,
                "variant_id": variant_id,
                "uses": uses_names,
                "in_pool": in_pool,
                "missing_from_pool": missing,
                "with_commander": with_cmd,
                "identity": "".join(sorted(var_identity)) or COLOURLESS,
                "requires": parsed_reqs,
                "produces": produces,
            }

    sorted_pool = sorted(
        pool_entries.values(),
        key=lambda item: (int(str(item["shell_id"])), str(item["variant_id"])),
    )
    sorted_templates = sorted(
        template_entries.values(),
        key=lambda item: (
            len(item["missing_from_pool"]),  # type: ignore[arg-type]
            -len(item["in_pool"]),  # type: ignore[arg-type]
            int(str(item["shell_id"])),
            str(item["variant_id"]),
        ),
    )
    return {
        "schema": TEMPLATE_SCHEMA,
        "commander": commander,
        "identity": "".join(sorted(identity)) or COLOURLESS,
        "bulk_version": version,
        "bulk_timestamp": timestamp,
        "bulk_sha256": bulk_sha256,
        "pool_shells": sorted_pool,
        "template_shells": sorted_templates,
    }
