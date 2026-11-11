"""Card roles (ramp, card draw, removal ...) from the public Scryfall tagger.

The tags are labels maintained by the Scryfall community: a public statement that a card
does a certain job, not a rating and not complete. The query names only a color identity,
never a collection or a deck.

Import is lossless. A role file says what it is (origin) and how much it covers (scope):

* ``FULL_SNAPSHOT`` replaces what an earlier snapshot of the same origin and scope said
  about the roles it lists, and nothing else. A replacement that removes claims needs the
  caller's explicit permission.
* ``PARTIAL_INCREMENTAL`` only adds.

Every statement is kept as a claim with its origin, so a role read from the card's Oracle
text never overwrites, and is never shown as, an original tagger label. ``card_role`` (what
the builder reads) and ``corpus_deck_role`` (the counts per source deck) are rebuilt from the
claims in the same transaction; a failed import changes nothing.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .store import DataClass, StudioStore, now_utc, rebuild_corpus_deck_role, sha256_file

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

# Scryfall's card search resolves these query slugs to the canonical label on the right
# (checked 2026-11-11 for ``id<=wug f:commander``: 317 and 194 cards, the same count as the
# canonical label). The tagger bulk lists canonical labels only, so a reader of the bulk has to
# map them explicitly; ``check_role_labels`` reports where that is needed.
SEARCH_ALIASES: dict[str, str] = {"board-wipe": "sweeper", "graveyard-hate": "hate-graveyard"}

ROLES_SCHEMA = "studio-roles-2"
FULL_SNAPSHOT = "FULL_SNAPSHOT"
PARTIAL_INCREMENTAL = "PARTIAL_INCREMENTAL"
ORIGIN_TAGGER = "SCRYFALL_TAGGER_ORIGINAL"
ORIGIN_CROSSWALK = "CROSSWALK_NORMALIZED"
ORIGIN_ORACLE_TEXT = "ORACLE_TEXT_REVIEW"
ROLE_ORIGINS = (ORIGIN_TAGGER, ORIGIN_CROSSWALK, ORIGIN_ORACLE_TEXT)
LEGACY_ORIGIN = "LEGACY_UNSPECIFIED"  # rows that were in card_role before claims existed
_COMPLETE = "COMPLETE_FOR_SCOPE"
_PARTIAL = "PARTIAL"
_SCOPE_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,39}")
_ORACLE_ID = re.compile(r"[^\s:]{1,64}")  # no blanks, no colon: not a name, not a card id
_IDENTITY = re.compile(r"[WUBRGC]{1,5}")
_ORIGIN_RANK = (
    "CASE role_origin WHEN 'SCRYFALL_TAGGER_ORIGINAL' THEN 0 WHEN 'CROSSWALK_NORMALIZED' THEN 1 "
    "WHEN 'ORACLE_TEXT_REVIEW' THEN 2 ELSE 3 END"
)


@dataclass(frozen=True)
class RoleFile:
    """A role file after validation. Reading one touches no database."""

    origin: str
    mode: str
    scope_key: str
    fetched_at: str
    tags: dict[str, str]
    mapping_rule: str | None
    roles: dict[str, tuple[str, ...]]
    legacy_format: bool = False


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
    colors = "".join(letter for letter in "wubrg" if letter in identity.casefold()) or "c"
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
                "schema": ROLES_SCHEMA,
                "source": "Scryfall tagger (otag), public card search",
                "role_origin": ORIGIN_TAGGER,
                "fetched_at": now_utc(),
                "identity": colors.upper(),
                "scope": {"mode": FULL_SNAPSHOT, "key": colors.upper(), "completeness": _COMPLETE},
                "tags": ROLES,
                "tag_aliases": {
                    tag: SEARCH_ALIASES[tag] for tag in ROLES.values() if tag in SEARCH_ALIASES
                },
                "roles": roles,
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


def _fail(name: str, message: str) -> ValueError:
    return ValueError(f"{name}: {message}")


def _identity_key(identity: str) -> str:
    return "".join(letter for letter in "WUBRG" if letter in identity.upper()) or "C"


def read_role_file(path: str | Path) -> RoleFile:
    """Read and check a role file. Raises ``ValueError`` for anything that is not clear.

    A file without scope and completeness is never read as a full snapshot. The only
    exception is the file ``fetch_role_file`` wrote before the scope existed: it names its
    color identity and carries a tag for every role, which says what it covers.
    """
    file_path = Path(path)
    name = file_path.name
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise _fail(name, f"not valid JSON ({error.msg})") from error
    roles_raw = payload.get("roles") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or not isinstance(roles_raw, dict) or not roles_raw:
        raise _fail(name, "no roles in the file")
    fetched_at = payload.get("fetched_at")
    if not isinstance(fetched_at, str) or not fetched_at.strip():
        raise _fail(name, "no fetched_at (the snapshot time belongs to the provenance)")

    legacy = False
    if payload.get("schema") == ROLES_SCHEMA:
        origin, mode, scope_key = _read_scope(name, payload)
    elif "schema" not in payload and _is_old_fetch_file(payload):
        legacy = True
        identity = payload["identity"]
        if not isinstance(identity, str) or not _IDENTITY.fullmatch(identity.upper()):
            raise _fail(name, "the color identity of the file is not readable")
        if set(roles_raw) != set(payload["tags"]):
            raise _fail(name, "roles and tags differ: the file is not a complete snapshot")
        origin, mode, scope_key = ORIGIN_TAGGER, FULL_SNAPSHOT, _identity_key(identity)
    elif "schema" in payload:
        raise _fail(name, f"unknown schema {payload.get('schema')!r}")
    else:
        raise _fail(
            name,
            f"no scope: a role file needs schema {ROLES_SCHEMA} with role_origin and scope "
            "(mode, key, completeness); a file without them is not read as a full snapshot",
        )

    tags = _read_tags(name, payload, origin)
    mapping_rule: str | None = None
    if origin == ORIGIN_CROSSWALK:
        version = payload.get("crosswalk_version")
        if not isinstance(version, str) or not version.strip():
            raise _fail(name, "a normalized file needs crosswalk_version")
        mapping_rule = f"crosswalk:{version.strip()}"

    roles: dict[str, tuple[str, ...]] = {}
    for role, ids in roles_raw.items():
        if role not in ROLES:
            raise _fail(name, f"unknown role {role!r}; the roles are {', '.join(ROLES)}")
        if not isinstance(ids, list):
            raise _fail(name, f"role {role} is not a list")
        for oracle_id in ids:
            if not isinstance(oracle_id, str) or not _ORACLE_ID.fullmatch(oracle_id):
                raise _fail(name, f"role {role}: {oracle_id!r} is not an oracle id")
        if len(set(ids)) != len(ids):
            raise _fail(name, f"role {role} lists an oracle id twice")
        if origin != ORIGIN_ORACLE_TEXT and role not in tags:
            raise _fail(name, f"role {role} has no original tag")
        roles[role] = tuple(sorted(ids))
    return RoleFile(origin, mode, scope_key, fetched_at.strip(), tags, mapping_rule, roles, legacy)


def _is_old_fetch_file(payload: dict[str, object]) -> bool:
    source = payload.get("source")
    return (
        isinstance(source, str)
        and source.startswith("Scryfall tagger (otag)")
        and isinstance(payload.get("identity"), str)
        and isinstance(payload.get("tags"), dict)
    )


def _read_scope(name: str, payload: dict[str, object]) -> tuple[str, str, str]:
    origin = payload.get("role_origin")
    if not isinstance(origin, str) or origin not in ROLE_ORIGINS:
        raise _fail(name, f"role_origin must be one of {', '.join(ROLE_ORIGINS)}")
    scope = payload.get("scope")
    if not isinstance(scope, dict):
        raise _fail(name, "no scope")
    mode, key, completeness = scope.get("mode"), scope.get("key"), scope.get("completeness")
    if mode not in (FULL_SNAPSHOT, PARTIAL_INCREMENTAL):
        raise _fail(name, f"scope.mode must be {FULL_SNAPSHOT} or {PARTIAL_INCREMENTAL}")
    if not isinstance(key, str) or not _SCOPE_KEY.fullmatch(key):
        raise _fail(name, "scope.key is missing or malformed")
    if (mode, completeness) not in {(FULL_SNAPSHOT, _COMPLETE), (PARTIAL_INCREMENTAL, _PARTIAL)}:
        raise _fail(name, f"scope.mode {mode} contradicts scope.completeness {completeness!r}")
    return origin, str(mode), key


def _read_tags(name: str, payload: dict[str, object], origin: str) -> dict[str, str]:
    raw = payload.get("tags")
    if origin == ORIGIN_ORACLE_TEXT:
        if raw:
            raise _fail(name, "a review of the Oracle text carries no tagger tags")
        return {}
    if not isinstance(raw, dict):
        raise _fail(name, f"{origin} needs the original tag of every role (tags)")
    tags: dict[str, str] = {}
    for role, tag in raw.items():
        if not isinstance(role, str) or not isinstance(tag, str) or not tag.strip():
            raise _fail(name, "tags must map each role to a tag")
        tags[role] = tag.strip()
    return tags


def check_role_labels(labels: Iterable[str]) -> dict[str, list[str]]:
    """Compare the query slugs of ``ROLES`` with the labels of an official tagger list.

    ``canonical``: the slug is a label. ``search_alias``: it is not, but the search resolves it
    to a label that is (``SEARCH_ALIASES``). ``unknown``: neither. Nothing is assumed equal
    that the list does not show.
    """
    known = {label.strip() for label in labels if label.strip()}
    report: dict[str, list[str]] = {"canonical": [], "search_alias": [], "unknown": []}
    for role, slug in ROLES.items():
        if slug in known:
            report["canonical"].append(role)
        elif SEARCH_ALIASES.get(slug) in known:
            report["search_alias"].append(role)
        else:
            report["unknown"].append(role)
    return report


def _claims_by_origin(db: sqlite3.Connection) -> dict[str, int]:
    rows = db.execute(
        "SELECT role_origin, COUNT(*) FROM card_role_claim GROUP BY role_origin ORDER BY 1"
    ).fetchall()
    return {str(row[0]): int(row[1]) for row in rows}


_SOURCE_CLASS = {
    ORIGIN_TAGGER: DataClass.ORIGINAL_SOURCE,
    ORIGIN_CROSSWALK: DataClass.NORMALIZED_SOURCE,
    ORIGIN_ORACLE_TEXT: DataClass.DERIVED_DESCRIPTIVE,
}


def import_roles(
    store: StudioStore, path: str | Path, *, allow_scope_replace: bool = False
) -> dict[str, object]:
    """Read a role file (``read_role_file``) and merge it into the store as claims.

    One transaction: the file is checked first, then source, claims, ``card_role`` and
    ``corpus_deck_role`` change together or not at all. Importing the same file twice leaves
    the store as it was.
    """
    file_path = Path(path)
    parsed = read_role_file(file_path)
    sha256 = sha256_file(file_path)
    new_pairs = {(oracle_id, role) for role, ids in parsed.roles.items() for oracle_id in ids}
    marks = ",".join("?" * len(parsed.roles))
    with store.connection as db:  # commits at the end, rolls back on any error
        source_id = store.register_source(
            data_class=_SOURCE_CLASS[parsed.origin],
            title=file_path.name,
            sha256=sha256,
            snapshot_date=parsed.fetched_at,
            url="https://tagger.scryfall.com/" if parsed.origin != ORIGIN_ORACLE_TEXT else None,
        )
        # card_role rows no claim stands behind (from before claims existed, or written by an
        # older program version) are kept as claims with an origin that says nothing more
        db.execute(
            "INSERT INTO card_role_claim(oracle_id, role, role_origin, scope_key, source_id, "
            "original_tag, mapping_rule) SELECT r.oracle_id, r.role, ?, 'LEGACY', r.source_id, "
            "NULL, 'card_role row without claim' FROM card_role r WHERE NOT EXISTS ("
            "SELECT 1 FROM card_role_claim c WHERE c.oracle_id = r.oracle_id AND c.role = r.role)",
            (LEGACY_ORIGIN,),
        )
        same_scope = {
            (str(r[0]), str(r[1]))
            for r in db.execute(
                "SELECT oracle_id, role FROM card_role_claim WHERE role_origin = ? "
                f"AND scope_key = ? AND role IN ({marks})",
                (parsed.origin, parsed.scope_key, *parsed.roles),
            )
        }
        removed = same_scope - new_pairs if parsed.mode == FULL_SNAPSHOT else set()
        if removed and not allow_scope_replace:
            raise ValueError(
                f"{file_path.name}: the full snapshot of {parsed.origin} / {parsed.scope_key} "
                f"would remove {len(removed)} earlier claims; "
                "run again with --replace-scope if that is intended"
            )
        legacy_superseded = 0
        if parsed.mode == FULL_SNAPSHOT:
            db.execute(
                "DELETE FROM card_role_claim WHERE role_origin = ? AND scope_key = ? "
                f"AND role IN ({marks})",
                (parsed.origin, parsed.scope_key, *parsed.roles),
            )
            if parsed.origin == ORIGIN_TAGGER:
                legacy_superseded = max(
                    0,
                    db.executemany(
                        "DELETE FROM card_role_claim WHERE role_origin = ? AND oracle_id = ? "
                        "AND role = ?",
                        [(LEGACY_ORIGIN, oracle_id, role) for oracle_id, role in sorted(new_pairs)],
                    ).rowcount,
                )
        db.executemany(
            "INSERT OR IGNORE INTO card_role_claim(oracle_id, role, role_origin, scope_key, "
            "source_id, original_tag, mapping_rule) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (oracle_id, role, parsed.origin, parsed.scope_key, source_id,
                 parsed.tags.get(role), parsed.mapping_rule)
                for role, ids in sorted(parsed.roles.items())
                for oracle_id in ids
            ],
        )  # fmt: skip
        db.execute("DELETE FROM card_role")
        db.execute(
            "INSERT INTO card_role(oracle_id, role, source_id) "
            "SELECT oracle_id, role, source_id FROM ("
            "SELECT oracle_id, role, source_id, ROW_NUMBER() OVER ("
            f"PARTITION BY oracle_id, role ORDER BY {_ORIGIN_RANK}, source_id) AS n "
            "FROM card_role_claim) WHERE n = 1"
        )
        rebuild_corpus_deck_role(db)
        legacy_left = int(
            db.execute(
                f"SELECT COUNT(*) FROM card_role_claim WHERE role_origin = ? AND role IN ({marks})",
                (LEGACY_ORIGIN, *parsed.roles),
            ).fetchone()[0]
        )
        by_origin = _claims_by_origin(db)
        card_role_total = int(db.execute("SELECT COUNT(*) FROM card_role").fetchone()[0])
    in_collection = int(
        store.connection.execute(
            "SELECT COUNT(DISTINCT c.card_id) FROM card c JOIN card_role r USING (oracle_id)"
        ).fetchone()[0]
    )
    return {
        "roles": len(parsed.roles),
        "role_rows": len(new_pairs),
        "collection_cards_with_role": in_collection,
        "role_origin": parsed.origin,
        "mode": parsed.mode,
        "scope": parsed.scope_key,
        "legacy_file_format": parsed.legacy_format,
        "claims_added": len(new_pairs - same_scope),
        "claims_removed": len(removed),
        "legacy_claims_superseded": legacy_superseded,
        "legacy_claims_left_in_these_roles": legacy_left,
        "claims_by_origin": by_origin,
        "card_role_rows": card_role_total,
        "source_id": source_id,
    }
