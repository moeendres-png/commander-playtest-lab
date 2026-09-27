# WSR22 impact adjudication and successor-integration specification

Date: 2026-09-27
Evidence head (immutable): `208341c6124674046787f3a4b1d699c98c286a27`
Branch: `wsr22/final-current-boundary-freeze-qualification-20260927`
Classification: `CODE_DERIVED` from current source + `DIRECTLY_VERIFIED` for the Rules-authority capture

---

## 1. Why PR #269 is not integration-ready

It is not blocked by a textual conflict alone. There are exactly **five** paths where the WSR22
branch and `origin/main` hold different blobs. Four of them are the conflicting paths named by the
Coordinator; the fifth is a trivial additive ignore rule. Verified by comparing blob ids for every
path in `git diff --name-only origin/main...origin/wsr22/...` that also exists on main.

| # | Path | Conflict class | Why |
|---|---|---|---|
| 1 | `qualification/pre-freeze-successor/CURRENT_RULES_AUTHORITY.json` | **semantic, Rules authority** | main (`d24432c3`) writes a 1.2.0 receipt that *rejects* 2026-09-25; WSR22 (`dfb490e2`) writes a byte-exact 2026-09-25 capture that *adopts* it |
| 2 | `tests/qualification/test_pre_freeze_contract_successor.py` | **derived** | assertions track whichever receipt is current |
| 3 | `qualification/SHA256SUMS` | **generated manifest** | seals the receipt and other contract blobs |
| 4 | `WS17_SHA256SUMS` | **generated manifest** | seals the root qualification surface |
| 5 | `.gitignore` | **textual, additive** | WSR22 adds `engine-bridge/db/` and `engine-bridge/target/cp-wsr22.txt` as runtime build output |

The conflict is a genuine **fork in Rules-authority adjudication**, not a merge accident: both sides
edited the same file from the same ancestor (`ea0533d2`, PR #254) in opposite directions. That is
precisely the case the Coordinator's rule addresses — do not repair it by mutating the evidence
history, cut a successor from fresh main instead.

## 2. The one real semantic conflict, and its resolution

main's receipt asserts:

```
"current_official_source": { "rules_page_txt_link_url": ".../MagicCompRules%2020260807.txt",
                             "effective_date": "2026-08-07" }
"freshness_adjudication": { "prior_claimed_newer_effective_date": "2026-09-25",
                            "disposition": "REJECTED_BY_HIGHER_AUTHORITY_CURRENT_OFFICIAL_RULES_PAGE",
                            "reason": "...the current official Wizards Rules page directly links the 20260807 TXT...",
                            "admission_credit_from_prior_signal": false }
"byte_exact_sha256": null,
"byte_exact_status": "NOT_CAPTURED_IN_THIS_COORDINATOR_SURFACE"
```

WSR22's capture asserts a direct official page fetch listing `MagicCompRules 20260925.{docx,pdf,txt}`,
a byte-exact TXT (977752 bytes, sha256 `8d860e45…`), rule 103.8a verbatim, and that the previously
recorded 20260807 TXT URL now returns HTTP 404.

**Resolution, per the binding Coordinator adjudication:** adopt 2026-09-25; main's receipt is
`STALE_RECEIPT`; `RULES_AUTHORITY_CONTRADICTION = RESOLVED`; no Rules-semantic regression; no
blanket FULL107 rerun.

**This session independently re-verified that adjudication rather than inheriting it.** Fetching the
live official TXT returns a document whose first line states the September 25, 2026 effective date
and whose rule 103.8a is character-identical to the WSR22-recorded text. Two further facts make the
resolution convergent rather than a bare override:

- main's own receipt concedes the 2026-09-25 signal existed; it rejected it on a *mechanism* claim
  (the page links 20260807) that the direct capture falsifies.
- WSR22 self-validated its capture pipeline: re-capturing the 2026-08-19 TXT reproduced the
  repository's own historical hash `4381ad1b…` exactly, so the pipeline is not merely plausible.

The Coordinator holds Rules authority under AGENTS.md §6/§8, and the adjudication is a *newest
direct user statement* under §3. It is therefore binding, and it is also the reading best supported
by the byte-exact evidence. `CURRENT_RULES_AUTHORITY = 2026-09-25`,
`FULL107_RUNTIME_EVIDENCE_INVALIDATED = NO`, `FULL107_BLANKET_RERUN_REQUIRED = NO`.

## 3. Disjointness check against the WSR23 mutation surface

`tools/foundry/**` and `tests/foundry/**` appear nowhere in the WSR22 diff, so the Phase A tooling
repair (`worktree_inventory.py`, `tests/foundry/test_foundry_tools.py`, `tests/foundry/test_launcher.py`)
cannot conflict with the WSR22 successor integration. Verified by listing all 46 WSR22-changed paths.

## 4. Evidence-family impact adjudication

Accepted per the Coordinator, re-derived against current source, no contradicting drift found.

| Family | Class | Basis |
|---|---|---|
| FULL107 107+107 runtime results | `UNAFFECTED_REUSABLE` (XMage); Forge half `REQUIRES_RECONCILIATION` | no contract/denominator/protocol/pin change; but see PB-09 |
| START-2 v1.0.6 | `UNAFFECTED_REUSABLE` | effective contract blob unchanged |
| AF00–AF11 | `UNAFFECTED_REUSABLE`, except Forge AF00 → `REQUIRES_RECONCILIATION` | receipt change does not alter a gate's obligation; AF00 Forge is a separate source-lock defect |
| Protocol-2 lifecycle | `UNAFFECTED_REUSABLE` | protocol schema blob `741e0acc…` unchanged |
| XMage native runtime (168 tests) | `UNAFFECTED_REUSABLE` | XMage pin `b1959698…` matches main |
| Forge native runtime (217 tests) | `UNAFFECTED_REUSABLE` | unaffected by a Lab receipt change |
| comparison classifications | `UNAFFECTED_REUSABLE` | derived from the rows above |
| hidden information | `UNAFFECTED_REUSABLE` | no change to redaction or observation surfaces |
| replay / RNG | `UNAFFECTED_REUSABLE` | seed binding untouched |
| Rules authority | `MECHANICAL_REQUALIFICATION` | receipt + its two manifests + its assertions |
| integrity manifests / seals | `MECHANICAL_REQUALIFICATION` | regenerate from the integrated tree |
| successor-inheritance proof | `UNAFFECTED_REUSABLE` | v1.0.6 ⊇ v1.0.5 record equality is a content fact |
| PB blocker register | `UNAFFECTED_REUSABLE`, **extended by PB-09** | PB-05's reason text is refuted; PB-03's cause is corrected |
| provider/adapter/build source locks | mixed — see §1 of `CAMPAIGN_STATE.md` | Forge executed commit ≠ pinned commit |

**No blanket runtime rerun.** The changed files are a receipt, two generated manifests, and one
assertion module. Changed files alone never invalidate runtime evidence, and here the rule-level
diff over the whole qualification-relevant set is `semantic_delta: NONE`.

## 5. Successor-integration specification

To be executed in a launcher-authorized session. Ordered so that no step depends on an unproven
assumption.

1. Cut `wsr22-successor/current-boundary-20260927` from **`origin/main` `8d2aacd5`** — never from
   stale local `main` `586914ea`.
2. Record the base as `audit_base_sha`/`audit_base_tree` in the successor state. Note that WSR22's own
   `SOURCE_LOCK.json` names its fields `head`/`tree` and points them at `c5f9418e` / `610f93d8` —
   which is the *base* identity, not the evidence head (whose tree is `d8f6c80a`). The successor
   should use the unambiguous `audit_base_*` names so no reader can mistake base for executed head.
3. Transplant from `208341c6…` only: the `qualification/final-current-boundary-20260927/` evidence
   directory, `src/commander_lab/qualification/current_boundary/`, the two runner scripts, and
   `tests/qualification/test_wsr22_current_boundary.py`. Take them **as whole files from the evidence
   head**; do not hand-merge them against main.
4. Write `qualification/pre-freeze-successor/CURRENT_RULES_AUTHORITY.json` fresh, carrying the
   2026-09-25 capture and preserving main's receipt content as superseded history rather than
   deleting it.
5. Update `tests/qualification/test_pre_freeze_contract_successor.py` to assert the 2026-09-25
   receipt. Do not weaken an assertion to make it pass; the assertion's *subject* legitimately changed.
6. **Regenerate** `qualification/SHA256SUMS` and `WS17_SHA256SUMS` from the final integrated tree.
   Never transplant a manifest — a transplanted manifest would seal the wrong tree.
7. Run only: the successor test module, the pre-freeze contract test module, the integrity/manifest
   checks, and the directly impacted meta checks.
8. Push, open the PR against `main`, inspect exact-head CI, fix only failures attributable to the
   integration, and merge when the campaign gates pass.
9. Re-read post-merge `main` HEAD/TREE; do not assume them.
10. Mark PR #269 superseded **only after** step 1–9 prove that every WSR22 evidence family above is
    present on main with the successor's provenance intact.

## 6. One thing the successor must not do

Do **not** "fix" the Forge source lock by editing `ef958ee9…` into `a37a865a…` anywhere. The executed
commit is a historical fact and stays recorded as such. The correct remedy is to re-run the Forge
evidence at the pinned commit (or to prove which commit the executed artifact corresponds to), and to
record the outcome honestly. Editing a provenance field to match a pin is precisely the kind of
evidence falsification this project forbids.
