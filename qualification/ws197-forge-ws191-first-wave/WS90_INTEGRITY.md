# WS197 WS90 Authority Integrity

Sealed package consumed WITHOUT mutation: `qualification/ws90-rqc3-corrected-first-wave-reissue/` (12 files).

## Pre-promotion (audit base 7725570b, clean tree)

`python3 qualification/ws90-rqc3-corrected-first-wave-reissue/verify.py` → `VALIDATION_PASS` (all gates green, zero behavior credit, no execution). Denominator exactly 15 (`A03 A04 B01 C01 C03 D06 E01 E02 F01 G02 G03 G04 H01 I01 J02`); 14 non-H01 byte-equivalent + fingerprint match (`NON_H01_SEMANTIC_DRIFT 0`); H01 single slot with A/B/C contrast family (`HUMILITY_FIRST` false/false/null + 0/0 SBA `704.5f` + NOT 2/2 Bear; `CLONE_FIRST`/`NO_HUMILITY` offered+taken Bear; `614.12` cited; old COPY_CHOICE absent; 1/1-alone-insufficient stated); decision union 20 kinds mechanically derived (`copy choices` sole carrier H01 via B/C; H01-A MUST-NOT-OCCUR); XMage pin `cfc36f`; provider false/null/`NO_PROVIDER_READY`; 5 WS60 deltas `STILL_REQUIRED`; 13 harness files classified, no `UNSAFE_SECOND_RULES_LOGIC`; 10 pilot behaviors absent; deterministic JSON rebuild PASS.

Classification: `WS90_AUTHORITY_INPUT_INTEGRITY = PASS (DIRECTLY_VERIFIED)`.

## Post-promotion (Phase A tree, authorized repin)

Same validator → semantic gates all PASS; exactly 2 FAILs, both the worktree-touched gate on the AUTHORIZED promotion edit:

- `FAIL historical untouched config/rules_engines.json :: touched config/rules_engines.json`
- `FAIL historical files untouched (no forbidden touch)`

Only `config/rules_engines.json` is actually forbidden-touched (the authorized dual-identity repin); the other listed paths are the validator's touched-sample display. No `qualification/ws90-*` file was modified (package bytes intact; 14 non-H01 fingerprints still match; H01 binding still enforced).

This is NOT an authority integrity failure: the gate proves WS90 did not smuggle production edits; WS197 is a separate authorized promotion workstream whose manifest edit is its contracted purpose. Semantic authority stands; behavior credit remains 0; `FORGE_RQC3_FIRST_WAVE` moves from `NOT_RUN` to freshly evidenced `0 PASS / 0 FAIL / 15 BLOCKED / 0 UNKNOWN` (see `FIRST_WAVE_MATRIX.json`).

Never altered authority to fit candidate behavior. `FULL107 = NOT_RUN`.
