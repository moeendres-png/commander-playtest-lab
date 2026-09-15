# WS226 G_AF_CURRENT_VIEW — XMage current G/AF dispositions (generated)

Source: `XMAGE_STANDING.json` (deterministic view, digest `5bc1a02d…`).
Machine companion: `G_AF_CURRENT_VIEW.json` (verdicts + truncated reasons).

- G01 PASS (scoped v2) · G02 PASS · G07 PASS · G09 PASS · G10 UNKNOWN (16 preserved) ·
  G11 PASS · G13 FAIL (computed) · G00 PASS · G14/G15 NOT_APPLICABLE ·
  G12 UNKNOWN · G03–G06/G08 per fixture rollup (see trace; no new runtime).
- AF01 UNKNOWN · AF02 PASS · AF05 PASS · AF07 PASS · AF08 UNKNOWN (blocked) ·
  AF09 PASS (WS218 tape) · AF10 PASS · AF11 UNKNOWN · AF00/AF03/AF04/AF06 per trace.
- Admission FAIL; freeze_eligible false.

S5-cardinality (WS220 successor: 2–5P CI) ≠ S5-admission (WS225 stage: expensive
135-fixture campaign). Generator's `ADMISSION_STAGE_CONTRACT` decides: XMage
S0–S4 PASS, S5 FAIL (campaign not run) → `DO_NOT_PROMOTE_CURRENT_PIN` (S5-pending,
no privilege). Forge S1-terminal, Quorune/Argentum S3-terminal preserved.

FULL107: `HISTORICAL_REGRESSION_ARTIFACT` (NOT_RUN preserved; no normative role;
no deletion; not an admission gate).
