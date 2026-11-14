"""Local card image cache.

Images are fetched once from the public card-image host and then served from disk. The
request names only the public card (its image address from the public card data); nothing
about quantities, decks or the collection as a whole is sent (Owner decision 2026-11-10).
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlsplit

from .store import StudioStore

IMAGE_HOST = "cards.scryfall.io"
_USER_AGENT = "CommanderStudio/0.1 (local deck builder)"
_MAX_BYTES = 5_000_000


def image_folder(store: StudioStore) -> Path:
    if store.path is None:
        raise RuntimeError("an in-memory store has no image folder")
    folder = store.path.parent / "images"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _has_table(store: StudioStore, name: str) -> bool:
    return (
        store.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
        ).fetchone()
        is not None
    )


def image_address(store: StudioStore, card_id: str, face: str = "front") -> tuple[str, str] | None:
    """``(cache key, address)`` of a card image, or ``None`` when the card data has none.

    The cache key is the card's oracle id, so every route serves the same file for a
    card. The collection's own printing (``card_printing``, issue #1342) wins over the
    representative printing of the public card data once its image is resolved; a face
    the printing does not carry falls back to the public card data.
    """
    if face not in {"front", "back"}:
        raise ValueError(face)
    db = store.connection
    if _has_table(store, "card_printing"):
        row = db.execute(
            "SELECT scryfall_id, image_front, image_back FROM card_printing WHERE card_id = ?",
            (card_id,),
        ).fetchone()
        if row is not None and row["image_front"] is not None:
            address = row["image_front"] if face == "front" else row["image_back"]
            if address is not None:
                fact = db.execute(
                    "SELECT oracle_id FROM card_fact WHERE card_id = ?", (card_id,)
                ).fetchone()
                key = fact["oracle_id"] if fact is not None else None
                if key is None and row["scryfall_id"] is not None:
                    key = f"printing-{row['scryfall_id']}"
                if key is not None:
                    return str(key), str(address)
    row = db.execute(
        f"SELECT oracle_id, image_{face} AS address FROM card_fact WHERE card_id = ?", (card_id,)
    ).fetchone()
    if row is None or row["address"] is None:
        return None
    return str(row["oracle_id"]), str(row["address"])


def cached_image(
    store: StudioStore,
    card_id: str,
    face: str = "front",
    *,
    fetch: bool = True,
    require_stamp: bool = False,
) -> Path | None:
    """Path of the cached image; fetches it once when it is missing and ``fetch`` is set."""
    found = image_address(store, card_id, face)
    if found is None:
        return None
    oracle_id, address = found
    return _cached(store, oracle_id, address, face, fetch=fetch, require_stamp=require_stamp)


def _stamp_path(target: Path) -> Path:
    return target.with_suffix(".stamp")


def _read_stamp(target: Path) -> str | None:
    try:
        return _stamp_path(target).read_text(encoding="utf-8")
    except OSError:
        return None


def _write_stamp(target: Path, address: str) -> None:
    with suppress(OSError):
        _stamp_path(target).write_text(address, encoding="utf-8")


def _fetch_image(target: Path, address: str) -> Path | None:
    """Download one image onto ``target`` and stamp it with the address it came from."""
    parts = urlsplit(address)
    if parts.scheme != "https" or parts.hostname != IMAGE_HOST:
        return None
    request = urllib.request.Request(address, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = response.read(_MAX_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    if not data or len(data) > _MAX_BYTES:
        return None
    partial = target.with_suffix(".part")
    partial.write_bytes(data)
    partial.replace(target)
    _write_stamp(target, address)
    return target


def _cached(
    store: StudioStore,
    oracle_id: str,
    address: str,
    face: str,
    *,
    fetch: bool,
    require_stamp: bool = False,
) -> Path | None:
    target = image_folder(store) / f"{oracle_id}-{face}.jpg"
    if target.exists() and target.stat().st_size > 0:
        stamp = _read_stamp(target)
        if stamp is not None:
            if stamp == address:
                return target
            # the file on disk shows another printing; only a fetch may replace it
            return _fetch_image(target, address) if fetch else None
        if require_stamp:
            # batch upgrade path (fetch_images): an unstamped file is not proven to
            # show the address's printing, so it is fetched and stamped once
            return _fetch_image(target, address) if fetch else None
        # an unstamped file from before the stamp existed counts as valid; when a
        # fetch would be allowed anyway, stamp it in place without downloading
        if fetch:
            _write_stamp(target, address)
        return target
    if not fetch:
        return None
    return _fetch_image(target, address)


def public_card(store: StudioStore, name: str) -> dict[str, object] | None:
    """Public facts of a card by its name (full name or front face), or ``None``.

    For cards outside the collection, such as the cards of the other seats in a game.
    Tokens ending in ' Token' fallback to their base card/token name and vice versa.
    """
    row = store.connection.execute(
        "SELECT oracle_id, name, mana_cost, mana_value, type_line, oracle_text, power, "
        "toughness, image_front FROM scryfall_card WHERE name = :name OR front_name = :name "
        "ORDER BY name = :name DESC LIMIT 1",
        {"name": name},
    ).fetchone()
    if row is not None:
        return dict(row)
    if name.endswith(" Token"):
        base_name = name[:-6].strip()
        row = store.connection.execute(
            "SELECT oracle_id, name, mana_cost, mana_value, type_line, oracle_text, power, "
            "toughness, image_front FROM scryfall_card WHERE name = :name OR front_name = :name "
            "ORDER BY name = :name DESC LIMIT 1",
            {"name": base_name},
        ).fetchone()
        if row is not None:
            return dict(row)
    elif not name.endswith(" Token"):
        token_name = f"{name} Token"
        row = store.connection.execute(
            "SELECT oracle_id, name, mana_cost, mana_value, type_line, oracle_text, power, "
            "toughness, image_front FROM scryfall_card WHERE name = :name OR front_name = :name "
            "ORDER BY name = :name DESC LIMIT 1",
            {"name": token_name},
        ).fetchone()
        if row is not None:
            return dict(row)
    return None


def cached_image_by_name(store: StudioStore, name: str, *, fetch: bool = True) -> Path | None:
    """Front image of a card named by the rules engine; same cache as the collection.

    When the public printing the name resolves to is the collection's own printing
    (``card_printing.scryfall_id`` names it), that printing's resolved image wins, so
    a game shows the same picture as the deck builder for the card.
    """
    card = public_card(store, name)
    if card is None:
        return None
    oracle_id = str(card["oracle_id"])
    if _has_table(store, "card_printing"):
        row = store.connection.execute(
            "SELECT p.image_front FROM card_printing p "
            "LEFT JOIN card_fact f ON f.card_id = p.card_id "
            "LEFT JOIN scryfall_card s ON s.scryfall_id = p.scryfall_id "
            "WHERE (f.oracle_id = ? OR s.oracle_id = ?) AND p.image_front IS NOT NULL "
            "ORDER BY f.oracle_id = ? DESC LIMIT 1",
            (oracle_id, oracle_id, oracle_id),
        ).fetchone()
        if row is not None:
            return _cached(store, oracle_id, str(row["image_front"]), "front", fetch=fetch)
    if card["image_front"] is None:
        return None
    return _cached(store, oracle_id, str(card["image_front"]), "front", fetch=fetch)


def fetch_images(store: StudioStore, card_ids: list[str], *, pause: float = 0.05) -> dict[str, int]:
    """Fill the cache for these cards (front and back). Returns what happened.

    The batch path requires the address stamp: a cached file whose stamp names
    another printing — or that has no stamp yet — is fetched and stamped once, so
    a printing change reaches the cache instead of being reported as cached.
    """
    result = {"cached": 0, "fetched": 0, "missing": 0}
    for card_id in card_ids:
        for face in ("front", "back"):
            if image_address(store, card_id, face) is None:
                continue
            if cached_image(store, card_id, face, fetch=False, require_stamp=True) is not None:
                result["cached"] += 1
            elif cached_image(store, card_id, face, require_stamp=True) is not None:
                result["fetched"] += 1
                time.sleep(pause)
            else:
                result["missing"] += 1
    return result
