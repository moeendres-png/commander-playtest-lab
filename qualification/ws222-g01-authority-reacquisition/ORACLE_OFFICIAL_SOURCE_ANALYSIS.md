# WS222 ORACLE_OFFICIAL_SOURCE_ANALYSIS

## What Wizards officially exposes today (bounded investigation, 2026-09-15)

1. **Gatherer 2.0 is the official card database.** `https://gatherer.wizards.com/`
   footer: "Gatherer provides the official and most up-to-date card text and
   rulings directly from Wizards of the Coast." A June 2025 Wizards announcement
   ("A Fresh Look for Gatherer") confirms Gatherer as the searchable Oracle
   reference. The magic.wizards.com Formats pages link Card Database to
   Gatherer. Classification: official authority for Oracle text + rulings.
2. **URL structure.** Canonical per-card pages are
   `/{SET}/en-us/{NUMBER}/{slug}` (e.g. `/NEO/en-us/177/boseiju-reaches-skyward`).
   Old Gatherer 1.x URLs (`/Pages/Card/Details.aspx?multiverseid=N`) 302-redirect
   to canonical 2.0 URLs (verified for Sol Ring, Boseiju, Wear // Tear,
   Find // Finality). 1.x search-by-name (`?name=`) still resolves singletons
   (Sol Ring, Boseiju) but fails on `//` names (Wear // Tear falls back to
   homepage) — hence the bridge+redirect method below.
3. **Structured official data, no public bulk artifact/API.** Each card page
   embeds a full structured record: `resourceId` (stable per-printing identity),
   `multiverseId`, `oracleName`/`instanceName` (Oracle vs printed),
   `oracleText`/`instanceText`, `oracleManaText`, `oracleTypeLine`,
   power/toughness, `formatLegalities` (incl. Commander), `rulings[]`
   (date + statement), `relatedCardInstances`, `compositeCard` (MDFC back-face
   linkage). There is NO official versioned bulk download and NO documented
   public JSON API (page-embedded flight data only; search is client-side).
   The published `sitemap_index.xml` (per-set sitemaps, lastmod 2026-09-01)
   enumerates card URLs but each page must still be fetched individually
   (~30k+ pages for full bulk — aggressive, out of scope, not performed).
   Model A (official bulk) is therefore UNAVAILABLE: proven by absence of any
   bulk link on Gatherer/landing pages + per-card-only mechanism + sitemap
   economics. This is an official-infrastructure limitation, not a network
   failure.
4. **Robots/terms posture.** `robots.txt`: `Allow: /` (only `/random-card`
   disallowed) + sitemap. Per-card capture with ~1s delays and a project
   User-Agent (29+1 pages total) is bounded, non-aggressive use of the
   published mechanism. No credentials used. No crawler built.
5. **Resolution method (Model B).** Scryfall `cards/named` supplies ONLY a
   pointer (`related_uris.gatherer` multiverseid URL; if the default printing
   lacks one, the first older printing with one via `prints_search_uri`,
   deterministic in returned order). The official 1.x URL's redirect resolves
   the canonical 2.0 URL; authority bytes are always Gatherer's. Bridge role is
   recorded per record as `discovery_pointer_only_never_authority` (one Veyran
   record notes `bridge_fallback_to_older_printing: true`).

## Reproducibility semantics (honest, proven)

- Gatherer pages are dynamic shells (rotating nonces/promos): live re-fetch of
  the same canonical URL yields DIFFERENT bytes (Ishai: 193253 vs 193427 bytes,
  SHA differs). Byte equality across live fetches is NOT claimed.
- Official FIELDS are deterministic: re-fetch field snapshot comparison is
  ALL-SAME (names, resourceId, multiverseId, set, number, oracle texts, mana,
  type lines, Commander legality, rulings). Reproducibility = pinned bytes as
  provenance + field-level determinism + drift procedure (re-fetch, compare
  snapshot; byte change alone is not authority change; field change triggers
  impact review). Offline verification (`--verify-only`) re-hashes captured
  bytes and re-extracts markers.

Evidence class: DIRECTLY_VERIFIED (live official fetches + redirect chains +
repeat probe). Model evaluation: A unavailable; B satisfied for the required
domain; C available for broader transport if needed (authority/transport
separation); D Coordinator-only (documented, not requested for G01 minimum).
