# Meta refresh interval (Meta-Lane PR6)

External meta data is valid for **12 months from `retrieved_at`**
(PR1: `expires_at_for`). After that boundary a source contributes
nothing to scoring:

- References backed by a stale source are excluded when a functional
  meta profile is built; when every matching reference is stale there
  is no profile (not a stale one).
- A package file whose every source is stale contributes no packages
  to the search attach step.
- Combo lines carry no per-line dates; the combos file is reported
  on its `provenance.retrieved_at` only and never enforced in scoring.

Stale data stays readable. Expiry removes weight, not history: the
report script lists stale sources so a refresh can be planned.

## Checking freshness

```sh
PYTHONPATH=src python scripts/refresh_meta.py --as-of 2027-09-01
PYTHONPATH=src python scripts/refresh_meta.py --as-of 2027-09-01 --json
PYTHONPATH=src python scripts/refresh_meta.py --fail-on-stale  # exit 2 if stale
```

Exit codes: 0 normally, 2 with `--fail-on-stale` when anything is
stale at `--as-of`, 1 when a file cannot be read or validated.

## Refreshing

A refresh is a **new snapshot**, never an edit of an existing file:
the PR1 store refuses to overwrite a snapshot, so a refreshed file
gets a new `snapshot_id` (and `supersedes` the old one). Refreshing
is a data change, not a code change, and it does not happen
automatically: the script reports only. There is no EDHREC API call
and no scraping in this repository.

Current boundaries (retrieved + 12 months): the 2026-10-25 refresh
snapshots and package files expire 2027-10-25; the 2026-08-05
snapshot expires 2027-08-05 and the 2026-08-13 search snapshot's
sources expire 2027-08-05 (part) and 2027-08-13 (part). The search
snapshot's references therefore drop out progressively during
August 2027 unless refreshed before then.
