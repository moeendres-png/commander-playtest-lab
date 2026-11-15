"""Generate a role file from the deterministic Oracle-text rules (issue #1379).

Applies ``commander_lab.studio.roles.classify_oracle_roles`` to every card of a
universe taken from a built Studio store and writes a ``studio-roles-2`` file
with origin ``ORACLE_TEXT_REVIEW`` — the same provenance class as
``roles_s5_oracle_expansion.json`` (#1353 part C), which this script regenerates,
plus the corpus-wide file ``roles_s6_oracle_corpus.json``.

Universes:

* ``collection``: the cards of the store's ``card`` table (the 1,655 collection
  cards), facts from that table — the s5 scope ``COLLECTION1655_RULES_1``.
* ``corpus``: the distinct oracle ids of the canonical Chulane corpus (the
  repo's own universe resolution, commander-bound, duplicates counted once),
  facts from ``scryfall_card`` — scope ``CHULANE_CORPUS_RULES_1``.

The output is deterministic: roles in ``roles.ROLES`` order, oracle ids sorted.
Cards whose facts are missing from the store are reported on stderr and left
out; nothing is guessed for them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from commander_lab.studio import roles, universe
from commander_lab.studio.store import StudioStore

COMMANDER = "Chulane, Teller of Tales"
SCOPES = {
    "collection": "COLLECTION1655_RULES_1",
    "corpus": "CHULANE_CORPUS_RULES_1",
}
SOURCE_TEXT = {
    "collection": (
        "Deterministic Oracle text rules (commander_lab.studio.roles."
        "classify_oracle_roles) applied to the 1,655 collection cards "
        "(issue #1353 part C, regenerated under #1379)"
    ),
    "corpus": (
        "Deterministic Oracle text rules (commander_lab.studio.roles."
        "classify_oracle_roles) applied to the distinct cards of the "
        "canonical Chulane corpus (issue #1379)"
    ),
}


def _collection_facts(store: StudioStore) -> dict[str, tuple[str, str]]:
    return {
        str(oracle_id): (str(type_line), str(oracle_text))
        for oracle_id, type_line, oracle_text in store.connection.execute(
            "SELECT oracle_id, type_line, oracle_text FROM card"
        )
    }


def _corpus_facts(store: StudioStore) -> tuple[dict[str, tuple[str, str]], int]:
    deck_ids = set(universe.resolve_universe(store, {"commanders": [COMMANDER]}))
    oracle_ids: set[str] = set()
    for deck_id, oracle_id in store.connection.execute(
        "SELECT deck_id, oracle_id FROM corpus_deck_card "
        "WHERE section IN ('main', 'mainboard') AND quantity > 0"
    ):
        if str(deck_id) in deck_ids and oracle_id:
            oracle_ids.add(str(oracle_id))
    facts = {
        str(oracle_id): (str(type_line), str(oracle_text))
        for oracle_id, type_line, oracle_text in store.connection.execute(
            "SELECT oracle_id, type_line, oracle_text FROM scryfall_card"
        )
    }
    missing = oracle_ids - set(facts)
    if missing:
        print(
            f"warning: {len(missing)} corpus cards have no Scryfall facts in the "
            "store and are left out",
            file=sys.stderr,
        )
    return {oid: facts[oid] for oid in sorted(oracle_ids & set(facts))}, len(oracle_ids)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Studio data folder (built store)")
    parser.add_argument("--universe", choices=sorted(SCOPES), required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--fetched-at", default="2026-11-15")
    args = parser.parse_args()

    store = StudioStore.open(Path(args.data))
    try:
        if args.universe == "collection":
            facts = _collection_facts(store)
            universe_size = len(facts)
        else:
            facts, universe_size = _corpus_facts(store)
    finally:
        store.close()

    by_role: dict[str, list[str]] = {}
    for oracle_id in sorted(facts):
        type_line, oracle_text = facts[oracle_id]
        for role in roles.classify_oracle_roles(type_line, oracle_text):
            by_role.setdefault(role, []).append(oracle_id)
    payload = {
        "schema": roles.ROLES_SCHEMA,
        "source": SOURCE_TEXT[args.universe],
        "role_origin": roles.ORIGIN_ORACLE_TEXT,
        "fetched_at": args.fetched_at,
        "scope": {
            "mode": roles.FULL_SNAPSHOT,
            "key": SCOPES[args.universe],
            "completeness": "COMPLETE_FOR_SCOPE",
        },
        "roles": {role: by_role[role] for role in sorted(by_role)},
    }
    out = Path(args.out)
    out.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    claims = sum(len(ids) for ids in by_role.values())
    print(
        f"{args.universe}: {universe_size} cards in universe, {len(facts)} with facts, "
        f"{claims} claims over {len(by_role)} roles -> {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
