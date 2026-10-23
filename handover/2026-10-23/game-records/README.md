# Game records (measurement lane, Muse) — 2026-10-23

Everything the measurement lane produced that can travel this channel, so the
pilot/efficiency work can use real game traces. All records are
`LOCAL_OBSERVED` measurement output (XMage is the only rules engine; these are
its transcripts).

## Contents

- `manifest.json` — every stored file with the sha256 of its ORIGINAL bytes
  and the list of stored parts. Files larger than ~110 KB are gzip-compressed,
  base64-encoded (the push channel accepts text only) and split into
  `.gz.b64.partNNN` chunks; `reassemble.py` rebuilds and verifies them.
- `m3-replay/` — the full M3 determinism-census replay logs (12 files,
  seeds 24/27/30 divergent pods; lab `84e245ac`, pin v11). Previously kept
  local-only by an owner decision of 2026-10-22; published now on the owner's
  instruction of 2026-10-23.
- `m4/` — the complete M4 working record except raw game bodies: all
  comparison/slice/retry/baseline REPORT JSONs, supervisor and run logs, the
  helper scripts used (`analyze_*`, `build_*`), prefilter outputs on both
  locks, readiness scan. Locks: lab `d48bbe5f2`, pin v11 bridge JAR sha256
  `69aa31ebf15dc47c29234a711026c2caa3eb8d29efe5921a63991c22e8cd34e8`.
  The final evaluation lives in `handover/2026-10-22/deck-improvement/`.
- `m4/games_manifest.json` — all **2,033 unique game transcripts** of M4
  (7,700,488,178 bytes raw) with per-file sha256.
- `m4/transcript-sample/` — six full transcripts (two baseline games per
  deck + one twin-check game per deck), packed like the rest.

## Not in this folder

The 2,033 full M4 transcripts (~7.7 GB raw, ~400 MB gzipped) exceed what the
API push channel can carry sensibly (text-only, 128 KB per file). They stay in
the local archive (`~/workspace/tmp/m4/**/games/`, file name = run content
hash) and are fully indexed by `m4/games_manifest.json`. Sensible routes for
the full corpus: a direct `git push` from the owner's machine, or a GitHub
Release asset (<= 2 GB) built from the local archive.

Excluded on purpose: `collection_counts.json` (the owner's collection
contents) — the bundle availability result derived from it is in the M4
final report, the raw counts are not published.
