"""Cardmarket link and price guide download for the TAM purchase list (#1637, WP-10b).

Synthetic values only. The link is built for the Owner's browser and never requested; a name
whose Cardmarket address is not certain gets the search page. The download asks only the two
published files, once per file, with an honest User-Agent, and stops at the first answer that
is not HTTP 200; a copy younger than 24 hours is reused.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import pytest

from commander_lab.studio import tam_cardmarket
from commander_lab.studio.tam_cardmarket import Filters

STATIC = Path(__file__).resolve().parents[2] / "src" / "commander_lab" / "studio" / "static"
OWNER_EXAMPLE = (
    "https://www.cardmarket.com/de/Magic/Cards/Rograkh-Son-of-Rohgahh"
    "?sellerCountry=7&language=1,3&minCondition=3"
)

# Real card name patterns; None: the address is not certain, the search page is used.
NAMES: tuple[tuple[str, str | None], ...] = (
    ("Rograkh, Son of Rohgahh", "Rograkh-Son-of-Rohgahh"),
    ("Tam, the Possibility", "Tam-the-Possibility"),
    ("Urza's Saga", "Urzas-Saga"),
    ("Jace, the Mind Sculptor", "Jace-the-Mind-Sculptor"),
    ("Sol Ring", "Sol-Ring"),
    ("Aetherize", "Aetherize"),
    ("Mishra's Factory", "Mishras-Factory"),
    ("Teferi, Hero of Dominaria", "Teferi-Hero-of-Dominaria"),
    ("Smothering Tithe", "Smothering-Tithe"),
    ("Counterspell", "Counterspell"),
    ("Gideon's Sacrifice", "Gideons-Sacrifice"),
    ("Circle of Protection: Red", None),  # colon
    ("Fire // Ice", None),  # split card
    ("Delver of Secrets // Insectile Aberration", None),  # double-faced
    ("Jötun Grunt", None),  # umlaut
    ("Æther Vial", None),  # ligature
    ("Lim-Dûl's Vault", None),  # hyphen and circumflex
    ("Kiki-Jiki, Mirror Breaker", None),  # hyphen
    ("Will-o'-the-Wisp", None),  # hyphen and apostrophe
    ("Borrowing 100,000 Arrows", None),  # digits
    ("Ach! Hans, Run!", None),  # exclamation marks
    ("Mr. Orfeo, the Boulder", None),  # dot
    ("Urza" + chr(0x2019) + "s Saga", None),  # curly apostrophe
    ("Sol  Ring", None),  # double space
    (" Sol Ring", None),  # leading space
    ("Rograkh,Son of Rohgahh", None),  # comma without space
    ("", None),
)


def test_card_slug_follows_the_cardmarket_convention_or_falls_back() -> None:
    assert len(NAMES) >= 20
    for name, slug in NAMES:
        assert tam_cardmarket.card_slug(name) == slug, name


def test_the_owner_example_link_and_the_search_fallback() -> None:
    url, kind = tam_cardmarket.card_link("Rograkh, Son of Rohgahh", Filters())
    assert (url, kind) == (OWNER_EXAMPLE, "karte")
    url, kind = tam_cardmarket.card_link("Fire // Ice", Filters())
    assert kind == "suche"
    assert url == (
        "https://www.cardmarket.com/de/Magic/Products/Search?searchString=Fire%20%2F%2F%20Ice"
    )
    url, _kind = tam_cardmarket.card_link("Jötun Grunt", Filters())
    assert url.endswith("searchString=J%C3%B6tun%20Grunt")
    url, _kind = tam_cardmarket.card_link("Lim-Dûl's Vault", Filters())
    assert url.endswith("searchString=Lim-D%C3%BBl%27s%20Vault")


def test_filters_only_take_known_values_and_name_their_code() -> None:
    assert Filters().code == "DE/EX/EN+DE"
    assert Filters().query == "sellerCountry=7&language=1,3&minCondition=3"
    other = Filters(country="alle", languages=("DE",), condition="NM")
    assert other.code == "alle/NM/DE" and other.query == "language=3&minCondition=2"
    none = Filters(languages=())
    assert none.code == "DE/EX/alle" and none.query == "sellerCountry=7&minCondition=3"
    # the order of the languages never changes the code
    assert Filters(languages=("DE", "EN")).code == "DE/EX/EN+DE"
    for code in ("DE/EX/EN+DE", "alle/NM/DE", "DE/PL/alle", "alle/MT/EN"):
        assert tam_cardmarket.filters_from_code(code).code == code
    for bad in ("DE/PO/EN", "FR/EX/EN", "DE/EX/FR", "DE/EX", "de/ex/en", "DE/EX/EN+DE "):
        with pytest.raises(ValueError):
            tam_cardmarket.filters_from_code(bad)
    with pytest.raises(ValueError):
        Filters(languages=("EN", "EN"))
    with pytest.raises(ValueError):
        Filters(country="7")


def _node(script: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    done = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, check=True, cwd=STATIC
    )
    return json.loads(done.stdout)


def test_the_page_builds_the_same_links_as_the_server() -> None:
    names = [name for name, _slug in NAMES]
    filters = [
        {"country": "DE", "languages": ["EN", "DE"], "condition": "EX"},
        {"country": "alle", "languages": ["DE"], "condition": "NM"},
        {"country": "DE", "languages": [], "condition": "PL"},
    ]
    script = f"""
const W = require('./wishlist.js');
const names = {json.dumps(names)};
const filters = {json.dumps(filters)};
console.log(JSON.stringify({{
  slugs: names.map((n) => W.cmSlug(n)),
  links: filters.map((f) => names.map((n) => W.cmLink(n, f))),
  codes: filters.map((f) => W.cmFilterCode(f)),
  text: W.cmFilterText(undefined),
  textOther: W.cmFilterText(filters[1]),
  garbage: W.cmFilters({{ country: '7', languages: ['FR', 'DE', 'EN', 'EN'], condition: 'PO' }}),
  notArray: W.cmFilters({{ languages: 'EN' }}),
}}));
"""
    result = _node(script)
    assert isinstance(result, dict)
    assert result["slugs"] == [slug for _name, slug in NAMES]
    for raw, links in zip(filters, result["links"], strict=True):
        chosen = Filters(
            country=str(raw["country"]),
            languages=tuple(raw["languages"]),  # type: ignore[arg-type]
            condition=str(raw["condition"]),
        )
        assert [[link["url"], link["kind"]] for link in links] == [
            list(tam_cardmarket.card_link(name, chosen)) for name in names
        ]
    assert result["links"][0][0]["url"] == OWNER_EXAMPLE
    assert result["codes"] == ["DE/EX/EN+DE", "alle/NM/DE", "DE/PL/alle"]
    assert (
        result["text"]
        == "Land: Deutschland · Sprache: Englisch, Deutsch · Mindestzustand: Excellent"
    )
    assert result["textOther"] == (
        "Land: alle Länder · Sprache: Deutsch · Mindestzustand: Near Mint (Nummer unbelegt)"
    )
    # unknown values fall back to the Owner's default, languages keep only known codes once
    assert result["garbage"] == {"country": "DE", "languages": ["EN", "DE"], "condition": "EX"}
    assert result["notArray"] == {"country": "DE", "languages": ["EN", "DE"], "condition": "EX"}


_VIEW_SCRIPT = r"""
const W = require('./wishlist.js');
function h(tag, props, ...children) {
  const el = { tag, props: props || {}, children: [] };
  el.replaceChildren = (...kids) => { el.children = kids.flat(); };
  el.children = children.flat();
  return el;
}
const text = (el) => (el === null || el === undefined || el === false) ? '' : typeof el !== 'object' ? String(el) : el.children.map(text).join(' ');
const all = (el, out = []) => { if (el && typeof el === 'object') { out.push(el); el.children.forEach((c) => all(c, out)); } return out; };
const missing = [
  { card_id: 'e', name: 'Entered Walker', missing: 1 },
  { card_id: 's', name: 'Stale Key', missing: 1 },
  { card_id: 't', name: 'Trend Only', missing: 2 },
  { card_id: 'n', name: 'Near Scryfall', missing: 1 },
  { card_id: 'u', name: 'Unknown Card', missing: 1 },
  { card_id: 'o', name: 'Owned Card', missing: 1 },
  { card_id: 'f', name: 'Fire // Ice', missing: 1 },
];
const answer = { kind: 'Näherung', notice: 'Richtwert, kein Angebot.', rule: 'r', cardmarket_notice: 'Eingetragen: abgelesen.',
  guide_notice: 'ohne Filter.',
  snapshot: { bulk_date: '2026-11-20', date_basis: 'Dateiname', imported_at: 't' },
  guide_snapshot: { guide_date: '2026-11-20', date_basis: 'createdAt', imported_at: 't', printings_known: 10, printings_matched: 8, name_mismatches: 1, name_check: true, age_days: 2, stale: false },
  cards: [
    { card_id: 'e', name: 'Entered Walker', status: 'value', eur_cents: 999, finish: 'nonfoil', printing: 'ABC 1',
      guide: { low_cents: 45, low_finish: 'nonfoil', low_printing: 'CMM 464', trend_cents: 94 },
      entered: { eur_cents: 1250, price_date: '2026-11-22', filter_code: 'DE/EX/EN+DE', age_days: 0, stale: false } },
    { card_id: 's', name: 'Stale Key', status: 'unknown',
      guide: { low_cents: 200, low_finish: 'foil', low_printing: 'XYZ 7', trend_cents: 300 },
      entered: { eur_cents: 5, price_date: '2026-10-01', filter_code: 'DE/EX/EN+DE', age_days: 52, stale: true } },
    { card_id: 't', name: 'Trend Only', status: 'unknown', guide: { low_cents: null, low_finish: '', low_printing: '', trend_cents: 700 } },
    { card_id: 'n', name: 'Near Scryfall', status: 'value', eur_cents: 150, finish: 'foil', printing: 'MH2 12' },
    { card_id: 'u', name: 'Unknown Card', status: 'unknown', entered: { eur_cents: 0, price_date: '2026-11-22', filter_code: 'DE/EX/EN+DE', age_days: 0, stale: false } },
    { card_id: 'o', status: 'owned' },
    { card_id: 'f', name: 'Fire // Ice', status: 'unknown' },
  ] };
const rows = W.tamPurchaseRows(missing, answer);
const saved = [];
const view = W.tamPurchaseView(h, answer, missing, { sort: 'price-asc', budget: '', onSave: (...args) => { saved.push(args); return Promise.resolve(answer); } });
const links = all(view).filter((el) => el.tag === 'a').map((el) => el.props);
const noGuide = W.tamPurchaseRows(missing, { ...answer, guide_snapshot: null });
const staleAnswer = { ...answer, guide_snapshot: { ...answer.guide_snapshot, stale: true, age_days: 20, name_check: false } };
const staleGuide = W.tamPurchaseRows(missing, staleAnswer);
const staleView = text(W.tamPurchaseView(h, staleAnswer, missing, { sort: 'name', budget: '' }));
const noFlag = W.tamPurchaseRows(missing, { ...answer, guide_snapshot: { ...answer.guide_snapshot, stale: undefined } });
const options = all(view).filter((el) => el.tag === 'option' && ['MT', 'NM', 'EX', 'GD', 'LP', 'PL'].includes(el.props.value)).map((el) => [el.props.value, text(el)]);
const button = all(view).find((el) => el.tag === 'button' && el.props.class === 'small tam-cm-save');
button.props.onclick();
console.log(JSON.stringify({
  rows: rows.map((r) => [r.card_id, r.status, r.basis, r.cents]),
  noGuide: noGuide.map((r) => [r.card_id, r.basis, r.cents]),
  staleGuide: staleGuide.map((r) => [r.card_id, r.basis, r.cents]),
  staleView,
  noFlag: noFlag.map((r) => r.basis),
  options,
  asc: W.sortTamRows(rows, 'price-asc').map((r) => r.card_id),
  budget: W.filterTamBudget(rows, 200).rows.map((r) => r.card_id),
  sum: W.tamSumText(W.summarizeTamRows(rows)),
  view: text(view),
  links,
  saved,
}));
"""


def test_the_view_uses_entered_then_guide_then_approximation_and_never_a_stale_entry() -> None:
    result = _node(_VIEW_SCRIPT)
    assert isinstance(result, dict)
    assert result["rows"] == [
        ["e", "value", "eingetragen", 1250],  # entered beats the guide (45) and Scryfall (999)
        ["s", "unknown", "preisfuehrer", 200],  # the stale entry (5) is never used
        ["t", "unknown", "preisfuehrer-trend", 700],  # guide without low: its trend
        ["n", "value", "naeherung", 150],  # no guide row: the Scryfall approximation
        ["u", "unknown", None, None],  # an entry of 0 is no value
        ["o", "owned", None, None],
        ["f", "unknown", None, None],
    ]
    # without a loaded price guide its rows are not used
    assert result["noGuide"][:3] == [
        ["e", "eingetragen", 1250],
        ["s", None, None],
        ["t", None, None],
    ]
    assert result["asc"] == ["n", "s", "t", "e", "f", "o", "u"]
    assert result["budget"] == ["s", "n"]
    assert result["sum"] == (
        "Summe (eingetragen, sonst Cardmarket-Preisführer, sonst Näherung): 30,00 € · "
        "1 von 6 Karten mit eingetragenem Preis · 2 Preisführer · 1 Näherung · "
        "2 von 6 Karten ohne Preis · 1 veraltete Einträge (älter als 14 Tage) nicht gezählt · "
        "1 im Besitz (kein Preis)"
    )
    view = str(result["view"])
    assert "Cardmarket DE/EX/EN+DE: 12,50 € (eingetragen am 22.11.2026)" in view
    assert (
        "Cardmarket ab 0,45 € (Trend 0,94 €) · ohne Filter Land/Sprache/Zustand · Stand 20.11.2026 · "
        "CMM 464, Nicht-Foil" in view
    )
    assert (
        "veraltet: Cardmarket DE/EX/EN+DE: 0,05 € (eingetragen am 01.10.2026), älter als 14 Tage, "
        "zählt nicht" in view
    )
    assert "Cardmarket ab unbekannt (Trend 7,00 €)" in view
    assert (
        "Näherung aus Scryfall (Cardmarket-Preisführer, kein Filter Deutschland/Excellent), "
        "Stand 2026-11-20: 1,50 € · MH2 12, Foil" in view
    )
    assert (
        "8 von 10 Drucken zugeordnet, Namen mit der Produktliste geprüft, 1 wegen abweichendem "
        "Namen ausgelassen" in view
    )
    # a price guide older than 14 days: shown and marked, never used; Scryfall steps in
    assert result["staleGuide"][:4] == [
        ["e", "eingetragen", 1250], ["s", None, None], ["t", None, None], ["n", "naeherung", 150],
    ]  # fmt: skip
    stale_view = str(result["staleView"])
    assert "veraltet (älter als 14 Tage), zählt nicht" in stale_view
    assert "veraltet: Cardmarket ab 2,00 € (Trend 3,00 €)" in stale_view
    assert "Namen nicht geprüft (ohne Produktliste)" in stale_view
    # a server without the stale flag is read as stale (fail closed)
    assert result["noFlag"][:3] == ["eingetragen", None, None]
    # only Excellent (from the Owner's link) is a confirmed condition number
    assert result["options"] == [
        ["MT", "Mint (Nummer unbelegt)"], ["NM", "Near Mint (Nummer unbelegt)"],
        ["EX", "Excellent"], ["GD", "Good (Nummer unbelegt)"],
        ["LP", "Light Played (Nummer unbelegt)"], ["PL", "Played (Nummer unbelegt)"],
    ]  # fmt: skip
    assert "Land: Deutschland · Sprache: Englisch, Deutsch · Mindestzustand: Excellent" in view
    assert not re.search(r"(?<![\d.])0,00 €", view)
    links = result["links"]
    assert isinstance(links, list) and len(links) == 6  # every card to buy, none for owned
    for link in links:
        assert link["target"] == "_blank"
        assert link["rel"] == "noopener noreferrer"
        assert link["referrerpolicy"] == "no-referrer"
        assert str(link["href"]).startswith("https://www.cardmarket.com/de/Magic/")
    fire = next(link for link in links if "Search" in str(link["href"]))
    assert fire["href"].endswith("searchString=Fire%20%2F%2F%20Ice")
    assert fire["dataset"] == {"kind": "suche"}
    # saving sends the card, the typed text, the date and the chosen filter code
    assert result["saved"][0][0] == "n" and result["saved"][0][3] == "DE/EX/EN+DE"


_ENTRY_SCRIPT = r"""
const W = require('./wishlist.js');
function h(tag, props, ...children) {
  const el = { tag, props: props || {}, children: [] };
  el.replaceChildren = (...kids) => { el.children = kids.flat(); };
  el.children = children.flat();
  return el;
}
const text = (el) => (el === null || el === undefined || el === false) ? '' : typeof el !== 'object' ? String(el) : el.children.map(text).join(' ');
const entry = (code, extra) => ({ eur_cents: 500, price_date: '2026-11-22', filter_code: code, age_days: 0, stale: false, ...extra });
const missing = ['a', 'b', 'c', 'd'].map((id) => ({ card_id: id, name: 'Card ' + id, missing: 1 }));
const answer = { cards: [
  { card_id: 'a', name: 'Card a', status: 'unknown', entered: entry('DE/EX/alle') },
  { card_id: 'b', name: 'Card b', status: 'unknown', entered: entry('alle/NM/DE', { eur_cents: 700 }) },
  { card_id: 'c', name: 'Card c', status: 'unknown', entered: entry('DE/PL/EN+DE', { eur_cents: 800 }) },
  // a server answer without the stale flag
  { card_id: 'd', name: 'Card d', status: 'unknown', entered: { eur_cents: 900, price_date: '2026-11-22', filter_code: 'DE/EX/EN+DE', age_days: 0 } },
] };
const rows = W.tamPurchaseRows(missing, answer);
console.log(JSON.stringify({
  codes: ['DE/EX/EN+DE', 'DE/EX/alle', 'alle/NM/DE', 'DE/GD/EN', ''].map(W.cmShortCode),
  rows: rows.map((r) => [r.card_id, r.basis, r.cents, Boolean(r.stale)]),
  sum: W.summarizeTamRows(rows),
  view: text(W.tamPurchaseView(h, answer, missing, { sort: 'name', budget: '' })),
}));
"""


def test_an_entry_names_all_its_filters_and_counts_only_with_a_fresh_flag() -> None:
    """Review P3-4 and P3-5(a): the label of an entry names country, condition and language
    (``DE/EX/alle`` never looks like ``DE/EX/EN+DE``), every condition but EX carries "Nummer
    unbelegt"; an entry without the stale flag is not counted (fail closed)."""
    result = _node(_ENTRY_SCRIPT)
    assert isinstance(result, dict)
    assert result["codes"] == [
        "DE/EX/EN+DE",
        "DE/EX/alle Sprachen",
        "alle Länder/NM/DE (Nummer unbelegt)",
        "DE/GD/EN (Nummer unbelegt)",
        "?/?/Sprache ? (Nummer unbelegt)",
    ]
    view = str(result["view"])
    assert "Cardmarket DE/EX/alle Sprachen: 5,00 € (eingetragen am 22.11.2026)" in view
    assert "Cardmarket alle Länder/NM/DE (Nummer unbelegt): 7,00 € (eingetragen am" in view
    assert "Cardmarket DE/PL/EN+DE (Nummer unbelegt): 8,00 € (eingetragen am" in view
    assert "Cardmarket DE/EX: " not in view
    assert result["rows"] == [
        ["a", "eingetragen", 500, False],
        ["b", "eingetragen", 700, False],
        ["c", "eingetragen", 800, False],
        ["d", None, None, True],  # no flag: shown as stale, never counted
    ]
    assert result["sum"]["stale"] == 1 and result["sum"]["sumCents"] == 2000
    assert "veraltet: Cardmarket DE/EX/EN+DE: 9,00 €" in view


# --- download --------------------------------------------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    answers: ClassVar[dict[str, tuple[int, bytes]]] = {}
    seen: ClassVar[list[tuple[str, str]]] = []
    raw: ClassVar[dict[str, bytes]] = {}  # bytes sent instead of an HTTP answer
    lengths: ClassVar[dict[str, str]] = {}  # a Content-Length that differs from the body

    def do_GET(self) -> None:
        _Handler.seen.append((self.path, str(self.headers.get("User-Agent"))))
        if self.path in _Handler.raw:
            self.wfile.write(_Handler.raw[self.path])
            return
        status, body = _Handler.answers.get(self.path, (404, b""))
        self.send_response(status)
        if status in (301, 302):
            self.send_header("Location", "/elsewhere")
        self.send_header("Content-Length", _Handler.lengths.get(self.path, str(len(body))))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        return


@pytest.fixture
def server() -> Iterator[str]:
    _Handler.answers = {}
    _Handler.seen = []
    _Handler.raw = {}
    _Handler.lengths = {}
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def _local(base: str) -> object:
    """http_get against the local test server instead of the Cardmarket host."""

    def get(url: str) -> bytes:
        return tam_cardmarket.http_get(url.replace(tam_cardmarket.DOWNLOAD_BASE, base + "/"))

    return get


def test_download_asks_once_per_file_with_an_honest_agent_and_reuses_a_fresh_copy(
    server: str, tmp_path: Path
) -> None:
    _Handler.answers = {
        "/priceGuide/price_guide_1.json": (200, b'{"priceGuides": []}'),
        "/productList/products_singles_1.json": (200, b'{"products": []}'),
    }
    report = tam_cardmarket.download(tmp_path, get=_local(server))  # type: ignore[arg-type]
    assert [r["from"] for r in report.values()] == ["download", "download"]
    assert [path for path, _agent in _Handler.seen] == [
        "/priceGuide/price_guide_1.json",
        "/productList/products_singles_1.json",
    ]
    assert {agent for _path, agent in _Handler.seen} == {tam_cardmarket.USER_AGENT}
    assert "privat" in tam_cardmarket.USER_AGENT and "Mozilla" not in tam_cardmarket.USER_AGENT
    assert (tmp_path / "price_guide_1.json").read_bytes() == b'{"priceGuides": []}'
    # a copy younger than 24 hours: no request
    again = tam_cardmarket.download(tmp_path, get=_local(server))  # type: ignore[arg-type]
    assert [r["from"] for r in again.values()] == ["cache", "cache"]
    assert len(_Handler.seen) == 2
    # one copy older than 24 hours: only that file is asked again
    old = time.time() - tam_cardmarket.CACHE_SECONDS - 60
    os.utime(tmp_path / "products_singles_1.json", (old, old))
    third = tam_cardmarket.download(tmp_path, get=_local(server))  # type: ignore[arg-type]
    assert [r["from"] for r in third.values()] == ["cache", "download"]
    assert len(_Handler.seen) == 3


@pytest.mark.parametrize("status", [403, 429, 503, 404, 302, 204])
def test_any_answer_but_200_stops_before_the_next_file(
    server: str, tmp_path: Path, status: int
) -> None:
    _Handler.answers = {
        "/priceGuide/price_guide_1.json": (
            status,
            b"<html>Attention Required! | Cloudflare</html>",
        ),
        "/productList/products_singles_1.json": (200, b'{"products": []}'),
    }
    with pytest.raises(tam_cardmarket.DownloadFailed, match="gestoppt"):
        tam_cardmarket.download(tmp_path, get=_local(server))  # type: ignore[arg-type]
    # the redirect is not followed and the second file is never asked
    assert [path for path, _agent in _Handler.seen] == ["/priceGuide/price_guide_1.json"]
    assert not (tmp_path / "price_guide_1.json").exists()


def test_the_download_asks_no_other_address(tmp_path: Path) -> None:
    with pytest.raises(tam_cardmarket.DownloadFailed, match="nur die Cardmarket-Downloads"):
        tam_cardmarket.download(
            tmp_path, urls={"x.json": "https://www.cardmarket.com/de/Magic/Cards/Sol-Ring"}
        )
    assert list(tmp_path.iterdir()) == []
    assert set(tam_cardmarket.DOWNLOADS.values()) == {
        "https://downloads.s3.cardmarket.com/productCatalog/priceGuide/price_guide_1.json",
        "https://downloads.s3.cardmarket.com/productCatalog/productList/products_singles_1.json",
    }


def test_a_refusal_is_noted_and_no_request_follows_for_a_day(server: str, tmp_path: Path) -> None:
    _Handler.answers = {
        "/priceGuide/price_guide_1.json": (429, b""),
        "/productList/products_singles_1.json": (200, b'{"products": []}'),
    }
    start = time.time()
    with pytest.raises(tam_cardmarket.DownloadFailed, match="HTTP 429"):
        tam_cardmarket.download(tmp_path, get=_local(server), now=start)  # type: ignore[arg-type]
    assert (tmp_path / tam_cardmarket.FAILURE_FILE).is_file()
    _Handler.answers["/priceGuide/price_guide_1.json"] = (200, b'{"priceGuides": []}')
    later = start + tam_cardmarket.CACHE_SECONDS - 60
    with pytest.raises(tam_cardmarket.DownloadFailed, match="kein neuer Abruf"):
        tam_cardmarket.download(tmp_path, get=_local(server), now=later)  # type: ignore[arg-type]
    assert len(_Handler.seen) == 1  # the second call asked nothing
    # a day later both files are asked again and the note is gone
    day_after = start + tam_cardmarket.CACHE_SECONDS + 60
    report = tam_cardmarket.download(tmp_path, get=_local(server), now=day_after)  # type: ignore[arg-type]
    assert [r["from"] for r in report.values()] == ["download", "download"]
    assert not (tmp_path / tam_cardmarket.FAILURE_FILE).exists()


def test_the_download_folder_never_lies_in_the_repository() -> None:
    inside = Path(__file__).resolve().parents[2] / "data" / "cardmarket-guard"
    assert not inside.exists()  # never delete a folder this test did not create
    try:
        with pytest.raises(tam_cardmarket.DownloadFailed, match="nicht im Repository"):
            tam_cardmarket.download(inside, get=lambda url: b"{}")
        assert not inside.exists()
    finally:
        # review P3-6: a broken guard must not leave the folder in the repository tree
        shutil.rmtree(inside, ignore_errors=True)


_BOTH_OK = {
    "/priceGuide/price_guide_1.json": (200, b'{"priceGuides": []}'),
    "/productList/products_singles_1.json": (200, b'{"products": []}'),
}


def test_a_broken_status_line_is_a_noted_failure(server: str, tmp_path: Path) -> None:
    """Review P2-1: an answer without a valid status line stops like a refusal: noted, and the
    next run asks nothing for 24 hours."""
    _Handler.answers = dict(_BOTH_OK)
    _Handler.raw = {"/priceGuide/price_guide_1.json": b"XYZ 200 OK\r\n\r\n{}"}
    with pytest.raises(tam_cardmarket.DownloadFailed, match="BadStatusLine"):
        tam_cardmarket.download(tmp_path, get=_local(server))  # type: ignore[arg-type]
    assert (tmp_path / tam_cardmarket.FAILURE_FILE).is_file()
    with pytest.raises(tam_cardmarket.DownloadFailed, match="kein neuer Abruf"):
        tam_cardmarket.download(tmp_path, get=_local(server))  # type: ignore[arg-type]
    assert [path for path, _agent in _Handler.seen] == ["/priceGuide/price_guide_1.json"]
    assert not (tmp_path / "price_guide_1.json").exists()


@pytest.mark.parametrize("declared", ["1000", "abc"])
def test_a_cut_off_transfer_is_a_noted_failure_not_a_copy(
    server: str, tmp_path: Path, declared: str
) -> None:
    """Review P3-2: a body shorter than its Content-Length (or an unreadable Content-Length)
    is no copy to keep for 24 hours."""
    _Handler.answers = dict(_BOTH_OK)
    _Handler.answers["/priceGuide/price_guide_1.json"] = (200, b"0123456789")
    _Handler.lengths = {"/priceGuide/price_guide_1.json": declared}
    with pytest.raises(tam_cardmarket.DownloadFailed, match="unvollständige Übertragung"):
        tam_cardmarket.download(tmp_path, get=_local(server))  # type: ignore[arg-type]
    assert not (tmp_path / "price_guide_1.json").exists()
    with pytest.raises(tam_cardmarket.DownloadFailed, match="kein neuer Abruf"):
        tam_cardmarket.download(tmp_path, get=_local(server))  # type: ignore[arg-type]
    assert len(_Handler.seen) == 1


@pytest.mark.parametrize("note", ["{kaputt", '{"at": "%s", "reason": "x"}', "[1, 2]"])
def test_an_unreadable_note_blocks_only_for_a_day_from_its_file_time(
    server: str, tmp_path: Path, note: str
) -> None:
    """Review P3-7: an unreadable note (or one dated in the future) still blocks (fail closed),
    says so honestly and lapses 24 hours after the file was written, never for good."""
    _Handler.answers = dict(_BOTH_OK)
    start = time.time()
    failure = tmp_path / tam_cardmarket.FAILURE_FILE
    failure.write_text(note.replace("%s", str(start + 1e9)), encoding="utf-8")
    with pytest.raises(tam_cardmarket.DownloadFailed, match="unlesbar") as refused:
        tam_cardmarket.download(tmp_path, get=_local(server), now=start)  # type: ignore[arg-type]
    hours = re.search(r"noch etwa (\d+) h", str(refused.value))
    assert hours is not None and 1 <= int(hours.group(1)) <= 24
    assert _Handler.seen == []
    old = start - tam_cardmarket.CACHE_SECONDS - 60
    os.utime(failure, (old, old))
    report = tam_cardmarket.download(tmp_path, get=_local(server), now=start)  # type: ignore[arg-type]
    assert [r["from"] for r in report.values()] == ["download", "download"]
    assert not failure.exists()
