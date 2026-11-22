"""Cardmarket links and the official price guide download for the TAM purchase list (#1637).

Register ``docs/OWNER_DECISIONS_STUDIO_20261118.md``, entry "Preise für TAM", and the Owner
exception of 2026-11-22. Two things only:

* :func:`card_link` builds the address of the Cardmarket card page with the Owner's filters
  (seller country, languages, minimum condition) for the Owner's own browser; the Studio never
  requests that page. A name whose address is not certain gets the search page instead.
* :func:`download` fetches the two files Cardmarket publishes for download (price guide and
  singles product list, ``downloads.s3.cardmarket.com``) on the Owner's command, once per file,
  with an honest User-Agent, no cookies, no account, no key, no proxy and no redirect; a copy
  younger than 24 hours in the local data folder is used instead of a new request; any status
  other than 200 stops at once and is noted, so no new request follows for 24 hours (at most one
  request per file and day). No page of www.cardmarket.com is read (no scraping).

This module is the only place of ``src`` that talks HTTP to a Cardmarket host.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

HOST = "www.cardmarket.com"
CARD_BASE = f"https://{HOST}/de/Magic/Cards/"
SEARCH_BASE = f"https://{HOST}/de/Magic/Products/Search?searchString="
DOWNLOAD_BASE = "https://downloads.s3.cardmarket.com/productCatalog/"
PRICE_GUIDE_FILE = "price_guide_1.json"
PRODUCT_LIST_FILE = "products_singles_1.json"
DOWNLOADS = {
    PRICE_GUIDE_FILE: DOWNLOAD_BASE + "priceGuide/" + PRICE_GUIDE_FILE,
    PRODUCT_LIST_FILE: DOWNLOAD_BASE + "productList/" + PRODUCT_LIST_FILE,
}
USER_AGENT = "CommanderStudio/1.0 (privat; lokales Einzelnutzer-Werkzeug; Abruf nur auf Befehl)"
CACHE_SECONDS = 24 * 3600
TIMEOUT_SECONDS = 120
MAX_BYTES = 200_000_000

# Filter values of the Owner's example link (sellerCountry=7 Deutschland, language=1,3
# Englisch/Deutsch, minCondition=3 Excellent). The other condition numbers follow Cardmarket's
# condition order (Mint 1 ... Played 6) and are not checked against a live page (UNKNOWN).
COUNTRIES: dict[str, tuple[str | None, str]] = {
    "DE": ("7", "Deutschland"),
    "alle": (None, "alle Länder"),
}
LANGUAGES: dict[str, tuple[str, str]] = {"EN": ("1", "Englisch"), "DE": ("3", "Deutsch")}
CONDITIONS: dict[str, tuple[str, str]] = {
    "MT": ("1", "Mint"),
    "NM": ("2", "Near Mint"),
    "EX": ("3", "Excellent"),
    "GD": ("4", "Good"),
    "LP": ("5", "Light Played"),
    "PL": ("6", "Played"),
}


@dataclass(frozen=True, slots=True)
class Filters:
    """The Cardmarket filters of a link: seller country, languages (empty: all), minimum
    condition. Only the values above are accepted."""

    country: str = "DE"
    languages: tuple[str, ...] = ("EN", "DE")
    condition: str = "EX"

    def __post_init__(self) -> None:
        if self.country not in COUNTRIES:
            raise ValueError(f"unknown country filter: {self.country!r}")
        if self.condition not in CONDITIONS:
            raise ValueError(f"unknown condition filter: {self.condition!r}")
        if len(set(self.languages)) != len(self.languages) or any(
            code not in LANGUAGES for code in self.languages
        ):
            raise ValueError(f"unknown language filter: {self.languages!r}")

    @property
    def ordered_languages(self) -> tuple[str, ...]:
        return tuple(code for code in LANGUAGES if code in self.languages)

    @property
    def code(self) -> str:
        """``DE/EX/EN+DE``: country, minimum condition, languages (``alle`` when none)."""
        languages = "+".join(self.ordered_languages) or "alle"
        return f"{self.country}/{self.condition}/{languages}"

    @property
    def query(self) -> str:
        parts = []
        country = COUNTRIES[self.country][0]
        if country is not None:
            parts.append(f"sellerCountry={country}")
        if self.languages:
            parts.append("language=" + ",".join(LANGUAGES[c][0] for c in self.ordered_languages))
        parts.append(f"minCondition={CONDITIONS[self.condition][0]}")
        return "&".join(parts)


_FILTER_CODE = re.compile(r"(DE|alle)/(MT|NM|EX|GD|LP|PL)/(EN\+DE|EN|DE|alle)", re.ASCII)


def filters_from_code(code: str) -> Filters:
    match = _FILTER_CODE.fullmatch(code)
    if match is None:
        raise ValueError(f"unknown filter code: {code!r}")
    languages = () if match.group(3) == "alle" else tuple(match.group(3).split("+"))
    return Filters(country=match.group(1), languages=languages, condition=match.group(2))


# A card name whose Cardmarket address is known for sure: ASCII words joined by a space, ", " or
# a straight apostrophe ("Rograkh, Son of Rohgahh" -> Rograkh-Son-of-Rohgahh, "Urza's Saga" ->
# Urzas-Saga). Everything else (//, colon, hyphen, digits, dots, umlauts, Æ, curly quotes, !)
# gets the Cardmarket search page instead of a guessed address.
_SAFE_NAME = re.compile(r"[A-Za-z]+(?:(?:, | |')[A-Za-z]+)*", re.ASCII)


def card_slug(name: str) -> str | None:
    """The Cardmarket address part of a card name, or ``None`` when it is not certain."""
    if not _SAFE_NAME.fullmatch(name):
        return None
    return name.replace(",", "").replace("'", "").replace(" ", "-")


def card_link(name: str, filters: Filters) -> tuple[str, str]:
    """(url, kind): the filtered card page (``karte``) or, when the address is not certain, the
    search page (``suche``; the filters are chosen there)."""
    slug = card_slug(name)
    if slug is None:
        return SEARCH_BASE + urllib.parse.quote(name, safe=""), "suche"
    return f"{CARD_BASE}{slug}?{filters.query}", "karte"


# --- official download ------------------------------------------------------------------------


class DownloadFailed(RuntimeError):
    """A download answered anything but HTTP 200 (or failed): nothing further is requested."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


# no proxy, no cookie jar, no redirect: only the plain handlers
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def http_get(url: str) -> bytes:
    """One GET with the honest User-Agent; the body of an HTTP 200 answer, else
    :class:`DownloadFailed` (403, 429, a redirect and every other status stop)."""
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    try:
        with _OPENER.open(request, timeout=TIMEOUT_SECONDS) as response:
            status = int(response.status)
            body: bytes = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        raise DownloadFailed(f"HTTP {error.code} für {url}: Abruf gestoppt") from None
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise DownloadFailed(f"keine Verbindung zu {url}: {type(error).__name__}") from None
    if status != 200:
        raise DownloadFailed(f"HTTP {status} für {url}: Abruf gestoppt")
    if len(body) > MAX_BYTES:
        raise DownloadFailed(f"Datei zu groß: {url}")
    return body


FAILURE_FILE = "download_failed.json"


def inside_repository(path: Path) -> bool:
    """True when ``path`` lies in the repository (prices never go there)."""
    from .store import _repository_root

    return path.resolve().is_relative_to(_repository_root())


def download(
    folder: Path,
    *,
    get: Callable[[str], bytes] | None = None,
    now: float | None = None,
    urls: dict[str, str] | None = None,
) -> dict[str, dict[str, object]]:
    """The two official files in ``folder`` (never inside the repository): a copy younger than
    24 hours is kept, otherwise each file is requested once (one after the other; the first
    failure stops). A failed request is noted in the folder and no request is made for 24
    hours after it, so a refusal (403, 429) is never answered with a new request the same day.
    Returns per file whether it came from the cache or was downloaded."""
    if inside_repository(folder):
        raise DownloadFailed(f"der Download-Ordner darf nicht im Repository liegen: {folder}")
    fetch = get or http_get
    clock = time.time() if now is None else now
    folder.mkdir(parents=True, exist_ok=True)
    failure = folder / FAILURE_FILE
    if failure.is_file():
        try:
            noted = json.loads(failure.read_text(encoding="utf-8"))
            since = float(noted["at"])
            reason = str(noted["reason"])
        except (ValueError, KeyError, TypeError):
            since, reason = clock, "unlesbarer Vermerk"
        if clock - since < CACHE_SECONDS:
            hours = max(1, int((CACHE_SECONDS - (clock - since)) / 3600 + 0.999))
            raise DownloadFailed(
                f"letzter Abruf gescheitert ({reason}); kein neuer Abruf vor Ablauf von 24 "
                f"Stunden (noch etwa {hours} h). Ersatz: Dateien im Browser laden und --file nutzen"
            )
    report: dict[str, dict[str, object]] = {}
    for name, url in (urls or DOWNLOADS).items():
        if fetch is http_get and not url.startswith(DOWNLOAD_BASE):
            raise DownloadFailed(f"nur die Cardmarket-Downloads: {url}")
        target = folder / name
        if target.is_file() and clock - target.stat().st_mtime < CACHE_SECONDS:
            report[name] = {"from": "cache", "path": str(target)}
            continue
        try:
            body = fetch(url)
        except DownloadFailed as error:
            failure.write_text(json.dumps({"at": clock, "reason": str(error)}), encoding="utf-8")
            raise
        partial = target.with_suffix(".part")
        partial.write_bytes(body)
        partial.replace(target)
        report[name] = {"from": "download", "path": str(target), "bytes": len(body)}
    failure.unlink(missing_ok=True)
    return report
