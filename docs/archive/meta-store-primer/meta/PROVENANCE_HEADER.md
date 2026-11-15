# Meta Snapshot Provenance Header (PR1)

Status: schema extension, Meta-Lane PR1. The snapshot format is unchanged in
its existing fields and keeps `schema_version: 1.0.0`: every field below is
optional and additive, so snapshots written before PR1 still validate.
Enforcement of caps (PR4), stale handling (PR6), snapshots (PR2/PR3),
spellbook wiring (PR5) and any `external_prior` (PR7) are explicitly NOT
part of PR1. Nothing in this document changes scoring: the scoring code
reads `format_band`, commander and decklist only, and none of the fields
below is read there.

## Per-source fields (`sources[]`)

| Field | Status | Rule |
|---|---|---|
| `source_id`, `title`, `url`, `author` | existing | As before. `url` may be null when a source has no stable page. |
| `retrieved_at`, `published_at` | existing | Retrieval date is mandatory; publication date may be null. |
| `source_type`, `categories`, `evidence_quality` | existing | As before. `categories` must not be empty. |
| `license_notes` | existing | Reference metadata and short structured extraction only. Never copy long primer text. |
| `tier` | PR1, optional | `A` (tracked/aggregated primary data with stated sample and date), `B` (established guide: primer/strategy article with decklist and reasoning), `C` (single opinion without a data basis). Tier C is never a strength claim and never enters scoring (PR4 enforces the caps). |
| `band` | PR1, optional | Exactly one band from the existing category set, and it must be one of the entry's `categories`. Set it only when the source has exactly one applicable band; otherwise leave it null. Bands are never mixed: cEDH data never feeds `high_power`, `normal_four_player` or `local_meta` recommendations. |
| `sample_size`, `small_sample` | PR1, optional (frequencies already had them) | `sample_size` is the stated n (integer, at least 1). When `sample_size` is given and `small_sample` is omitted, it is derived as `sample_size < 5`. When both are given they must agree; a contradiction is a validation error, not a warning. |
| `expires_at` | PR1, optional | Stale boundary, computed as `retrieved_at` + 12 calendar months (see `expires_at_for` in `src/commander_lab/models/meta.py`). PR1 defines the field and the computation only; treating expired records as weight 0 belongs to PR6. |

## Per-deck-snapshot fields (`deck_snapshots[]`)

| Field | Status | Rule |
|---|---|---|
| `format_band`, `categories`, `retrieved_at`, `license_notes` | existing | As before. |
| `band` | PR1, optional | The single-band view of the snapshot. When set it must equal `format_band`. |
| `target_deck_ref` | PR1, optional | Reference to a handover target deck as `{path, commit, branch?}`. It is a reference only: never copy the target decklist into a snapshot. Populating it for RogShai/Chulane belongs to PR2/PR3. |

## Per-package fields (`packages[]`)

| Field | Status | Rule |
|---|---|---|
| `vetoed_by_games` | PR1, optional (default `false`) | True only when paired games overruled this package. The contradiction itself is documented in the PR/artifact, never silently overwritten. A card-level prior veto belongs to the profile prior fields and is deliberately not modeled here. |

## Per-frequency fields (`card_frequencies[]`)

`commander`, `format_band`, `sample_size`, `small_sample` already exist and
are unchanged. No new field is added here.

## Templates (placeholders only, no real decklists)

Source entry with PR1 fields:

```json
{
  "source_id": "example-source-2026",
  "title": "Example aggregator page",
  "url": "https://example.test/source",
  "author": "Example",
  "retrieved_at": "2026-10-25T00:00:00+00:00",
  "published_at": null,
  "source_type": "aggregator",
  "categories": ["high_power"],
  "evidence_quality": "aggregator",
  "license_notes": "reference metadata and short structured extraction only",
  "tier": "A",
  "band": "high_power",
  "sample_size": 53,
  "small_sample": false,
  "expires_at": "2027-10-25T00:00:00+00:00"
}
```

Deck snapshot excerpt with PR1 fields:

```json
{
  "format_band": "high_power",
  "band": "high_power",
  "target_deck_ref": {
    "path": "handover/2026-10-22/example-deck/",
    "commit": "0123456789abcdef0123456789abcdef01234567",
    "branch": "muse/claude-handover"
  }
}
```

Package entry with PR1 field:

```json
{
  "package_id": "example-package",
  "name": "Example package",
  "cards": [],
  "roles": [],
  "categories": ["high_power"],
  "vetoed_by_games": false
}
```

## Standing rules for future snapshots

- Popularity is not strength. A frequency is a popularity signal (budget,
  availability and meme effects included), never a win-rate claim.
- Gaps stay gaps. A missing band, primer or tournament presence is reported
  as a finding, never stuffed with data from another band or commander.
- Freshness is dated. Every source carries `retrieved_at`; anything older
  than 12 months is stale once PR6 enforces it. Until then, stale records
  stay readable but must be labeled as such in any new artifact.
- Validation lives in `src/commander_lab/models/meta.py` (models
  `MetaSource`, `MetaDeckSnapshot`, `MetaPackage`, `MetaTargetDeckRef`,
  `MetaTier`, helper `expires_at_for`) and is covered by
  `tests/unit/test_meta_snapshot_schema_pr1.py`.
