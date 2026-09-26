# Collection snapshots

`current_deck_allocations.json` is a legacy/read-only physical-inventory allocation snapshot generated from the canonical inventory state on 2026-08-07. It is retained for regression and allocation-validation context and is **not** the authoritative source for the current active-own-deck scope.

Current active-own-deck truth is defined under `data/collections/current/`, especially `ACTIVE_OWN_DECKS_CURRENT.json`. As of the current project state, `rogshai/current` is the sole active own deck; `korvold/current` is an inactive former own deck and does not reserve cards for simultaneous own-deck construction.

This repository snapshot does not replace the canonical physical inventory workbook in Google Drive. Printing metadata such as set, collector number, language, condition, and foil status is inventory/provenance data; it does not change the Oracle identity or simulated rules behavior of the same card.
