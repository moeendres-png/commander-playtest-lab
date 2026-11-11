"""Local card image cache.

Images are fetched once from the public card-image host and then served from disk. The
request names only the public card (its image address from the public card data); nothing
about quantities, decks or the collection as a whole is sent (Owner decision 2026-11-10).
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
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


def image_address(store: StudioStore, card_id: str, face: str = "front") -> tuple[str, str] | None:
    """``(oracle_id, address)`` of a card image, or ``None`` when the card data has none."""
    if face not in {"front", "back"}:
        raise ValueError(face)
    row = store.connection.execute(
        f"SELECT oracle_id, image_{face} AS address FROM card_fact WHERE card_id = ?", (card_id,)
    ).fetchone()
    if row is None or row["address"] is None:
        return None
    return str(row["oracle_id"]), str(row["address"])


def cached_image(
    store: StudioStore, card_id: str, face: str = "front", *, fetch: bool = True
) -> Path | None:
    """Path of the cached image; fetches it once when it is missing and ``fetch`` is set."""
    found = image_address(store, card_id, face)
    if found is None:
        return None
    oracle_id, address = found
    return _cached(store, oracle_id, address, face, fetch=fetch)


def _cached(
    store: StudioStore, oracle_id: str, address: str, face: str, *, fetch: bool
) -> Path | None:
    target = image_folder(store) / f"{oracle_id}-{face}.jpg"
    if target.exists() and target.stat().st_size > 0:
        return target
    if not fetch:
        return None
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
    return target


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
    """Front image of a card named by the rules engine; same cache as the collection."""
    card = public_card(store, name)
    if card is None or card["image_front"] is None:
        return None
    return _cached(store, str(card["oracle_id"]), str(card["image_front"]), "front", fetch=fetch)


def fetch_images(store: StudioStore, card_ids: list[str], *, pause: float = 0.05) -> dict[str, int]:
    """Fill the cache for these cards (front and back). Returns what happened."""
    result = {"cached": 0, "fetched": 0, "missing": 0}
    for card_id in card_ids:
        for face in ("front", "back"):
            if image_address(store, card_id, face) is None:
                continue
            if cached_image(store, card_id, face, fetch=False) is not None:
                result["cached"] += 1
            elif cached_image(store, card_id, face) is not None:
                result["fetched"] += 1
                time.sleep(pause)
            else:
                result["missing"] += 1
    return result
