"""Listed combos of a commander against one deck list.

The combos come from the commander's combo list file (``edhrec_<commander>_combos``): each
row names the full card set of one combo and the number of decks the source counted it in.
This module only compares card sets: which listed combos a deck holds completely and which
lack exactly one card. It is a count over a public list, not a rating, and a combo the
source does not list is unknown here, not absent.

Names are matched by the full card name, then by the FRONT face of a two-part card, never
by the back half.
"""

from __future__ import annotations

import functools
import json
import math
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from . import cache, decks
from .store import StudioStore

SCHEMA = "studio-deck-combos-1"
_TEMPLATES_PATH = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "research"
    / "deckbuilder_1655"
    / "spellbook_shell_templates.json"
)
_PERMANENT_TYPES = frozenset(
    {"creature", "artifact", "enchantment", "planeswalker", "land", "battle"}
)
_COMPARE_OPS = ("<=", ">=", "!=", "=", "<", ">", ":")


class UnsupportedQueryError(ValueError):
    """Raised when a Scryfall query contains syntax that cannot be evaluated offline."""


def _keys(name: str) -> list[str]:
    """The names a deck card answers to: its full name and, for a two-part card, its front
    face."""
    full = name.strip().casefold()
    front = full.split(" // ")[0].strip()
    return [full] if front == full else [full, front]


@dataclass(frozen=True)
class _Expr:
    pass


@dataclass(frozen=True)
class _And(_Expr):
    items: tuple[_Expr, ...]


@dataclass(frozen=True)
class _Or(_Expr):
    items: tuple[_Expr, ...]


@dataclass(frozen=True)
class _Not(_Expr):
    item: _Expr


@dataclass(frozen=True)
class _Term(_Expr):
    kind: str
    op: str
    value: str


def _tokenize_query(query: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    n = len(query)
    while i < n:
        ch = query[i]
        if ch.isspace():
            i += 1
            continue
        if ch in ("(", ")"):
            tokens.append(ch)
            i += 1
            continue
        if ch == "-" and i + 1 < n and query[i + 1] == "(":
            tokens.append("-(")
            i += 2
            continue
        buf: list[str] = []
        in_quote: str | None = None
        while i < n:
            c = query[i]
            if in_quote is not None:
                if c == "\\" and i + 1 < n:
                    buf.append(query[i + 1])
                    i += 2
                    continue
                if c == in_quote:
                    in_quote = None
                    i += 1
                    continue
                buf.append(c)
                i += 1
            else:
                if c.isspace() or c in ("(", ")"):
                    break
                if c in ('"', "'"):
                    in_quote = c
                    i += 1
                    continue
                if c == "/":
                    raise UnsupportedQueryError("regex syntax is not supported offline")
                buf.append(c)
                i += 1
        if in_quote is not None:
            raise UnsupportedQueryError("unclosed quote in query")
        tok = "".join(buf)
        if tok:
            tokens.append(tok)
    return tokens


_COLOR_WORDS: dict[str, str] = {
    "white": "W", "blue": "U", "black": "B", "red": "R", "green": "G", "colorless": "C",
    # guilds
    "azorius": "WU", "dimir": "UB", "rakdos": "BR", "gruul": "RG", "selesnya": "GW",
    "orzhov": "WB", "izzet": "UR", "golgari": "BG", "boros": "RW", "simic": "GU",
    # shards
    "bant": "GWU", "esper": "WUB", "grixis": "UBR", "jund": "BRG", "naya": "RGW",
    # wedges
    "abzan": "WBG", "jeskai": "URW", "sultai": "BGU", "mardu": "RWB", "temur": "GUR",
    # Strixhaven colleges
    "lorehold": "RW", "prismari": "UR", "quandrix": "GU", "silverquill": "WB",
    "witherbloom": "BG",
}  # fmt: skip
_COLOR_OPS = frozenset({":", "=", ">=", "<=", "<", ">"})


def _parse_identity_value(field: str, sep_op: str, val: str) -> _Term:
    """Scryfall color-identity value: a color or group word, or letters of ``wubrgc`` only.

    Anything else (``m``, ``multicolor``, four-color names, stray letters) cannot be
    evaluated exactly and fails closed."""
    low = val.casefold()
    letters = _COLOR_WORDS.get(low)
    if letters is None:
        if not low or not set(low) <= set("wubrgc"):
            raise UnsupportedQueryError(f"unsupported color value {field}{sep_op}{val}")
        letters = low.upper()
    if "C" in letters and set(letters) != {"C"}:
        raise UnsupportedQueryError(f"unsupported color mix with colorless {val!r}")
    wanted = "".join(sorted(set(letters)))
    if sep_op not in _COLOR_OPS:
        raise UnsupportedQueryError(f"unsupported color operator {field}{sep_op}")
    if wanted == "C" and sep_op not in {":", "="}:
        raise UnsupportedQueryError(f"unsupported colorless operator {field}{sep_op}")
    if sep_op == ":" and wanted != "C":
        raise UnsupportedQueryError("id: with ':' is not evaluated offline; use =, <= or >=")
    return _Term("identity", sep_op, wanted)


def _parse_atom(token: str) -> _Expr:
    negated = False
    raw = token
    if raw.startswith("-") and len(raw) > 1:
        negated = True
        raw = raw[1:]

    if raw.startswith("!"):
        expr: _Expr = _Term("exact_name", "=", raw[1:].strip())
        return _Not(expr) if negated else expr

    # Find earliest comparison/field separator outside quotes (quotes already stripped, keep first)
    sep_pos = -1
    sep_op = ""
    for op in _COMPARE_OPS:
        pos = raw.find(op)
        if pos > 0 and (
            sep_pos == -1 or pos < sep_pos or (pos == sep_pos and len(op) > len(sep_op))
        ):
            # Only treat as field separator if prefix looks like a field name
            prefix = raw[:pos]
            if prefix.isalpha():
                sep_pos = pos
                sep_op = op

    if sep_pos > 0:
        key = raw[:sep_pos].casefold()
        val = raw[sep_pos + len(sep_op) :]
        if not val:
            raise UnsupportedQueryError(f"empty value for {key}{sep_op}")
        if key in {"t", "type"} and sep_op == ":":
            phrase = " ".join(val.casefold().split())
            if not phrase:
                raise UnsupportedQueryError("empty type phrase")
            expr = _Term("type", ":", phrase)
        elif key in {"o", "oracle", "fo"} and sep_op == ":":
            expr = _Term("oracle", ":", val.casefold())
        elif key in {"kw", "keyword"} and sep_op == ":":
            expr = _Term("keyword", ":", val.casefold())
        elif key in {"mv", "cmc"}:
            try:
                num_val = float(val)
            except ValueError as err:
                raise UnsupportedQueryError(f"non-numeric mana value {val!r}") from err
            if not math.isfinite(num_val):
                raise UnsupportedQueryError(f"non-finite mana value {val!r}")
            norm_op = "=" if sep_op == ":" else sep_op
            expr = _Term("mv", norm_op, val)
        elif key in {"pow", "power"}:
            try:
                num_val = float(val)
            except ValueError as err:
                raise UnsupportedQueryError(f"non-numeric power {val!r}") from err
            if not math.isfinite(num_val):
                raise UnsupportedQueryError(f"non-finite power {val!r}")
            norm_op = "=" if sep_op == ":" else sep_op
            expr = _Term("power", norm_op, val)
        elif key in {"tou", "toughness"}:
            try:
                num_val = float(val)
            except ValueError as err:
                raise UnsupportedQueryError(f"non-numeric toughness {val!r}") from err
            if not math.isfinite(num_val):
                raise UnsupportedQueryError(f"non-finite toughness {val!r}")
            norm_op = "=" if sep_op == ":" else sep_op
            expr = _Term("toughness", norm_op, val)
        elif key in {"m", "mana"}:
            if sep_op not in {"=", ":"}:
                raise UnsupportedQueryError(f"unsupported mana operator {key}{sep_op}")
            expr = _Term("mana", sep_op, val.upper())
        elif key in {"id", "identity", "ci"}:
            expr = _parse_identity_value(key, sep_op, val)
        elif key in {"c", "color"}:
            # Card color is not exact from mana_cost alone (color indicator, Prepare
            # layout, DFC faces): needs Scryfall ``colors``. Fail closed.
            raise UnsupportedQueryError(f"card color {key}{sep_op}{val} is not evaluated offline")
        elif key == "is" and sep_op == ":":
            low = val.casefold()
            if low not in {"permanent", "spell", "commander"}:
                raise UnsupportedQueryError(f"unsupported is:{val}")
            expr = _Term("is", ":", low)
        elif key in {"f", "format", "legal"} and sep_op == ":" and val.casefold() == "commander":
            expr = _Term("legal", ":", "commander")
        else:
            raise UnsupportedQueryError(f"unsupported Scryfall operator {key}{sep_op}{val}")
        return _Not(expr) if negated else expr

    raise UnsupportedQueryError(f"bare or unsupported query token {raw!r}")


class _Parser:
    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def next(self) -> str:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def parse(self) -> _Expr:
        if not self.tokens:
            raise UnsupportedQueryError("empty query")
        expr = self._parse_or()
        if self.pos < len(self.tokens):
            raise UnsupportedQueryError(f"unexpected token {self.tokens[self.pos]!r}")
        return expr

    def _parse_or(self) -> _Expr:
        items = [self._parse_and()]
        while (tok := self.peek()) is not None and tok.upper() == "OR":
            self.next()
            items.append(self._parse_and())
        return items[0] if len(items) == 1 else _Or(tuple(items))

    def _parse_and(self) -> _Expr:
        items: list[_Expr] = []
        while (tok := self.peek()) is not None:
            if tok == ")" or tok.upper() == "OR":
                break
            items.append(self._parse_factor())
        if not items:
            raise UnsupportedQueryError("empty group in query")
        return items[0] if len(items) == 1 else _And(tuple(items))

    def _parse_factor(self) -> _Expr:
        tok = self.next()
        if tok == "(":
            inner = self._parse_or()
            if self.peek() != ")":
                raise UnsupportedQueryError("unclosed parenthesis in query")
            self.next()
            return inner
        if tok == "-(":
            inner = self._parse_or()
            if self.peek() != ")":
                raise UnsupportedQueryError("unclosed negated parenthesis in query")
            self.next()
            return _Not(inner)
        if tok == ")" or tok.upper() == "OR":
            raise UnsupportedQueryError(f"unexpected token {tok!r}")
        return _parse_atom(tok)


def _num_cmp(op: str, lhs: float, rhs: float) -> bool:
    if op == "=":
        return lhs == rhs
    if op == "!=":
        return lhs != rhs
    if op == "<=":
        return lhs <= rhs
    if op == "<":
        return lhs < rhs
    if op == ">=":
        return lhs >= rhs
    if op == ">":
        return lhs > rhs
    return False


def _color_cmp(op: str, have: set[str], wanted: set[str]) -> bool:
    """Scryfall color set comparison; ``:`` means "at least these" (``>=``)."""
    if op == "=":
        return have == wanted
    if op == "<=":
        return have <= wanted
    if op == "<":
        return have < wanted
    if op == ">":
        return have > wanted
    return wanted <= have


def _eval_term(term: _Term, card: Mapping[str, object]) -> bool:
    kind = term.kind
    if kind == "exact_name":
        target = term.value.casefold()
        name = str(card.get("name") or "").casefold()
        front = str(card.get("front_name") or "").casefold()
        return name == target or (front != "" and front == target)
    if kind == "type":
        # Scryfall type search is a case-insensitive substring match on the type line.
        return term.value in " ".join(str(card.get("type_line") or "").casefold().split())
    if kind == "oracle":
        oracle = str(card.get("oracle_text") or "").casefold()
        needle = term.value.replace("~", str(card.get("name") or "").casefold())
        return needle in oracle
    if kind == "keyword":
        kws = card.get("keywords")
        kw_set = set(kws) if isinstance(kws, (set, frozenset, list, tuple)) else set()
        return term.value in kw_set
    if kind == "mv":
        val = card.get("mana_value")
        if val is None:
            return False
        return _num_cmp(term.op, float(val), float(term.value))  # type: ignore[arg-type]
    if kind == "power":
        raw = str(card.get("power") or "").strip()
        try:
            num = float(raw)
        except ValueError:
            return False
        return _num_cmp(term.op, num, float(term.value))
    if kind == "toughness":
        raw = str(card.get("toughness") or "").strip()
        try:
            num = float(raw)
        except ValueError:
            return False
        return _num_cmp(term.op, num, float(term.value))
    if kind == "mana":
        cost = str(card.get("mana_cost") or "").upper()
        if not cost:
            return False
        if term.op == "=":
            return cost == term.value
        return term.value in cost
    if kind == "identity":
        raw_set = card.get("identity")
        have: set[str] = (
            {str(x) for x in raw_set}
            if isinstance(raw_set, (set, frozenset, list, tuple))
            else set()
        )
        if term.value == "C":
            return not have
        return _color_cmp(term.op, have, set(term.value))
    if kind == "is":
        tl_words = {
            part.strip().casefold()
            for part in str(card.get("type_line") or "").replace("—", " ").split()
        }
        if term.value == "permanent":
            return bool(tl_words & _PERMANENT_TYPES)
        if term.value == "spell":
            return "land" not in tl_words and bool(tl_words)
        if term.value == "commander":
            return "legendary" in tl_words and (
                "creature" in tl_words
                or "can be your commander" in str(card.get("oracle_text") or "").casefold()
            )
    if kind == "legal":
        return bool(card.get("commander_legal"))
    return False


def _eval_expr(expr: _Expr, card: Mapping[str, object]) -> bool:
    if isinstance(expr, _Term):
        return _eval_term(expr, card)
    if isinstance(expr, _Not):
        return not _eval_expr(expr.item, card)
    if isinstance(expr, _And):
        return all(_eval_expr(item, card) for item in expr.items)
    if isinstance(expr, _Or):
        return any(_eval_expr(item, card) for item in expr.items)
    return False


def compile_scryfall_query(query: str | None) -> _Expr:
    """Parse ``query`` into an AST or raise :class:`UnsupportedQueryError` (fail closed)."""
    if query is None or not str(query).strip():
        raise UnsupportedQueryError("NO_SCRYFALL_QUERY")
    tokens = _tokenize_query(str(query).strip())
    return _Parser(tokens).parse()


def evaluate_scryfall_query(
    query: str | None, cards: Sequence[Mapping[str, object]]
) -> tuple[str, str | None, list[Mapping[str, object]]]:
    """Evaluate ``query`` strictly offline against ``cards``.

    Returns ``(status, reason, matching_cards)``. Any unsupported or missing query fails
    closed with ``status="UNKNOWN"``, never ``0``."""
    if query is None or not str(query).strip():
        return ("UNKNOWN", "NO_SCRYFALL_QUERY", [])
    try:
        ast = compile_scryfall_query(query)
    except UnsupportedQueryError as err:
        return ("UNKNOWN", f"UNSUPPORTED_QUERY: {err}", [])
    matched = [card for card in cards if _eval_expr(ast, card)]
    return ("OK", None, matched)


def _parse_keywords(raw: object) -> frozenset[str]:
    if not raw:
        return frozenset()
    if isinstance(raw, (list, tuple, set, frozenset)):
        return frozenset(str(item).strip().casefold() for item in raw if str(item).strip())
    text = str(raw).strip()
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return frozenset(
                    str(item).strip().casefold() for item in parsed if str(item).strip()
                )
        except json.JSONDecodeError:
            pass
    return frozenset(part.strip().casefold() for part in text.split(",") if part.strip())


@functools.lru_cache(maxsize=4)
def _load_template_snapshot(path_str: str) -> dict[str, object] | None:
    path = Path(path_str)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


type _CatalogRow = tuple[
    str, str, str, str, float | None, str, str, frozenset[str], bool, frozenset[str],
    object, object, int, int,
]  # fmt: skip


def _catalog_rows(
    store: StudioStore, commanders: Sequence[str]
) -> tuple[frozenset[str], tuple[_CatalogRow, ...]]:
    """The commander identity and every collection card with its normalized metadata (owned
    count last), as immutable tuples. Remembered per store state and commanders (#1563): the
    two callers of one request and later requests share one read."""

    def compute() -> tuple[frozenset[str], tuple[_CatalogRow, ...]]:
        db = store.connection
        has_scryfall_join = (
            db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='scryfall_card'"
            ).fetchone()
            is not None
        )
        identity: frozenset[str] = frozenset()
        if commanders:
            rows_cmd = db.execute(
                f"SELECT color_identity FROM card_fact WHERE oracle_name IN ({','.join('?' for _ in commanders)})",
                tuple(commanders),
            ).fetchall()
            merged: set[str] = set()
            for r in rows_cmd:
                merged.update(decks.color_set(r["color_identity"]))
            identity = frozenset(merged)

        if has_scryfall_join:
            sql = (
                "SELECT c.card_id, c.oracle_name, c.mana_cost, c.mana_value, c.type_line, "
                "c.oracle_text, c.color_identity, c.commander_legal, "
                "i.owned_lower_bound, i.available_lower_bound, "
                "s.front_name, s.keywords, s.power, s.toughness "
                "FROM card_fact c "
                "JOIN inventory i USING (card_id) "
                "LEFT JOIN scryfall_card s USING (oracle_id) "
                "ORDER BY c.oracle_name"
            )
        else:
            sql = (
                "SELECT c.card_id, c.oracle_name, c.mana_cost, c.mana_value, c.type_line, "
                "c.oracle_text, c.color_identity, c.commander_legal, "
                "i.owned_lower_bound, i.available_lower_bound, "
                "NULL AS front_name, '[]' AS keywords, NULL AS power, NULL AS toughness "
                "FROM card_fact c JOIN inventory i USING (card_id) ORDER BY c.oracle_name"
            )
        rows: list[_CatalogRow] = []
        for r in db.execute(sql):
            rows.append(
                (
                    str(r["card_id"]),
                    str(r["oracle_name"]),
                    str(r["front_name"] or ""),
                    str(r["mana_cost"] or ""),
                    float(r["mana_value"]) if r["mana_value"] is not None else None,
                    str(r["type_line"] or ""),
                    str(r["oracle_text"] or ""),
                    decks.color_set(r["color_identity"]),
                    bool(r["commander_legal"]),
                    _parse_keywords(r["keywords"]),
                    r["power"],
                    r["toughness"],
                    int(r["available_lower_bound"] or 0),
                    int(r["owned_lower_bound"] or 0),
                )
            )
        return identity, tuple(rows)

    return cache.cached(store, ("slot_catalog", tuple(commanders)), compute)


def _card_catalog_for_slots(
    store: StudioStore,
    commanders: Sequence[str],
    deck_ids: set[str],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    """Return ``(deck_cards, pool_cards, collection_cards)`` with normalized metadata. The rows
    are remembered (``_catalog_rows``); the dictionaries are new on every call."""
    identity, rows = _catalog_rows(store, commanders)
    collection: list[dict[str, object]] = []
    pool: list[dict[str, object]] = []
    deck: list[dict[str, object]] = []
    for (
        cid, name, front_name, mana_cost, mana_value, type_line, oracle_text, card_id_colors,
        commander_legal, keywords, power, toughness, available, owned,
    ) in rows:  # fmt: skip
        in_deck = cid in deck_ids
        if owned <= 0 and not in_deck:
            continue
        item: dict[str, object] = {
            "card_id": cid,
            "name": name,
            "front_name": front_name,
            "mana_cost": mana_cost,
            "mana_value": mana_value,
            "type_line": type_line,
            "oracle_text": oracle_text,
            "identity": card_id_colors,
            "commander_legal": commander_legal,
            "keywords": keywords,
            "power": power,
            "toughness": toughness,
            "available": available,
            "in_deck": in_deck,
        }
        collection.append(item)
        if in_deck:
            deck.append(item)
        if owned > 0 and commander_legal and (not commanders or card_id_colors <= identity):
            pool.append(item)
    return deck, pool, collection


def _spellbook_shells_section(
    store: StudioStore,
    commanders: Sequence[str],
    deck_ids: set[str],
    deck_names_cf: set[str],
    template_snapshot_path: Path | None,
) -> tuple[str, list[dict[str, object]], list[dict[str, object]]]:
    snap_path = template_snapshot_path if template_snapshot_path is not None else _TEMPLATES_PATH
    snap = _load_template_snapshot(str(snap_path))
    if snap is None:
        return ("NOT_COLLECTED", [], [])
    snap_cmd = str(snap.get("commander") or "").strip()
    if snap_cmd and not any(c.strip().casefold() == snap_cmd.casefold() for c in commanders):
        return ("NOT_COLLECTED", [], [])

    deck_cards, pool_cards, collection_cards = _card_catalog_for_slots(store, commanders, deck_ids)
    avail_by_cf: dict[str, int] = {
        str(c["name"]).casefold(): int(str(c["available"] or 0)) for c in pool_cards
    }
    id_by_cf: dict[str, str] = {str(c["name"]).casefold(): str(c["card_id"]) for c in pool_cards}

    pool_shells_out: list[dict[str, object]] = []
    for raw_shell in snap.get("pool_shells") or []:  # type: ignore[attr-defined]
        if not isinstance(raw_shell, Mapping):
            continue
        uses = [str(u) for u in (raw_shell.get("uses") or [])]
        in_deck = [u for u in uses if any(k in deck_names_cf for k in _keys(u))]
        missing = [u for u in uses if not any(k in deck_names_cf for k in _keys(u))]
        pool_shells_out.append(
            {
                "shell_id": raw_shell.get("shell_id"),
                "variant_id": raw_shell.get("variant_id"),
                "uses": uses,
                "in_deck": in_deck,
                "missing_from_deck": missing,
                "available_missing": {
                    m: {
                        "card_id": id_by_cf.get(m.casefold()),
                        "available": avail_by_cf.get(m.casefold(), 0),
                    }
                    for m in missing
                },
                "complete_in_deck": len(missing) == 0,
                "with_commander": bool(raw_shell.get("with_commander")),
                "produces": list(raw_shell.get("produces") or []),
            }
        )
    pool_shells_out.sort(
        key=lambda item: (
            len(item["missing_from_deck"]),  # type: ignore[arg-type]
            -len(item["uses"]),  # type: ignore[arg-type]
            int(str(item["shell_id"] or 0)),
        )
    )

    slot_cache: dict[str, dict[str, object]] = {}

    def _eval_req(req: Mapping[str, object]) -> dict[str, object]:
        query = req.get("scryfall_query")
        q_str = str(query) if isinstance(query, str) and query.strip() else None
        q_key = q_str or "<NONE>"
        if q_key not in slot_cache:
            d_status, d_reason, d_hits = evaluate_scryfall_query(q_str, deck_cards)
            p_status, p_reason, p_hits = evaluate_scryfall_query(q_str, pool_cards)
            c_status, c_reason, c_hits = evaluate_scryfall_query(q_str, collection_cards)
            status = "OK" if d_status == p_status == c_status == "OK" else "UNKNOWN"
            reason = d_reason or p_reason or c_reason
            p_sorted = sorted(
                p_hits,
                key=lambda item: (
                    0 if not item["in_deck"] and int(str(item["available"] or 0)) > 0 else 1,
                    str(item["name"]),
                ),
            )
            slot_cache[q_key] = {
                "status": status,
                "reason": reason,
                "deck": {"hits": len(d_hits) if status == "OK" else None, "total": len(deck_cards)},
                "pool": {"hits": len(p_hits) if status == "OK" else None, "total": len(pool_cards)},
                "collection": {
                    "hits": len(c_hits) if status == "OK" else None,
                    "total": len(collection_cards),
                },
                "matches_in_deck": [{"card_id": c["card_id"], "name": c["name"]} for c in d_hits]
                if status == "OK"
                else [],
                "matches_in_pool": [
                    {
                        "card_id": c["card_id"],
                        "name": c["name"],
                        "available": c["available"],
                        "in_deck": c["in_deck"],
                    }
                    for c in p_sorted[:25]
                ]
                if status == "OK"
                else [],
                "matches_in_pool_total": len(p_hits) if status == "OK" else None,
            }
        cached = slot_cache[q_key]
        qty = int(str(req.get("quantity") or 1))
        deck_hits_val = cached["deck"]["hits"]  # type: ignore[index]
        fulfilled = (
            cached["status"] == "OK" and isinstance(deck_hits_val, int) and deck_hits_val >= qty
        )
        raw_zones = req.get("zone_locations")
        zones = [str(z) for z in raw_zones] if isinstance(raw_zones, (list, tuple)) else []
        return {
            "template_id": req.get("template_id"),
            "name": req.get("name"),
            "scryfall_query": q_str,
            "quantity": qty,
            "must_be_commander": bool(req.get("must_be_commander")),
            "zone_locations": zones,
            # The evaluator only checks card text: a commander or zone condition of the slot
            # is not checked, so "fulfilled" is only partly verified.
            "partially_checked": bool(req.get("must_be_commander")) or bool(zones),
            "fulfilled_in_deck": fulfilled,
            **cached,
        }

    template_slots_out: list[dict[str, object]] = []
    for raw_tpl in snap.get("template_shells") or []:  # type: ignore[attr-defined]
        if not isinstance(raw_tpl, Mapping):
            continue
        uses = [str(u) for u in (raw_tpl.get("uses") or [])]
        missing_pool = [str(u) for u in (raw_tpl.get("missing_from_pool") or [])]
        if len(missing_pool) > 1:
            # Show shells whose concrete pieces exist in pool first; still allow missing<=1
            continue
        in_deck = [u for u in uses if any(k in deck_names_cf for k in _keys(u))]
        missing_deck = [u for u in uses if not any(k in deck_names_cf for k in _keys(u))]
        slots = [
            _eval_req(req) for req in (raw_tpl.get("requires") or []) if isinstance(req, Mapping)
        ]
        if not slots:
            continue
        template_slots_out.append(
            {
                "shell_id": raw_tpl.get("shell_id"),
                "variant_id": raw_tpl.get("variant_id"),
                "uses": uses,
                "in_deck": in_deck,
                "missing_from_deck": missing_deck,
                "missing_from_pool": missing_pool,
                "available_missing": {
                    m: {
                        "card_id": id_by_cf.get(m.casefold()),
                        "available": avail_by_cf.get(m.casefold(), 0),
                    }
                    for m in missing_deck
                    if m not in missing_pool
                },
                "concrete_complete": len(missing_deck) == 0,
                "with_commander": bool(raw_tpl.get("with_commander")),
                "produces": list(raw_tpl.get("produces") or []),
                "slots": slots,
            }
        )
    template_slots_out.sort(
        key=lambda item: (
            len(item["missing_from_pool"]),  # type: ignore[arg-type]
            len(item["missing_from_deck"]),  # type: ignore[arg-type]
            0 if all(s["fulfilled_in_deck"] for s in item["slots"]) else 1,  # type: ignore[attr-defined]
            int(str(item["shell_id"] or 0)),
        )
    )
    return ("OK", pool_shells_out, template_slots_out)


def stored_combos(store: StudioStore, commander: str) -> list[tuple[list[str], int]]:
    """Every stored combo of ``commander``: (card names, deck count), in list order."""
    rows = store.connection.execute(
        "SELECT cards, num_decks FROM commander_combo WHERE commander_name = ? COLLATE NOCASE "
        "ORDER BY ordinal",
        (commander,),
    ).fetchall()
    found: list[tuple[list[str], int]] = []
    for row in rows:
        # A damaged row (no JSON list of names, no count) is skipped: it must not take the
        # deck check down with it.
        try:
            cards = json.loads(row["cards"])
            decks = int(row["num_decks"])
        except (TypeError, ValueError):
            continue
        if not isinstance(cards, list) or not cards:
            continue
        if not all(isinstance(name, str) and name.strip() for name in cards):
            continue
        found.append((list(cards), decks))
    return found


def combo_sources(store: StudioStore, commanders: Iterable[str]) -> list[dict[str, object]]:
    """Where the stored combo list of each commander comes from: the imported source file's
    title and times. Empty without a stored list."""
    found: dict[str, dict[str, object]] = {}
    for commander in commanders:
        for row in store.connection.execute(
            "SELECT DISTINCT s.source_id, s.title, s.snapshot_date, s.imported_at "
            "FROM commander_combo c JOIN source s USING (source_id) "
            "WHERE c.commander_name = ? COLLATE NOCASE ORDER BY s.imported_at",
            (commander,),
        ):
            found.setdefault(
                str(row["source_id"]),
                {
                    "title": str(row["title"]),
                    "snapshot_date": row["snapshot_date"],
                    "imported_at": str(row["imported_at"]),
                },
            )
    return list(found.values())


def _completion_candidates(
    store: StudioStore,
    commanders: Sequence[str],
    deck_ids: set[str],
    one_missing: Sequence[Mapping[str, object]],
    pool_shells: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Aggregate free legal pool cards by how many 1-missing combos and pool shells they complete."""
    if not one_missing and not pool_shells:
        return []
    _deck_cards, pool_cards, _collection_cards = _card_catalog_for_slots(
        store, commanders, deck_ids
    )
    free_by_key: dict[str, dict[str, object]] = {}
    for p in pool_cards:
        if p.get("in_deck") or int(str(p.get("available") or 0)) <= 0:
            continue
        for k in _keys(str(p["name"])):
            free_by_key.setdefault(k, p)

    by_cid: dict[str, dict[str, object]] = {}

    def _bucket(p: Mapping[str, object]) -> dict[str, object]:
        cid = str(p["card_id"])
        if cid not in by_cid:
            by_cid[cid] = {
                "card_id": cid,
                "name": str(p["name"]),
                "mana_value": p.get("mana_value"),
                "available": int(str(p.get("available") or 0)),
                "completed_combos": [],
                "completed_shells": [],
            }
        return by_cid[cid]

    combos_by_cid: dict[str, list[dict[str, object]]] = {}
    shells_by_cid: dict[str, list[dict[str, object]]] = {}

    for combo in one_missing:
        missing_name = str(combo.get("missing") or "").strip().casefold()
        found = free_by_key.get(missing_name)
        if found is None:
            continue
        entry = _bucket(found)
        cid = str(entry["card_id"])
        raw_cards = combo.get("cards")
        cards_list = (
            [str(x) for x in raw_cards]
            if isinstance(raw_cards, Sequence) and not isinstance(raw_cards, str)
            else []
        )
        combos_by_cid.setdefault(cid, []).append(
            {
                "cards": cards_list,
                "num_decks": int(str(combo.get("num_decks") or 0)),
            }
        )

    for sh in pool_shells:
        missing_list = sh.get("missing_from_deck")
        if not isinstance(missing_list, Sequence) or len(missing_list) != 1:
            continue
        missing_name = str(missing_list[0]).strip().casefold()
        found = free_by_key.get(missing_name)
        if found is None:
            continue
        entry = _bucket(found)
        cid = str(entry["card_id"])
        raw_uses = sh.get("uses")
        uses_list = (
            [str(x) for x in raw_uses]
            if isinstance(raw_uses, Sequence) and not isinstance(raw_uses, str)
            else []
        )
        raw_produces = sh.get("produces")
        produces_list = (
            [str(x) for x in raw_produces]
            if isinstance(raw_produces, Sequence) and not isinstance(raw_produces, str)
            else []
        )
        shells_by_cid.setdefault(cid, []).append(
            {
                "shell_id": sh.get("shell_id"),
                "uses": uses_list,
                "produces": produces_list,
            }
        )

    ranked: list[tuple[int, int, int, str, dict[str, object]]] = []
    for cid, item in by_cid.items():
        c_combos = combos_by_cid.get(cid, [])
        c_shells = shells_by_cid.get(cid, [])
        item["completed_combos"] = c_combos
        item["completed_shells"] = c_shells
        n_combos = len(c_combos)
        n_shells = len(c_shells)
        total = n_combos + n_shells
        max_decks = max((int(str(x["num_decks"])) for x in c_combos), default=0)
        name = str(item["name"])
        ranked.append(
            (
                -total,
                -n_combos,
                -max_decks,
                name,
                {
                    **item,
                    "completed_combos_count": n_combos,
                    "completed_shells_count": n_shells,
                    "total_completed": total,
                    "max_num_decks": max_decks,
                },
            )
        )
    ranked.sort(key=lambda r: r[:4])
    return [r[4] for r in ranked]


def deck_combos(
    store: StudioStore,
    rows: Sequence[sqlite3.Row],
    commanders: Iterable[str] | None = None,
    *,
    template_snapshot_path: Path | None = None,
) -> dict[str, object]:
    """Listed combos of the deck's commander(s): complete in the deck, or one card short,
    plus qualifying Commander Spellbook shells & template slots (#1417, B-7).

    ``rows`` are the deck rows (``oracle_name``, ``zone``). The commander is taken from the
    rows of zone ``commander`` unless ``commanders`` names it. Without a stored combo list
    the result says so (``listed`` 0), it never reports "no combos".
    """
    names: set[str] = set()
    deck_ids: set[str] = set()
    for row in rows:
        names.update(_keys(str(row["oracle_name"])))
        try:
            cid = row["card_id"]
        except (KeyError, IndexError):
            cid = None
        if cid:
            deck_ids.add(str(cid))
    chosen = (
        list(commanders)
        if commanders is not None
        else [str(row["oracle_name"]) for row in rows if row["zone"] == "commander"]
    )
    complete: list[dict[str, object]] = []
    one_missing: list[dict[str, object]] = []
    listed = 0
    seen: set[str] = set()
    for commander in chosen:
        for cards, num_decks in stored_combos(store, commander):
            key = json.dumps(sorted(name.casefold() for name in cards))
            if key in seen:
                continue
            seen.add(key)
            listed += 1
            missing = [name for name in cards if name.strip().casefold() not in names]
            entry: dict[str, object] = {"cards": cards, "num_decks": num_decks}
            if not missing:
                complete.append(entry)
            elif len(missing) == 1:
                one_missing.append({**entry, "missing": missing[0]})
    complete.sort(key=lambda item: (-int(str(item["num_decks"])), str(item["cards"])))
    one_missing.sort(key=lambda item: (-int(str(item["num_decks"])), str(item["cards"])))

    template_status, pool_shells, template_slots = _spellbook_shells_section(
        store, chosen, deck_ids, names, template_snapshot_path
    )
    completion_candidates = _completion_candidates(
        store, chosen, deck_ids, one_missing, pool_shells
    )
    return {
        "schema": SCHEMA,
        "commanders": chosen,
        "listed": listed,
        "sources": combo_sources(store, chosen),
        "complete": complete,
        "one_missing": one_missing,
        "completion_candidates": completion_candidates,
        "template_status": template_status,
        "pool_shells": pool_shells,
        "template_slots": template_slots,
        "meaning": (
            "Vergleich mit der Kombo-Liste der Quelle für diesen Commander. Gezählt wird nur, "
            "was die Quelle listet; eine nicht gelistete Kombo ist hier unbekannt. Die Deckzahl "
            "ist die Zahl der Decks, in denen die Quelle die Kombo gezählt hat. Keine Bewertung."
        ),
    }
