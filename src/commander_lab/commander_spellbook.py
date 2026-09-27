from __future__ import annotations

import hashlib
import http.client
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from commander_lab.models import StructuralDeckProfile

SPELLBOOK_HOST = "backend.commanderspellbook.com"
SPELLBOOK_PATH = "/find-my-combos"
SPELLBOOK_SOURCE_URL = f"https://{SPELLBOOK_HOST}{SPELLBOOK_PATH}"
DEFAULT_MAX_RESPONSE_BYTES = 8_000_000


class CommanderSpellbookError(RuntimeError):
    """Raised when an explicit Commander Spellbook sync or snapshot check fails."""


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def build_find_my_combos_payload(deck: StructuralDeckProfile) -> dict[str, list[dict[str, Any]]]:
    commanders = set(deck.commander_names)
    main: list[dict[str, Any]] = []
    command: list[dict[str, Any]] = []
    for card in deck.cards:
        row = {"card": card.oracle_name, "quantity": 1}
        if card.oracle_name in commanders:
            command.append(row)
        else:
            main.append(row)
    if len(command) != len(commanders):
        missing = sorted(commanders - {str(row["card"]) for row in command})
        raise CommanderSpellbookError(f"commander cards missing from structural deck: {missing}")
    return {"main": main, "commanders": command}


def _post_find_my_combos(payload: bytes, timeout: float, max_bytes: int) -> bytes:
    connection = http.client.HTTPSConnection(SPELLBOOK_HOST, timeout=timeout)
    try:
        connection.request(
            "POST",
            SPELLBOOK_PATH,
            body=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "commander-playtest-lab/commander-spellbook-sync",
            },
        )
        response = connection.getresponse()
        if response.status != 200:
            error_body = response.read(min(max_bytes, 4096)).decode("utf-8", errors="replace")
            raise CommanderSpellbookError(
                f"Commander Spellbook returned HTTP {response.status}: {error_body[:500]}"
            )
        response_body = response.read(max_bytes + 1)
        if len(response_body) > max_bytes:
            raise CommanderSpellbookError("Commander Spellbook response exceeded size limit")
        return response_body
    except (OSError, http.client.HTTPException) as exc:
        raise CommanderSpellbookError(f"Commander Spellbook request failed: {exc}") from exc
    finally:
        connection.close()


def _validate_response(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CommanderSpellbookError("Commander Spellbook response is not a JSON object")
    results = payload.get("results")
    if not isinstance(results, dict):
        raise CommanderSpellbookError("Commander Spellbook response has no results object")
    required_lists = (
        "included",
        "includedByChangingCommanders",
        "almostIncluded",
        "almostIncludedByAddingColors",
        "almostIncludedByChangingCommanders",
        "almostIncludedByAddingColorsAndChangingCommanders",
    )
    for key in required_lists:
        if not isinstance(results.get(key), list):
            raise CommanderSpellbookError(f"Commander Spellbook results.{key} is not a list")
    identity = results.get("identity")
    if not isinstance(identity, str):
        raise CommanderSpellbookError("Commander Spellbook results.identity is not a string")
    return payload


def sync_commander_spellbook_snapshot(
    deck: StructuralDeckProfile,
    destination: str | Path,
    *,
    timeout: float = 15.0,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    fetcher: Callable[[bytes, float, int], bytes] | None = None,
) -> dict[str, Any]:
    """Explicitly fetch and persist one hash-bound combo snapshot.

    This is the only network path. Simulators and offline analysis consume the saved snapshot and
    never call Commander Spellbook implicitly.
    """

    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if max_response_bytes < 1024:
        raise ValueError("max_response_bytes is too small")
    request_object = build_find_my_combos_payload(deck)
    request_bytes = _canonical_json_bytes(request_object)
    transport = fetcher or _post_find_my_combos
    raw = transport(request_bytes, timeout, max_response_bytes)
    if len(raw) > max_response_bytes:
        raise CommanderSpellbookError("Commander Spellbook response exceeded size limit")
    try:
        response_object = _validate_response(json.loads(raw.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CommanderSpellbookError("Commander Spellbook returned invalid JSON") from exc
    semantic_response_bytes = _canonical_json_bytes(response_object)

    snapshot = {
        "schema_version": "1.0",
        "source": "Commander Spellbook find-my-combos",
        "source_url": SPELLBOOK_SOURCE_URL,
        "source_license": "MIT upstream project; data remains external evidence",
        "fetched_at": datetime.now(UTC).isoformat(),
        "deck_id": deck.deck_id,
        "deck_hash": deck.deck_hash,
        "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
        "raw_response_sha256": hashlib.sha256(raw).hexdigest(),
        "response_semantic_sha256": hashlib.sha256(semantic_response_bytes).hexdigest(),
        "truth_boundary": (
            "combo database match != proof that Commander Playtest Lab can legally execute the line"
        ),
        "request": request_object,
        "response": response_object,
    }
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "path": str(path),
        "deck_hash": deck.deck_hash,
        "request_sha256": snapshot["request_sha256"],
        "raw_response_sha256": snapshot["raw_response_sha256"],
        "response_semantic_sha256": snapshot["response_semantic_sha256"],
        "included_combo_count": len(response_object["results"]["included"]),
    }


def load_commander_spellbook_snapshot(
    path: str | Path,
    *,
    expected_deck_hash: str | None = None,
) -> dict[str, Any]:
    snapshot_path = Path(path)
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CommanderSpellbookError(
            f"invalid Commander Spellbook snapshot: {snapshot_path}"
        ) from exc
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != "1.0":
        raise CommanderSpellbookError("unsupported Commander Spellbook snapshot schema")
    if snapshot.get("source_url") != SPELLBOOK_SOURCE_URL:
        raise CommanderSpellbookError("Commander Spellbook snapshot source URL mismatch")
    if expected_deck_hash is not None and snapshot.get("deck_hash") != expected_deck_hash:
        raise CommanderSpellbookError("Commander Spellbook snapshot deck hash is stale")

    request = snapshot.get("request")
    response = _validate_response(snapshot.get("response"))
    request_bytes = _canonical_json_bytes(request)
    response_bytes = _canonical_json_bytes(response)
    if hashlib.sha256(request_bytes).hexdigest() != snapshot.get("request_sha256"):
        raise CommanderSpellbookError("Commander Spellbook snapshot request hash mismatch")
    if hashlib.sha256(response_bytes).hexdigest() != snapshot.get("response_semantic_sha256"):
        raise CommanderSpellbookError("Commander Spellbook snapshot response hash mismatch")
    raw_hash = snapshot.get("raw_response_sha256")
    if not isinstance(raw_hash, str) or len(raw_hash) != 64:
        raise CommanderSpellbookError("Commander Spellbook snapshot has no valid raw response hash")
    return snapshot


def combo_snapshot_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    response = _validate_response(snapshot.get("response"))
    results = response["results"]
    included = results["included"]
    almost = results["almostIncluded"]

    def variant_summary(row: Any) -> dict[str, Any]:
        if not isinstance(row, dict):
            return {"id": "unknown", "cards": [], "produces": []}
        cards = [
            use.get("card", {}).get("name")
            for use in row.get("uses", [])
            if isinstance(use, dict) and isinstance(use.get("card"), dict)
        ]
        produces = [
            item.get("feature", {}).get("name")
            for item in row.get("produces", [])
            if isinstance(item, dict) and isinstance(item.get("feature"), dict)
        ]
        return {
            "id": str(row.get("id", "unknown")),
            "cards": sorted(str(card) for card in cards if card),
            "produces": sorted(str(feature) for feature in produces if feature),
            "description": str(row.get("description", "")),
        }

    return {
        "deck_id": snapshot.get("deck_id"),
        "deck_hash": snapshot.get("deck_hash"),
        "identity": results.get("identity"),
        "included": [variant_summary(row) for row in included],
        "almost_included": [variant_summary(row) for row in almost],
        "truth_boundary": snapshot.get("truth_boundary"),
    }


__all__ = [
    "SPELLBOOK_SOURCE_URL",
    "CommanderSpellbookError",
    "build_find_my_combos_payload",
    "combo_snapshot_summary",
    "load_commander_spellbook_snapshot",
    "sync_commander_spellbook_snapshot",
]
