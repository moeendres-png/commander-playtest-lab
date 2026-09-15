# WS222 CR_OFFICIAL_SOURCE

## Official entry point (independently fetched, not trusted from prompt)

- Landing page: `https://magic.wizards.com/en/rules` (HTTP 200, `text/html`,
  150428 bytes, SHA-256 `51aa2394…eba938`, retrieved 2026-09-15T04:00:48Z).
  The page's Comprehensive Rules section links exactly three official artifacts.
- Resolved TXT artifact: `https://media.wizards.com/2026/downloads/MagicCompRules%2020260819.txt`
  (file `MagicCompRules_20260819.txt`). DOCX/PDF remain `...20260807.docx/.pdf`.
- The prompt's expected TXT (`...20260807.txt`) is STALE: it now returns
  HTTP 404. Current official source truth wins; the drift is recorded here and
  in `CR_ACQUISITION_RECEIPT.json` (landing_txt_links). The TXT was republished
  2026-08-19 (Last-Modified `Wed, 19 Aug 2026 20:07:32 GMT`; landing content
  block updated `2026-08-19T20:11:54Z`) while the in-document effective date is
  unchanged: "These rules are effective as of August 7, 2026."

## Artifact identity (normalization NONE, hash over downloaded bytes)

- File: `artifacts/cr/MagicCompRules_20260819.txt`
- Size: 977822 bytes (Content-Length header agrees).
- SHA-256: `4381ad1b39ab2c05f7d03633a20f711ed37277074d3266dcba5f38cbb527423f`
- Content-Type: `text/plain`. ETag `"fb8bffb15798ecff075d383589c2f263:1787170217.794465"`.
- Encoding: UTF-8 with BOM (`EF BB BF` preserved in hashed bytes).
- Effective date (extracted from bytes, line 3): "These rules are effective as
  of August 7, 2026." 9397 lines; glossary + credits present; tail
  re-states the effective date.
- Corroborating family (not authority): official PDF `...20260807.pdf`
  (HTTP 200, `application/pdf`, 2524708 bytes, SHA-256 `9e2268a0ed58f229…`,
  Last-Modified 2026-07-30) proves the `20260807` family is real while the TXT
  moved to `20260819`. PDF bytes were NOT pinned as authority (TXT is the
  semantic/reference form per contract preference); no second authority.

## Provenance

Machine companion: `artifacts/cr/CR_ACQUISITION_RECEIPT.json` (landing URL,
final URLs, timestamps, headers, hashes, links, effective-date text).
Landing snapshot `artifacts/cr/landing.html` preserved for provenance.
Acquisition: `tooling/acquire_cr.py` (allowlist magic/media.wizards.com, no
credentials, redirect tracking, atomic writes, HTML-masquerade fail-closed,
effective-date check, idempotent `--verify-only`, offline from captured bytes).

Evidence class: DIRECTLY_VERIFIED (live official fetch + byte hash).
