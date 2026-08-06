# WORK PROMPT — Final audit Drive round-trip and real-data intake

Use Google Drive and local file execution. Do not alter any canonical deck list, inventory quantity, allocation or purchase record.

## Ground truth

- Project folder: `MTG – Aktueller Projektstand`
- Handoff folder: `MTG Commander Playtest Lab – Aktuelle Übergabe`
- Canonical `00_LATEST` folder ID: `1PV4WXGZyolwiylzK9F5w5VrJ2LmAv_vj`
- Prior repository file ID: `1QrPVlbP4CNfvwtzl0dv6lVXmG5ayHSA5`
- Prior bundle file ID: `1MTlpDgxNyefGpL37KGTFzvmBdwMOgr3O`
- Prior source ZIP file ID: `19oNfI7Z6UecpXZ0eI6-aXKwPXClr7b92`
- Prior wheel file ID: `1H8BjtKxZ8SD_Fbcj_oPmegK2RAAoFHvL`
- Prior validation ZIP file ID: `1_tM5-j9vA6tqUeAm_fyNYlG4Ue9fuI59`
- Audit package version: `1.10.2`
- Audited code commit: `f5a17fe` and descendants in the final repository artifact
- Start commit: `6459581cc3e886d412d8e3c1bf3c1f7dfe0f3009`

## Tasks

1. Create or locate `20_Final_System_Audit` under the canonical handoff folder.
2. Upload the supplied final-audit repository ZIP, Git bundle, source ZIP, wheel, validation ZIP and all `FINAL_*` / repair-routing files with raw bytes preserved.
3. Do not overwrite `00_LATEST` binaries until the previous versions are copied to a historical folder.
4. Update `00_LATEST` status, manifest, SHA-256 register, changelog, function matrix, blocker register and bug register using the uploaded files.
5. Re-download the final repository ZIP or bundle from Drive.
6. Compare SHA-256, verify ZIP/bundle integrity, restore to a fresh directory and run:
   - `git fsck --full`
   - `python -m compileall -q src tests`
   - targeted core tests
   - `commander-lab doctor`
   - one four-player structural smoke run
7. Record Drive file IDs, sizes, hashes and `uploaded_and_redownload_verified` status.
8. When real playtest files are later provided, import them into a new dataset version. Never count synthetic fixtures as real data and never auto-apply calibration.

## Acceptance

- All uploaded byte hashes match local `FINAL_SHA256SUMS.txt`.
- Fresh restore HEAD contains audited code commit `f5a17fe` and the final audit documentation commit.
- Package imports as 1.10.2; 92 unique tools are present.
- Core tests and structural smoke pass.
- No canonical MTG data changed.
