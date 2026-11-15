"""Direct web card images from ``cards.scryfall.io`` (local disk cache disabled, #1382).

Card images are loaded directly from ``https://cards.scryfall.io`` in the browser with
``referrerpolicy="no-referrer"`` and ``loading="lazy"``. The request names only the public
card image URL from the public card data; nothing about quantities, decks or the collection
as a whole is sent (Owner decision 2026-11-10). Legacy ``/img/...`` routes respond with a
302 redirect to the validated ``https://cards.scryfall.io`` address without writing files to
disk. Any pre-existing ``images/`` directory is left untouched and reported with its size so
the Owner can remove it when convenient.
"""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from urllib.parse import urlsplit

from .store import StudioStore

IMAGE_HOST = "cards.scryfall.io"


def valid_image_url(address: object) -> str | None:
    """Return ``address`` when it is an ``https://cards.scryfall.io/...`` URL, else ``None``."""
    if not isinstance(address, str) or not address:
        return None
    parts = urlsplit(address)
    if parts.scheme != "https" or parts.hostname != IMAGE_HOST or not parts.path:
        return None
    return address


def image_folder(store: StudioStore) -> Path:
    """Path where the legacy image cache lived (never created automatically)."""
    if store.path is None:
        raise RuntimeError("an in-memory store has no image folder")
    return store.path.parent / "images"


def image_cache_status(store: StudioStore) -> dict[str, object]:
    """Non-destructive status of any legacy ``images/`` folder next to ``studio.sqlite3``."""
    if store.path is None:
        return {
            "cache_enabled": False,
            "exists": False,
            "folder": None,
            "files": 0,
            "bytes": 0,
            "megabytes": 0.0,
            "hint": (
                f"Lokaler Bild-Cache ist abgeschaltet; Bilder werden direkt von "
                f"https://{IMAGE_HOST} geladen."
            ),
        }
    folder = store.path.parent / "images"
    if not folder.is_dir():
        return {
            "cache_enabled": False,
            "exists": False,
            "folder": str(folder),
            "files": 0,
            "bytes": 0,
            "megabytes": 0.0,
            "hint": (
                f"Lokaler Bild-Cache ist abgeschaltet; Bilder werden direkt von "
                f"https://{IMAGE_HOST} geladen."
            ),
        }
    files = 0
    total_bytes = 0
    for entry in folder.rglob("*"):
        if entry.is_file():
            files += 1
            with suppress(OSError):
                total_bytes += entry.stat().st_size
    mb = round(total_bytes / (1024 * 1024), 2)
    return {
        "cache_enabled": False,
        "exists": True,
        "folder": str(folder),
        "files": files,
        "bytes": total_bytes,
        "megabytes": mb,
        "hint": (
            f"Lokaler Bild-Cache ist abgeschaltet (Bilder kommen direkt von https://{IMAGE_HOST}). "
            f"Der vorhandene Ordner {folder} ({files} Dateien, {mb:.2f} MB) wird nicht mehr "
            "genutzt und kann gelöscht werden."
        ),
    }


def _has_table(store: StudioStore, name: str) -> bool:
    return (
        store.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
        ).fetchone()
        is not None
    )


def image_address(store: StudioStore, card_id: str, face: str = "front") -> tuple[str, str] | None:
    """``(oracle_or_printing_key, address)`` of a card image on ``https://cards.scryfall.io``,
    or ``None`` when the card data has none or the host is not ``cards.scryfall.io``.

    The collection's own printing (``card_printing``, issue #1342) wins over the
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
        if row is not None and valid_image_url(row["image_front"]) is not None:
            raw_addr = row["image_front"] if face == "front" else row["image_back"]
            addr = valid_image_url(raw_addr)
            if addr is not None:
                fact = db.execute(
                    "SELECT oracle_id FROM card_fact WHERE card_id = ?", (card_id,)
                ).fetchone()
                key = fact["oracle_id"] if fact is not None else None
                if key is None and row["scryfall_id"] is not None:
                    key = f"printing-{row['scryfall_id']}"
                if key is not None:
                    return str(key), addr
    row = db.execute(
        f"SELECT oracle_id, image_{face} AS address FROM card_fact WHERE card_id = ?", (card_id,)
    ).fetchone()
    if row is None:
        return None
    addr = valid_image_url(row["address"])
    if addr is None:
        return None
    return str(row["oracle_id"]), addr


def web_image_url(store: StudioStore, card_id: str, face: str = "front") -> str | None:
    """Validated ``https://cards.scryfall.io/...`` URL for ``card_id`` and ``face``, or ``None``."""
    found = image_address(store, card_id, face)
    return found[1] if found is not None else None


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


def web_image_url_by_name(store: StudioStore, name: str) -> str | None:
    """Validated ``https://cards.scryfall.io/...`` front image URL of a card named by the
    rules engine, or ``None``.

    When the public printing the name resolves to is the collection's own printing
    (``card_printing``), that printing's resolved image wins so a game shows the same
    picture as the deck builder for the card.
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
            owned_url = valid_image_url(row["image_front"])
            if owned_url is not None:
                return owned_url
    return valid_image_url(card["image_front"])


def cached_image(
    store: StudioStore,
    card_id: str,
    face: str = "front",
    *,
    fetch: bool = False,
    require_stamp: bool = False,
) -> Path | None:
    """Deprecated (#1382): local image cache is disabled; never writes to ``images/``."""
    del store, card_id, face, fetch, require_stamp
    return None


def cached_image_by_name(store: StudioStore, name: str, *, fetch: bool = False) -> Path | None:
    """Deprecated (#1382): local image cache is disabled; never writes to ``images/``."""
    del store, name, fetch
    return None


def fetch_images(
    store: StudioStore, card_ids: list[str] | None = None, *, pause: float = 0.0
) -> dict[str, object]:
    """Deprecated (#1382): local image cache is disabled; reports any existing ``images/`` folder."""
    del card_ids, pause
    return {
        "deprecated": True,
        "cached": 0,
        "fetched": 0,
        "missing": 0,
        **image_cache_status(store),
    }
