# WSR25 Terminal Closure

Terminal record for the XMage/Mage residual closure and delegated-authority campaign.
Scope: XMage residual evidence closure, Git/GitHub delegation, project and repository
hygiene. Everything below is merged on `main`. No open workstream item remains.

`ARCHITECTURE_FREEZE = NOT CLAIMED`. `PRODUCTION_PROVIDER = NOT SELECTED`.

## Source Lock

- Final `main` audit base: `c771e3535125432ee0f25aed6496db33f0b44f33`
  (tree `7ac8ed892cae3162a861c6a03fa610ad5332229b`). This file is delivered in the merge
  commit of its own pull request, so read it from the newest `main`, not from the audit base.
- Canonical XMage pin: `b19596980f2734496ea1896504253e1bdd2756dd` (`config/rules_engines.json`).
- Bridge: `xmage-engine-bridge 0.1.0-SNAPSHOT`, xmage `1.4.61`, Lab protocol `2.0.0`.

## Delivered

| Objective | Result | Merge commit |
| --- | --- | --- |
| RG-07 exact-N target offering, current-pin Lab evidence | PASS 6/6 | `425a9af2` (#270) |
| RG-08 replacement timing, current-pin Lab evidence | PASS 8/8 | `425a9af2` (#270) |
| Camp-carrier transplant manifest and rejected-residue preservation | merged | `425a9af2`, `4a3abd34` (#273) |
| Delegated owned-branch Git authority (repo policy + machine-verified battery) | ENABLED | `f5941985` (#272) |
| Foundry workspace access | merged by the owning lane | `b786fbf2` (#266) |
| Global user OpenCode config (99 git/gh rules, backed up) | ENABLED | n/a (user config) |
| Repository hygiene: description, topics, label taxonomy, branch policy, issue receipts | done | `c771e353` (#276) |
| Repository triage index | merged | `c771e353` (#276) |

## Evidence retained

- `docs/workstream_wsr25_rg07_rg08_port_20260927/` — handoff, transplant manifest,
  deferred successor notes, and the forensic patch of the seven rejected Mage edits.
- `docs/REPOSITORY_TRIAGE_INDEX.md` — PR lanes, label semantics, issue states.
- `docs/RETENTION_AND_LIFECYCLE_POLICY.md` — pin lineage `77d7646 → cfc36f44 → db134b97 → b1959698`.

## Explicitly not done (other owners)

- PB-03 starting-state injection and the WSR22 successor integration (Space Bunny MAX).
- **PB-09 — `EVIDENCE_INTEGRITY_DEFECT`, owner Forge lane + Coordinator, and its decision is
  ordered *before* PB-03.** Forge's Rules-Core pin is satisfied, its Lab bridge-source pin is
  not: the Forge column measured a Lab Rules-Core fork rather than the pinned candidate. This
  is the mechanical cause of the apparent Forge capability lead, and the reason its PASS
  asymmetry is not a measured Rules difference. Source:
  `docs/pre_freeze_completion_20260927/PRE_FREEZE_COMPARISON_PACKAGE.md` §7.1 and the blocker
  table (`PROVIDER_COMPARISON_COMPLETE = NO`, `PROVIDER_SELECTION_READY = NO`).
- **PB-06 / PB-07 / PB-08 are `both`-sided blockers, not Forge-only.** Per the same package:
  PB-06 per-scenario hidden channels, PB-07 the effective 29-card corpus, PB-08 the
  per-fixture clean-process replay twin are `UNKNOWN_IMPACT` and still open for **both**
  candidates. Ownership is therefore split per side, not assigned to one lane: the Forge
  seams with the XMage-side seams (hidden-channel projection, 29-card corpus execution,
  replay/RNG twin rows) as parallel obligations, so a successor must not close either half
  on the strength of the other.
- Provider selection and Architecture Freeze (Coordinator only).
- 33 provenance pull requests kept open on purpose; no branch or repository deletion.
- WS-48 stash, duplicate Forge clone, Mage pull requests #13–#16, restored-morph guard
  relaxation: preserved untouched per Coordinator instruction.

## Known residual gaps after closure

- PB-03 harness fixture-prefix defect, plus eleven rows whose `BLOCKED` status is a
  **modeled projection** from the bridge dimension manifest (not an executed result):
  `MICRO_STACK`, `MICRO_TRIGGERS`, `MICRO_REPLACEMENT`, `MICRO_PREVENTION`, `MICRO_COPY`,
  `MICRO_MODES`, `MICRO_CONTINUOUS_EFFECTS`, `MICRO_STATE_BASED_ACTIONS`, `MICRO_CONTROL`,
  `MICRO_COMBAT`, `MICRO_RULES_RANDOMNESS`. They stay blocked while `stack spells`,
  `attachments and counters`, `controller/owner divergence` and `temporal points outside
  the qualified turn-1 allow-list` remain unsupported, and must still be executed to
  learn their real outcome. The corresponding ~22-row admission is likewise a projection.
- `ACTIVATED_ABILITY_PRESENT` guard is intentionally conservative after the RG-06B
  falsification; relaxation is a post-selection Lab re-pin decision.
- B4-D action submission for 18 decision classes (WS-204 line).
- Issues #192, #193, #204, #205 remain open with recorded evidence.

## Resume point for any successor

Nothing is mid-flight. This record itself lands in the merge commit of its own pull request,
so `c771e353` is the **audit base**, not the revision that contains this file. Start from the
newest `main` (`git pull --ff-only`), read this file from there, read
`docs/REPOSITORY_TRIAGE_INDEX.md` for the backlog rules, and treat
`config/rules_engines.json` as the only pin authority.
