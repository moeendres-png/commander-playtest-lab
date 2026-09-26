# WORK PROMPT — Post-audit Drive evidence and real-playtest intake

Use Google Drive and local file execution. The Phase-12.11 final audit is already complete. Do not repeat completed uploads unless an artifact fails verification. Do not alter any canonical deck list, inventory quantity, allocation or purchase record.

## Verified current state

- Project folder: `MTG – Aktueller Projektstand`
- Handoff folder: `MTG Commander Playtest Lab – Aktuelle Übergabe`
- Canonical `00_LATEST` folder ID: `1PV4WXGZyolwiylzK9F5w5VrJ2LmAv_vj`
- Final audit folder: `20_Final_System_Audit` (`1YTuihDCyRZBynKa1wQ9JXe_6DvdJDzyf`)
- Stable repository file ID: `1QrPVlbP4CNfvwtzl0dv6lVXmG5ayHSA5`
- Final-audit repository file ID: `1nK9kIeJic7A93wBUkG-Lam3KQH71fLkw`
- Final-audit bundle file ID: `1pchdkQACw7k_vCLXYUICWZSfhuyBwRKV`
- Final-audit source file ID: `1Xu-N9NUyeyaEqYNJYYytwqkZkmccTJy1`
- Final-audit wheel file ID: `1_EP9AJ976wFgKRlJiACzT-SwBKPBZ2TY`
- Final-audit validation file ID: `1PpXCuT0fM4uYCtP5Bt7ljWR_nGCOhiNd`
- Final result file ID: `1tOcLBbzfp4ughHYeo2pNAWQjkaFIOcq9`
- Current package version: `1.10.2`
- Verified repository HEAD: `9721332308dd058bf4aa92ad8be66a9733a5ccd7`
- Audited product-code commit: `f5a17fe6a8f8baf2f1793f782445f4da2a3e75d6`
- Existing round-trip status: `uploaded_and_redownload_verified`

## Open Work tasks

### 1. Real-playtest intake (`BLOCK-REAL-001`)

Only proceed after the user supplies real game logs.

1. Copy the supplied files into a new append-only dataset version under the project playtest-data area.
2. Validate CSV, XLSX or JSON input without filling missing values.
3. Reject synthetic fixtures as real observations.
4. Preserve deck version, game ID, correction lineage and train/validation split.
5. Run import validation and produce a dataset manifest and SHA-256 register.
6. Do not apply calibration parameters automatically.
7. Upload the dataset artifacts and reports to Drive, then re-download one artifact and compare SHA-256.

Acceptance gate: at least 20 valid training games and 8 separate validation games before calibration can be evaluated; `real_playtest_calibration_status` remains `not_run` below that threshold.

### 2. Evidence handoff from Codex

When Codex produces external-engine, QA, Parquet or optional MCP artifacts:

1. Verify the supplied repository commit, manifest and checksums.
2. Preserve the existing 1.10.2 final-audit artifacts historically.
3. Upload the new repository, bundle, source, wheel, validation and evidence files into a new dated subfolder.
4. Update `00_LATEST` only after tests and hashes are verified.
5. Re-download the repository ZIP or bundle and run `git fsck --full`, compile checks, targeted regressions, `commander-lab doctor`, database check and a one-game four-player structural smoke.
6. Record actual Drive IDs, sizes and hashes.

## Acceptance and prohibitions

- Use only real Drive IDs observed from completed writes/readback.
- A result is `uploaded_and_redownload_verified` only after a genuine Drive re-download and matching SHA-256.
- No canonical MTG deck, inventory, allocation or purchase data may change.
- No synthetic game may count as real.
- No Tactical Oracle or mock may be labeled `external_rules_engine`.
