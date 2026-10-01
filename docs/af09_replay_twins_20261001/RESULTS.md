# AF09 replay-twin results (2026-10-01)

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`

Evidence documents:

- `evidence/AF09_REPLAY_TWIN_XMAGE.json` and `…_XMAGE_{2,3,5}P.json`
- `evidence/AF09_REPLAY_TWIN_FORGE.json` and `…_FORGE_{2,3,5}P.json`

All were produced from a clean worktree at Lab `299b1e8a` (tree recorded
inside each document) with `lab_source.clean = true`. Heavy engine execution
was serialized per candidate and used isolated runtime directories outside
every foreign worktree.

## Cardinality matrix (all four required counts)

| Count | Forge | XMage |
|---|---|---|
| 2P | PASS (120 decisions/events, 240 checkpoints) | UNKNOWN — fresh consumer `CHOSEN_OPTION_AMBIGUOUS` at step 110 |
| 3P | PASS (121 / 121 / 242) | PASS (123 / 123 / 124; 123 steps re-derived) |
| 4P | PASS (122 / 122 / 244) | PASS (127 / 127 / 128; 127 steps re-derived) |
| 5P | PASS (123 / 123 / 246) | PASS (126 / 126 / 127; 126 steps re-derived) |

Every PASS row has zero semantic divergences, a complete `GAME_OVER`
terminal, observed pairwise-distinct process identities, an acknowledged
requested seed, and every adversarial control detected.

**2P XMage blocker (exact).** At step 110 the recorded choice is the mana
ability of a `Plains`; the fresh process offers two native options carrying the
same semantic fingerprint, so the qualified WS218 resolution refuses the
first-match and fails closed. The harness-side fingerprint projection
(`semantic_replay/fingerprint.py`) disambiguates same-name cards in
hand/graveyard/command/exile by occurrence but projects identical battlefield
permanents without an occurrence identity. The recorder's own two tapes agree;
only the live consumer exposes the collision. This is a lane/fixture
capability limit of the current fingerprint contract, not a Semantic Rules
disagreement, and it is recorded rather than normalized: the twin is UNKNOWN
for 2P. 3P/4P/5P fixtures do not select between identical battlefield
permanents.

## XMage — PASS at 3P/4P/5P, UNKNOWN at 2P (fresh direct, clean-process tape twin)

The 4P row is detailed below; the 3P and 5P documents carry the same shape and
all verify. The 2P UNKNOWN is the identical-battlefield-permanent fingerprint
collision documented in the cardinality matrix.

| Fact | Observed |
|---|---|
| Lane | `full-game` semantic replay tape (WS218 recorder/consumer) |
| Fixture | `technical-isamaru-full-game-4p-v1`, 4P, seed `20260824` |
| Candidate | `37e4df6c914f1e189e24f0ef59fa91734c922436`, isolated exact-source build into an isolated Maven repository |
| Observed artifact | kind `file`, sha256 `bf3d91bc2722d186327a5cc69b6fe931e540219a1f506c48bb7003c84068cc27` (the provider's own loaded-artifact digest; equals the isolated candidate jar) |
| Requested / acknowledged seed | `20260824` / `20260824` (`ACKNOWLEDGED_ENGINE_SEED`, `rng_credit = true`) |
| Process identities | `RECORD_FIRST` pid 2494577, `RECORD_SECOND` pid 2494665, `REPLAY_CONSUMER` pid 2494753 — all observed from `/proc`, pairwise distinct |
| Decision tape | 127 engine-identified decisions |
| Event tape | 127 per-step event digests |
| Checkpoints | 128 semantic state digests (initial + post every decision) |
| Tape comparison | match, 127 compared steps, no first divergence |
| Fresh-process consumption | 127/127 steps re-derived; zero divergences |
| Terminal | `GAME_OVER`, complete; outcomes carry winner and conceded/lost rows |
| Semantic comparison | PASS, zero divergences |
| Adversarial controls | all detected, including baseline verification |

Terminal mechanism: the qualified WS218 recorder's `concede_to_finish` after
the 120-decision budget; the fresh consumer re-executes and verifies the
concession and the terminal outcome rows. This is the same terminal contract
the tape lane was qualified with; it is a real engine terminal, not a harness
assertion.

## Forge — PASS at 2P/3P/4P/5P (fresh direct, clean-process generic-lane twin)

The 4P row is detailed below; the 2P/3P/5P documents carry the same shape and
all verify.

| Fact | Observed |
|---|---|
| Lane | `protocol2-jsonl` |
| Fixture | `AF09-GENERIC-forge-4P-v1`, 4P, seed `424242`, the four in-repo singleton Commander deck lists |
| Candidate | bridge/materialization `20e3e1f7ff8e6195b95ed0dc14e0d4c87f1bcf4c` (tree `00006689`), clean exact-source checkout; Rules-Core role `bb0a740d` bound separately in the launch plan |
| Provider-declared commit | `20e3e1f7…`, matches the plan's expected engine commit |
| Requested / acknowledged seed | `424242` / `424242` (`ACKNOWLEDGED_ENGINE_SEED`, `rng_credit = true`) |
| Process identities | `RECORD` pid 2488881, `REPLAY` pid 2489812 — observed and distinct |
| Decision tape | 122 engine-identified decisions (external decision tape replayed in the second process) |
| Event tape | 122 ordered semantic event digests |
| Checkpoints | 244 engine `public_state_digest` checkpoints (pre and post every decision) |
| RNG tape | per-decision `rng_binding.rules_calls` coordinates, identical in both processes |
| Terminal | `GAME_OVER`, complete; one winner, three conceded rows (`left = true`) |
| Semantic comparison | PASS, zero divergences |
| Adversarial controls | all detected, including baseline verification |

Terminal mechanism: from decision 120 onward the pilot chooses the engine's own
offered concession (CR 104.3a, published on every supported priority frame) for
each not-yet-conceded actor until the engine ends the game. The tape records the
concession as an ordinary semantic option fingerprint; the replay process
re-resolves and re-executes it, and the engine's terminal outcome is compared.

## Honest limitations

1. **Local execution class.** These are fresh direct runtime results on the
   exact candidate identities above, executed locally with isolated
   workspaces and repositories. The current-boundary `RNG_REPLAY_*.json`
   integration remains Phase 2 and must run again in the PB-03 pipeline after
   `#450`/`#452` are terminal; these documents are not substitutes for that
   epoch.
2. **XMage artifact provenance.** The candidate was rebuilt from an isolated
   clone of `37e4df6c` into an isolated Maven repository in this session; the
   provider's observed loaded-artifact sha256 is recorded and matches the built
   jar. The shared Maven cache and every foreign worktree were left untouched.
3. **Forge fully-identical duplicates are unreplayable by design.** Forge's
   WS227 option identity intentionally gives indistinguishable duplicate
   siblings one colliding fingerprint and refuses first-match. A frame whose
   entire offered set collides fails closed (`HIDDEN_ZONE_SELECTION` with eight
   identical basics after a long draw-go game). The fixture therefore uses the
   real singleton deck lists and ends at a defined engine-offered concession
   horizon before such a state can arise.
4. **Bounded horizon is not a PASS.** A 4000-decision draw-go horizon run is
   recorded as UNKNOWN in the workstream history even though it showed zero
   semantic divergence; only the complete-terminal runs verify.
5. **Independent engine-side findings (not repaired here).**
   `game_driver.py` records `priority_pass_state_changed` as `None` for every
   candidate because it unwraps an already-unwrapped payload. The engine does
   publish those hashes (Forge on decisions; XMage in the event log). The
   surface is owned elsewhere while foreign writers are active; recorded as
   `F-AF09-1` in the workstream state file.

## What this does and does not claim

- It claims the AF09 clean-process semantic replay twin contract is implemented,
  executable, adversarial-control-covered, and passes for both candidates on
  the exact identities above.
- It does not select a provider, rank candidates, claim Architecture Freeze,
  run AF11, or replace the current-boundary epoch evidence.
