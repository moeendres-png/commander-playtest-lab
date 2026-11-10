"""Card roles (ramp, card draw, removal ...) from the public Scryfall tagger.

The tags are labels maintained by the Scryfall community: a public statement that a card
does a certain job, not a rating and not complete. The query names only a color identity,
never a collection or a deck.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .store import DataClass, StudioStore, now_utc, sha256_file

SEARCH = "https://api.scryfall.com/cards/search"
_USER_AGENT = "CommanderStudio/0.1 (local deck builder)"

# role -> tagger tag
ROLES: dict[str, str] = {
    "ramp": "ramp",
    "mana_rock": "mana-rock",
    "mana_dork": "mana-dork",
    "land_ramp": "land-ramp",
    "card_draw": "draw",
    "card_advantage": "card-advantage",
    "cantrip": "cantrip",
    "tutor": "tutor",
    "removal": "removal",
    "board_wipe": "board-wipe",
    "counterspell": "counterspell",
    "bounce": "bounce",
    "flicker": "flicker",
    "recursion": "recursion",
    "protection": "protection",
    "graveyard_hate": "graveyard-hate",
    "lifegain": "lifegain",
}


def _page(address: str) -> dict[str, object]:
    request = urllib.request.Request(
        address, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"}
    )
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                loaded = json.loads(response.read())
            break
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == 5:
                raise
            wait = error.headers.get("Retry-After", "")
            time.sleep(min(float(wait) if wait.isdigit() else 5.0 * (attempt + 1), 60.0))
    if not isinstance(loaded, dict):
        raise ValueError("unexpected answer of the card search")
    return loaded


def fetch_role_file(identity: str, out_path: str | Path, *, pause: float = 0.6) -> Path:
    """Ask the public card search which Commander-legal cards inside ``identity`` carry
    each role tag and write the answer to ``out_path`` (JSON)."""
    colors = "".join(letter for letter in identity.casefold() if letter in "wubrg") or "c"
    roles: dict[str, list[str]] = {}
    for role, tag in ROLES.items():
        query = f"otag:{tag} id<={colors} f:commander"
        address: str | None = SEARCH + "?" + urllib.parse.urlencode({"q": query})
        found: set[str] = set()
        while address is not None:
            if not address.startswith("https://api.scryfall.com/"):
                raise ValueError("unexpected address in the card search answer")
            page = _page(address)
            data = page.get("data")
            for card in data if isinstance(data, list) else []:
                if isinstance(card, dict) and isinstance(card.get("oracle_id"), str):
                    found.add(card["oracle_id"])
            following = page.get("next_page")
            address = following if page.get("has_more") and isinstance(following, str) else None
            time.sleep(pause)
        roles[role] = sorted(found)
    target = Path(out_path)
    target.write_text(
        json.dumps(
            {
                "source": "Scryfall tagger (otag), public card search",
                "fetched_at": now_utc(),
                "identity": colors.upper(),
                "tags": ROLES,
                "roles": roles,
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


def import_roles(store: StudioStore, path: str | Path) -> dict[str, object]:
    """Read a role file written by ``fetch_role_file`` and count roles per source deck."""
    file_path = Path(path)
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    roles = payload.get("roles") if isinstance(payload, dict) else None
    if not isinstance(roles, dict):
        raise ValueError(f"{file_path.name}: no roles in the file")
    source_id = store.register_source(
        data_class=DataClass.ORIGINAL_SOURCE,
        title=file_path.name,
        sha256=sha256_file(file_path),
        snapshot_date=str(payload.get("fetched_at") or "") or None,
        url="https://tagger.scryfall.com/",
    )
    rows = [
        (str(oracle_id), str(role), source_id)
        for role, ids in roles.items()
        if isinstance(ids, list)
        for oracle_id in ids
    ]
    with store.connection as db:
        db.execute("DELETE FROM card_role")
        db.executemany(
            "INSERT OR IGNORE INTO card_role(oracle_id, role, source_id) VALUES (?, ?, ?)", rows
        )
        db.execute("DELETE FROM corpus_deck_role")
        db.execute(
            "INSERT INTO corpus_deck_role "
            "SELECT k.deck_id, r.role, SUM(k.quantity) FROM corpus_deck_card k "
            "JOIN card_role r ON r.oracle_id = k.oracle_id "
            "WHERE k.section != 'sideboard' GROUP BY k.deck_id, r.role"
        )
    in_collection = int(
        store.connection.execute(
            "SELECT COUNT(DISTINCT c.card_id) FROM card c JOIN card_role r USING (oracle_id)"
        ).fetchone()[0]
    )
    return {
        "roles": len(roles),
        "role_rows": len(rows),
        "collection_cards_with_role": in_collection,
    }
