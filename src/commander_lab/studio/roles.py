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

from .decks import color_set
from .store import DataClass, StudioStore, now_utc, rebuild_corpus_deck_role, sha256_file

SEARCH = "https://api.scryfall.com/cards/search"
# Generic client identity: no project, repository or person reference, no contact details
# (Owner decision #1557 point 4).
_USER_AGENT = "mtg-card-roles-tool/1.0"

# role -> tagger tag (every value is a canonical otag: slug verified 200 OK on api.scryfall.com)
ROLES: dict[str, str] = {
    "ramp": "ramp",
    "mana_rock": "mana-rock",
    "mana_dork": "mana-dork",
    "land_ramp": "land-ramp",
    "card_draw": "draw",
    "card_advantage": "card-advantage",
    "cantrip": "cantrip",
    "card_selection": "topdeck-manipulation",
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
    "evasion": "evasion",
    "hate": "hate",
    "tax": "tax",
    "combat_trick": "combat-trick",
    "counters": "gives-pp-counters",
    "token_production": "repeatable-creature-tokens",
    "utility_land": "utility-land",
    "mana_sink": "mana-sink",
    "mill": "mill",
    "tapper": "tapper",
    "untapper": "untapper",
    "sacrifice_outlet": "sacrifice-outlet",
    "anthem": "anthem",
    "landfall": "landfall",
    "copy": "copy",
    "cost_reduction": "cost-reducer",
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
    return import_role_snapshot(
        store,
        parsed,
        title=file_path.name,
        sha256=sha256_file(file_path),
        allow_scope_replace=allow_scope_replace,
    )


def import_role_snapshot(
    store: StudioStore,
    parsed: RoleFile,
    *,
    title: str,
    sha256: str,
    allow_scope_replace: bool = False,
) -> dict[str, object]:
    """Merge an already checked role file into the store as claims (see ``import_roles``).

    ``title`` and ``sha256`` name the file the roles were read from; a converter that reads
    another format (a CSV) passes its own file here, so the source row says where the claims
    really come from."""
    new_pairs = {(oracle_id, role) for role, ids in parsed.roles.items() for oracle_id in ids}
    marks = ",".join("?" * len(parsed.roles))
    with store.connection as db:  # commits at the end, rolls back on any error
        source_id = store.register_source(
            data_class=_SOURCE_CLASS[parsed.origin],
            title=title,
            sha256=sha256,
            snapshot_date=parsed.fetched_at or None,
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
                f"{title}: the full snapshot of {parsed.origin} / {parsed.scope_key} "
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


_ORACLE_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("counters", re.compile(r"\+1/\+1 counter")),
    ("token_production", re.compile(r"\bcreate\b[^.\n]*\bcreature token|\bliving weapon\b")),
    (
        "card_selection",
        re.compile(r"\b(?:scry|surveil) \d+\b|look at the top \w+ cards? of your library"),
    ),
    (
        "evasion",
        re.compile(
            r"(?:^|\n|, |has |have |gains |gain )"
            r"(?:flying|menace|shadow|fear|intimidate|horsemanship|unblockable|can't be blocked)"
        ),
    ),
    (
        "untapper",
        re.compile(r"\buntap (?:up to \w+ )?(?:other )?target\b|\buntap all\b|\buntap that\b"),
    ),
    ("tapper", re.compile(r"\btap (?:up to \w+ )?(?:target|all)\b|\bdetain target\b")),
    (
        "mill",
        re.compile(
            r"\bmills? (?:a|\w+) cards?\b|"
            r"\bput the top \w+ cards? of [^\n.]*library into [^\n.]*graveyard"
        ),
    ),
    (
        "copy",
        re.compile(r"\bcopy target\b|\bcreate a token that's a copy\b|\bbecomes? a copy of\b"),
    ),
    (
        "cost_reduction",
        re.compile(r"spells? (?:you cast )?cost \{\d+\} less to cast|costs? \{\d+\} less to cast"),
    ),
    ("landfall", re.compile(r"landfall —|whenever a land you control enters")),
    (
        "flicker",
        re.compile(
            r"\bexile\b[^\n.]*, then return (?:it|that card|them|those cards) "
            r"to the battlefield\b"
            r"|\bexile\b[^.\n]*\. return (?:it|that card) to the battlefield\b"
        ),
    ),
    (
        "recursion",
        re.compile(
            r"\breturns? [^\n.]*from (?:your|a|an opponent's|any|their|that player's) "
            r"graveyard to (?:the battlefield|your hand)\b"
            r"|\bput [^\n.]*from (?:your|a|an opponent's|any) graveyard "
            r"(?:onto|on) the battlefield\b"
        ),
    ),
    (
        "graveyard_hate",
        re.compile(
            r"\bexile (?:target|up to \w+ target) cards? from a graveyard\b"
            r"|\bexile all cards from [^\n.]*graveyards?\b"
            r"|\bexile (?:all|each opponent's) graveyards?\b"
            r"|\bexile [^\n.]*player's graveyard\b"
        ),
    ),
    (
        "tutor",
        re.compile(
            r"\bsearch your library for [^\n.]*, reveal it, [^\n.]*into your hand\b"
            r"|\bsearch your library for a card[^\n.]*put that card on top of "
            r"your library\b"
            r"|\bsearch your library for (?:a|an) [^\n.]*?"
            r"(?:creature|artifact|enchantment|planeswalker|instant|sorcery) card"
            r"[^\n.]*, put (?:it|that card) onto the battlefield\b"
        ),
    ),
    (
        "removal",
        re.compile(
            r"\b(?:destroy|exile) target\b|"
            r"deals? \d+ damage to (?:any target|target (?:creature|planeswalker))"
        ),
    ),
    (
        "board_wipe",
        re.compile(
            r"\b(?:destroy|exile) all (?:creatures|nonland permanents|artifacts|enchantments)\b"
        ),
    ),
    ("bounce", re.compile(r"\breturn target [^\n.]* to its owner's hand\b")),
    ("counterspell", re.compile(r"\bcounter target [^\n.]*spell\b")),
    ("lifegain", re.compile(r"\bgain[s]? \d+ life\b")),
    (
        "protection",
        re.compile(r"\bhexproof\b|\bshroud\b|\bindestructible\b|\bward \{|\bprotection from\b"),
    ),
)
_ANTHEM_RE = re.compile(r"(?:other )?creatures you control get \+\d+/\+\d+")
_LAND_RAMP_RE = re.compile(
    r"search your library for [^\n.]*"
    r"(?:land|plains|island|swamp|mountain|forest) card"
    r"[^\n.]*put[^\n.]*(?:onto|into) the battlefield"
)
# A mana ability whose tap cost carries an extra component ("{T}, Sacrifice this
# artifact: Add three mana ..."): the plain "{t}:" check misses it. It reads the
# reminder-stripped text and is anchored at a line start, so a Treasure token's
# reminder text does not count: the token has the ability, not the card that
# creates it.
_TAP_ADD_RE = re.compile(r"(?:^|\n)\{t\},[^\n:]*: add (?:\{|\w+ mana)")
_TEMP_BOOST_RE = re.compile(
    r"get[s]? \+[\dx]+/\+?[\dx-]* until end of turn|gains? [^\n.]* until end of turn"
)
# Parenthesised reminder text explains an ability of another object (a token
# the card creates) or of a keyword; the mana and search rules below read the
# text with it removed: the token has the ability, not the card that creates
# it.
_REMINDER = re.compile(r"\([^()]*\)")
# A draw whose drawer is not the card's controller ("that player draws", "each
# player draws", "its controller draws"). "Target player draws" stays: the
# controller may target themselves ("Night's Whisper"-style).
_DRAW_OTHER_SUBJECT_RE = re.compile(
    r"\b(?:(?:that|each|defending) player|players|(?:its|'s) (?:controller|owner))\s+(?:may\s+)?$"
)


def strip_reminder(text: str) -> str:
    """The text without parenthesised reminder text, nested parentheses included.

    The innermost pair is removed until none is left; an unbalanced ")" stays."""
    while True:
        stripped = _REMINDER.sub(" ", text)
        if stripped == text:
            return stripped
        text = stripped


_DRAW_RE = re.compile(r"\bdraws? (?:(?:a |an |\w+ |that many )?(?:additional )?)?cards?\b")
_DRAW_TRIGGER_RE = re.compile(r"\b(?:whenever|when|if)\b")
# A negation counts only directly at the draw phrase (last words of the
# clause): an unrelated "can't" earlier in the clause ("enchanted creature
# can't attack or block and has '{7}: … draws a card'") negates something
# else, not the draw.
_DRAW_NEGATION_TAIL_RE = re.compile(r"\b(?:can't|cannot|don't|doesn't)(?:\s+\w+){0,2}\s*$")
_DRAW_OPPONENT_SUBJECT_RE = re.compile(r"\bopponents?\s+(?:would\s+|may\s+)?$")
_TAX_RE = re.compile(r"\bcosts? \{\d+\} more to cast\b")
_TAX_SELF_COST_RE = re.compile(r"\bthis spell costs? \{\d+\} more to cast\b")
_SINGLE_DRAW_RE = re.compile(r"\bdraws? a card\b")
_MULTI_OR_VAR_DRAW_RE = re.compile(
    r"\bdraws? (?:two|three|four|five|six|seven|eight|nine|ten|\d+|x|that many)(?: additional)? cards\b"
    r"|\bdraw cards\b"
    r"|\beach player draws\b"
)
_MULTI_DRAW_RE = re.compile(
    r"\bdraws? (?:two|three|four|five|six|seven|eight|nine|ten|\d+)(?: additional)? cards\b"
    r"|\bdraw cards equal to\b"
)
_SYMMETRIC_OR_LOOT_RE = re.compile(
    r"\beach player draws\b|\bthen discard (?:a|\w+) cards?\b|\bthen put [^\n.]*from your hand\b"
)
_ETB_DRAW_RE = re.compile(r"\bwhen [^\n.]*\benters\b[^\n.]*\bdraw a card\b")
_HATE_RE = re.compile(
    r"(?:your )?(?:opponents?|players?|each player) can't cast\b"
    r"|(?:your )?(?:opponents?|players?|each player) can't (?:activate|search|play lands|untap|gain life)\b"
    r"|(?:your )?(?:opponents?|players?|each player) can't draw more than \w+ cards?\b"
    r"|\bactivated abilities of [^\n.]*can't be activated\b"
    r"|\b(?:creatures|permanents) entering [^\n.]*don't cause abilities to trigger\b"
    r"|\bcan't cast spells from (?:anywhere other than|graveyards?|exile)\b"
    r"|\b(?:graveyards?|libraries)[^\n.]*can't enter the battlefield\b"
    r"|\bcan't enter the battlefield from graveyards?\b"
)


def _clause_prefix(text: str, start: int) -> str:
    """The clause the position ``start`` sits in: the text since the last
    comma, full stop, semicolon or line break before it."""
    boundary = max(text.rfind(sep, 0, start) for sep in ",.;\n")
    return text[boundary + 1 : start]


def _has_card_draw(o: str, *, own_only: bool = False) -> bool:
    """A draw phrase counts only as the controller's own draw effect.

    A phrase inside a trigger condition draws nothing ("whenever you draw a
    card" is a payoff trigger; the draw is the condition, not the effect),
    and neither does a negated one ("players can't draw cards") or one whose
    only drawer is an opponent ("target opponent draws a card"). The clause
    decides: what follows the comma of "when this creature enters, draw a
    card" is the effect and counts, and so does the real draw after a
    replaced opponent draw ("if an opponent would draw a card, instead you
    draw a card").

    ``own_only`` also drops a draw whose drawer is another player ("that
    player draws", "each player draws", "its controller draws")."""
    for match in _DRAW_RE.finditer(o):
        prefix = _clause_prefix(o, match.start())
        if _DRAW_TRIGGER_RE.search(prefix):
            continue
        if _DRAW_NEGATION_TAIL_RE.search(prefix):
            continue
        if _DRAW_OPPONENT_SUBJECT_RE.search(prefix):
            continue
        if own_only and _DRAW_OTHER_SUBJECT_RE.search(prefix):
            continue
        return True
    return False


def _has_tax(o: str) -> bool:
    """A "costs {N} more to cast" phrase is a tax effect on spells in
    general. A spell's own escalating cost formula ("this spell costs {1}
    more to cast for each target beyond the first") taxes nobody and is
    removed before the match."""
    return bool(_TAX_RE.search(_TAX_SELF_COST_RE.sub(" ", o)))


def _has_utility_ability(oracle: str) -> bool:
    """A land has a utility ability when one of its lines is an activated ability
    (a cost with a mana symbol or a sacrifice, then a colon) whose effect neither
    produces mana nor searches the library (a fetch land's search is land ramp,
    not utility). Static and triggered text has no such colon and never counts."""
    for line in oracle.split("\n"):
        cost, sep, effect = line.partition(":")
        if not sep or ("{" not in cost and "sacrifice" not in cost):
            continue
        effect = effect.strip()
        if effect.startswith("add ") or effect.startswith("add{"):
            continue
        if "search your library" in effect:
            continue
        return True
    return False


def _has_repeatable_draw_trigger(o: str) -> bool:
    # controller draws only: "whenever a player casts ..., that player draws" is no advantage
    for sentence in re.split(r"[.\n]+", o):
        if (
            re.search(r"\bwhenever\b", sentence)
            and _has_card_draw(sentence, own_only=True)
            and not _SYMMETRIC_OR_LOOT_RE.search(sentence)
        ):
            return True
    return False


def classify_oracle_roles(type_line: str, oracle_text: str) -> tuple[str, ...]:
    """Derive deterministic functional roles from public card ``type_line`` and ``oracle_text``.

    Pure and rule-based (origin ``ORACLE_TEXT_REVIEW``): only clear Oracle text mechanics map
    to roles; vanilla text yields ``()``. Never guesses, never overwrites tagger claims.
    """
    t = (type_line or "").casefold()
    o = (oracle_text or "").casefold()
    if not o.strip():
        return ()
    found = {role for role, pattern in _ORACLE_RULES if pattern.search(o)}
    # cantrip, card_advantage and hate read the text without reminder text: a
    # Clue's "draw a card" or a Split second "players can't cast spells" belongs
    # to the explained object or keyword, not to the card. card_draw keeps
    # reading the full text.
    bare = strip_reminder(o)
    if _has_card_draw(o):
        found.add("card_draw")
    if _has_card_draw(bare):
        if (
            ("instant" in t or "sorcery" in t)
            and _SINGLE_DRAW_RE.search(bare)
            and not _MULTI_OR_VAR_DRAW_RE.search(bare)
        ):
            found.add("cantrip")
        # card_advantage needs a draw for the card's own controller
        if _has_card_draw(bare, own_only=True) and (
            (_MULTI_DRAW_RE.search(bare) and not _SYMMETRIC_OR_LOOT_RE.search(bare))
            or _has_repeatable_draw_trigger(bare)
            or (
                "instant" not in t
                and "sorcery" not in t
                and _ETB_DRAW_RE.search(bare)
                and not _SYMMETRIC_OR_LOOT_RE.search(bare)
            )
        ):
            found.add("card_advantage")
    if _has_tax(o):
        found.add("tax")
    if _HATE_RE.search(bare):
        found.add("hate")
    if re.search(r"\bbattle cry\b", o) or any(
        _ANTHEM_RE.search(clause) and "until end of turn" not in clause
        for clause in re.split(r"[.\n]+", o)
    ):
        found.add("anthem")
    if _TEMP_BOOST_RE.search(o) and (
        "instant" in t or "sorcery" in t or "{" in o or "when" in o or "whenever" in o
    ):
        found.add("combat_trick")
    if re.search(r"\binvestigate\b", bare):
        found.add("card_advantage")
    if "land" not in t and (("add " in bare and "{t}:" in bare) or _TAP_ADD_RE.search(bare)):
        found.add("ramp")
        if "creature" in t:
            found.add("mana_dork")
        elif "artifact" in t:
            found.add("mana_rock")
    if _LAND_RAMP_RE.search(bare):
        found.add("land_ramp")
        found.add("ramp")
    if "land" in t and _has_utility_ability(o):
        found.add("utility_land")
    return tuple(sorted(found))


def role_origin_audit(store: StudioStore, commander: str | None = None) -> dict[str, object]:
    """Compare stored Scryfall tagger claims against deterministic Oracle text claims (#1413).

    When ``commander`` is provided, also computes pool-scoped coverage (``pool_total``,
    ``pool_tagged``, ``pool_untagged``, ``per_role_pool_counts``) and per-role tagger vs.
    Oracle overlap inside the commander's legal collection pool. Pure counts with explicit
    denominators; never guesses or changes claims.
    """
    db = store.connection
    by_origin = _claims_by_origin(db)
    tagger_by_role: dict[str, set[str]] = {}
    oracle_by_role: dict[str, set[str]] = {}
    for oracle_id, role, origin in db.execute(
        "SELECT oracle_id, role, role_origin FROM card_role_claim"
    ):
        oid, r = str(oracle_id), str(role)
        if origin in (ORIGIN_TAGGER, ORIGIN_CROSSWALK):
            tagger_by_role.setdefault(r, set()).add(oid)
        elif origin == ORIGIN_ORACLE_TEXT:
            oracle_by_role.setdefault(r, set()).add(oid)

    pool_oracle_ids: set[str] | None = None
    pool_total = 0
    pool_tagged = 0
    pool_untagged = 0
    per_role_pool_counts: dict[str, int] = {}
    pool_claims_by_origin: dict[str, int] = {}
    pool_tagger_by_role: dict[str, set[str]] = {}
    pool_oracle_by_role: dict[str, set[str]] = {}

    if commander is not None:
        cmd_row = db.execute(
            "SELECT color_identity FROM card_fact WHERE oracle_name = ?",
            (commander,),
        ).fetchone()
        if cmd_row is None:
            raise KeyError(commander)
        identity = color_set(cmd_row["color_identity"])
        roles_by_oracle: dict[str, set[str]] = {}
        for oid_val, role_val in db.execute(
            "SELECT oracle_id, role FROM card_role "
            "UNION "
            "SELECT oracle_id, role FROM card_role_claim"
        ):
            roles_by_oracle.setdefault(str(oid_val), set()).add(str(role_val))

        per_role_pool_counts = {role: 0 for role in ROLES}
        pool_oracle_ids = set()
        for card_row in db.execute(
            "SELECT c.card_id, c.oracle_id, c.color_identity "
            "FROM card_fact c JOIN inventory i USING (card_id) "
            "WHERE c.commander_legal = 1"
        ):
            if not color_set(card_row["color_identity"]) <= identity:
                continue
            pool_total += 1
            raw_oid = card_row["oracle_id"]
            if not raw_oid:
                continue
            oid = str(raw_oid)
            pool_oracle_ids.add(oid)
            card_roles = roles_by_oracle.get(oid, set())
            if card_roles:
                pool_tagged += 1
                for r in card_roles:
                    per_role_pool_counts[r] = per_role_pool_counts.get(r, 0) + 1
        pool_untagged = pool_total - pool_tagged

        for oracle_id, role, origin in db.execute(
            "SELECT oracle_id, role, role_origin FROM card_role_claim"
        ):
            oid = str(oracle_id)
            if oid not in pool_oracle_ids:
                continue
            orig = str(origin)
            r = str(role)
            pool_claims_by_origin[orig] = pool_claims_by_origin.get(orig, 0) + 1
            if orig in (ORIGIN_TAGGER, ORIGIN_CROSSWALK):
                pool_tagger_by_role.setdefault(r, set()).add(oid)
            elif orig == ORIGIN_ORACLE_TEXT:
                pool_oracle_by_role.setdefault(r, set()).add(oid)

    rows: list[dict[str, object]] = []
    for role in ROLES:
        tag_ids = tagger_by_role.get(role, set())
        ora_ids = oracle_by_role.get(role, set())
        both = len(tag_ids & ora_ids)
        entry: dict[str, object] = {
            "role": role,
            "tagger_total": len(tag_ids),
            "oracle_total": len(ora_ids),
            "both": both,
            "tagger_only": len(tag_ids - ora_ids),
            "oracle_only": len(ora_ids - tag_ids),
            "oracle_confirmed_share": round(both / len(ora_ids), 4) if ora_ids else None,
        }
        if pool_oracle_ids is not None:
            p_tag = pool_tagger_by_role.get(role, set())
            p_ora = pool_oracle_by_role.get(role, set())
            p_both = len(p_tag & p_ora)
            p_count = int(per_role_pool_counts.get(role, 0))
            entry["pool_count"] = p_count
            entry["pool_total"] = pool_total
            entry["pool_share"] = round(p_count / pool_total, 4) if pool_total else None
            entry["pool_tagger_total"] = len(p_tag)
            entry["pool_oracle_total"] = len(p_ora)
            entry["pool_both"] = p_both
            entry["pool_tagger_only"] = len(p_tag - p_ora)
            entry["pool_oracle_only"] = len(p_ora - p_tag)
        rows.append(entry)

    if pool_oracle_ids is None:
        return {"claims_by_origin": by_origin, "roles": rows}
    return {
        "commander": commander,
        "claims_by_origin": by_origin,
        "pool_claims_by_origin": pool_claims_by_origin,
        "pool_total": pool_total,
        "pool_tagged": pool_tagged,
        "pool_untagged": pool_untagged,
        "pool_coverage_share": round(pool_tagged / pool_total, 4) if pool_total else None,
        "per_role_pool_counts": per_role_pool_counts,
        "roles": rows,
    }
