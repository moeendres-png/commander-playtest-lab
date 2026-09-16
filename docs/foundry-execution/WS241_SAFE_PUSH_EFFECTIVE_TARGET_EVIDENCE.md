# WS241 — safe_push Effective Push-Target Evidence Seal (incl. WS241-C final remediation)

Status: SEALED LOCAL IMPLEMENTATION. No publication. No independent review.
`ARCHITECTURE_FREEZE=NOT_CLAIMED`; `PRODUCTION_PROVIDER=NOT_SELECTED`;
`FULL107=NOT_RUN`.

## 1. Source lock

- Repository: `moeendres-png/commander-playtest-lab`
- Branch: `ws241/safe-push-effective-target-20260916`
- Worktree: `/home/moeen/code/ws241-safe-push-effective-target`
- Audit base: `aebcfda37d61eb435dde6cd11792ef80019dcd10`
  (TREE `bf003afc0c0b71535094b6b96e3b1184d6dd0f1f`, per workstream issuance)
- Implementation commit: `bf504a914ce1e951fb051576035e5b92f58ebf21` (local only,
  clean tree at seal time)
- Main drift at seal: none observed (`aebcfda3` still tip of fetched main line
  in this worktree's log; no rebase performed)
- Task authority: issue #204 (CODE_DERIVED gap report; adjacent, pre-existing,
  not a WS240 regression). #196 covers cross-repo tool-path authority.
- State file (outside worktree):
  `/home/moeen/.local/state/commander-simulator-next/ws241-safe-push-effective-target/WORKSTREAM_STATE.yaml`
  (schema 2.0; `validated_head: null` — no independent validation credit claimed)

## 2. Blob hashes at implementation commit (SHA-256)

- `0b6970a9...a260` tools/foundry/safe_push.py (changed)
- `375bf6e2...4275` tests/foundry/test_safe_push.py (rig paths only)
- `d21a9337...aaf32` tests/foundry/test_safe_push_effective_target.py (new)
- `f0bcf184...ebe9e` tests/foundry/test_launcher.py (slug-anchored hook remote)
- `13ab24dd...f9a1e` tests/foundry/test_ws75_tooling_hardening.py (rig path only)
- `2a85f2c0...133` tests/foundry/test_telemetry.py (slug form + redaction asserts)
- `a3129733...e544c` tools/foundry/source_lock.py (UNCHANGED — reused read-only)
- `78fbf2c5...c0a5e` tools/foundry/launcher.py (UNCHANGED — hook is L3-partial only)
- `9778b9a0...f036` opencode.json (UNCHANGED)

## 3. Fail-before — OLD canonical safe_push (DIRECTLY_VERIFIED, hermetic)

Hermetic `/tmp` fixtures: local bare remotes A (canonical) / B (evil),
isolated HOME/global/system config, no network, no GitHub push. Full dry-run
gates (state 2.0, ancestry, ancestor-held writer lock, clean tree) satisfied;
only the push-target identity varied.

| Scenario | OLD dry-run verdict |
|---|---|
| canonical fetch + divergent `remote.origin.pushurl` → B | `DRY_RUN_OK` (gap holds) |
| `url.<B>.pushInsteadOf = <fetch>` | `DRY_RUN_OK` (gap holds) |
| reversed multivalue origin (evil first, canonical last; `--get` returns last) | `DRY_RUN_OK` (gap holds) |
| lookalike fetch path containing slug as substring (`.../fixture-repo-evil.git`, evil main populated) | `DRY_RUN_OK` (gap holds) |
| `url.<B>.insteadOf = <fetch>` | rejected, but incidentally at the creation gate (`cannot resolve remote main/master`), not by identity |
| multivalue canonical-first + evil-second | rejected (`--get` surfaces last = evil) — order-dependent, not systematic |
| `ls-remote` failure stderr | echoed raw into `PUSH_REJECT` (host/URL leak) |
| `git push` failure stderr | echoed raw into `PUSH_REJECT` (URL/credential leak path) |

Git semantics used as reference (DIRECTLY_VERIFIED locally):
`git remote get-url --push --all <remote>` expands pushurl/pushInsteadOf/insteadOf;
`git config --get` returns the last multivalue record; `git push <remote>`
honors pushurl while `git ls-remote <remote>` does not — hence gate-10/fetch
reads cannot establish the gate-11 write destination.

## 4. Fix-after — NEW code (DIRECTLY_VERIFIED, hermetic)

Gate 3 replaced: exact owner/repo identity on BOTH the single configured
fetch URL record and the single Git-expanded effective push URL;
zero/multiple records, any `insteadOf`/`pushInsteadOf` presence (local,
global, system, environment), divergent/multiple pushurl, and non-exact
slugs fail closed. GitHub HTTPS/SSH delegate to the shared
`source_lock.is_canonical_remote` exact identity (valid for CPL and Forge
slugs); `file://`/plain paths require slug-boundary-exact suffix match.
Pre-write re-check immediately before `git push` (dry-run/actual parity).
All reject reasons and metric `reject_reason` values carry counts/static
text only — no URLs, userinfo, or remote output.

| Check | Result |
|---|---|
| 53 collected items in `test_safe_push_effective_target.py` (36 functions; pre-C revision had 37 items — see §8.5 for methodology; positives incl. Forge slug, unit matrices; negatives incl. ALL pushurl forms, rewrites × scopes, multivalues both orders, mirror/receivepack, lookalike, dry-run→actual mutation, redaction ×4, metrics) | PASS (post-C bytes; §8) |
| 30 existing `test_safe_push.py` (creation/lineage/FF/lock/state gates retained) | PASS |
| source-lock suites (identity, P1 rewrite, P2 multivalue — untouched code) | PASS |
| launcher / ws75 / telemetry / state / writer-lock / freshness / drift / foundry-tools suites | PASS (3 consumer fixtures updated to exact-identity slug form; 1 telemetry redaction assert strengthened to no-URL-material) |
| `ruff check` on all touched files | PASS |
| `ruff format --check` on all touched files | PASS |
| `py_compile` on changed/new Python files | PASS |
| `mypy` | NOT_RUN — binary not installed in this environment (environmental) |
| Full unrelated suite beyond the impacted set | NOT_RUN per impact policy |

Combined impacted run: 408 passed, 1 skipped (pre-existing environmental
skip `test_telemetry.py:104` — no live export snapshot present; preserved,
not introduced).

## 5. Invalidated vs retained evidence

- Invalidated by the byte change: any prior PASS that exercised OLD gate-3
  substring semantics (cause: changed bytes; old results do not validate new
  bytes). All such surfaces were re-executed above against the new bytes.
- Retained: WS239/WS240 source-lock seals (code untouched; suites re-run
  green here as regression only, not as requalification credit).
- `test_telemetry.py::test_safe_push_emits_metrics` now uses slug
  `slug-here/r`; intent (metrics on DRY_RUN_OK) unchanged.

## 6. Known residual / unknowns (not claimed)

- Non-atomicity: config could change in the instant between the final
  re-check and the `push` exec. Stated in the module docstring; window
  narrowed to that instant, never the earlier dry-run. No in-process
  file-locking of git config exists (git offers none).
- HTTPS/SSH positive transport remains CODE_DERIVED for transport (no
  network in hermetic fixtures); identity function units are
  DIRECTLY_VERIFIED.
- Launcher pre-push hook remains L3-partial by construction (bypassable via
  `--no-verify`); destination identity now rests on safe_push gates, not the
  hook marker. The marker is still set only by safe_push.
- Publication, independent review, merge: NOT_RUN / gated (see §7).

## 8. WS241-C final remediation (adjudicated corrections 1–5, one commit)

Adjudication:
`/home/moeen/.local/state/commander-simulator-next/legacy-recovery-preflight-aebcfda3/ISSUE204_CANDIDATE_ADJUDICATION_2026-09-16.md`
(read-only; surviving line C with minimum corrections; A/B archived as
reference, untouched).

1. ANY `remote.<name>.pushurl` record (single, blank, multivalue,
   environment-injected) is now rejected; the two single-pushurl positives
   were converted to reject-tests. Rationale aligns with #204 + A/B consensus.
2. `fetch==push` byte equality enforced after `get-url --push --all`
   resolution (pure helper `_push_matches_fetch`; closes the
   divergent-but-both-exact residual).
3. `remote.<name>.mirror` / `remote.<name>.receivepack` records of any kind
   rejected (unreadable fails closed). Exact Git behavior verified
   hermetically (DIRECTLY_VERIFIED, `/tmp/ws241c-gitbehavior/probe.py`):
   mirror=true + explicit refspec → push refused
   (`fatal: --mirror can't be combined with refspecs`, rc=128; without a
   refspec mirror mode pushes all refs, so the key is incompatible with the
   single authorized refspec either way); receivepack=<script> → the
   configured program IS executed in place of git-receive-pack (marker
   proved execution — a cooperating script could redirect/accept);
   receivepack=true → push fails (protocol break); `get-url --push --all`
   is unaffected by both keys, so explicit inspection is required.
4. `_no_push_rewrites` now returns False on ANY inspection failure
   (subprocess/timeout/unexpected), unit-tested for OSError and
   TimeoutExpired; no traceback, no raw data escapes.
5. Test-count methodology corrected: the new security file contains
   **36 test functions, 3 of them parametrized (14+3+3), yielding exactly
   53 collected pytest items** (`--collect-only` verified), 120 assert
   occurrences. Earlier "37" counts referred to the pre-C revision's
   collected items and are superseded. Counts below always mean collected
   items executed.

WS241-C blobs (SHA-256, final bytes):
- `bfbac978...c25cbd` tools/foundry/safe_push.py
- `8bf82070...c35f330` tests/foundry/test_safe_push_effective_target.py

WS241-C validation on final bytes (DIRECTLY_VERIFIED):
- new security suite: 53/53 collected items PASS
- existing safe_push suite (gates 4–11 retention): 30/30 PASS
- full impacted set (safe_push ×2, source-lock ×3, launcher, ws75,
  telemetry, state ×2, writer-lock, freshness, drift, foundry-tools):
  **425 passed, 1 skipped** (pre-existing environmental skip
  `test_telemetry.py:104`, preserved)
- `ruff check`: PASS; `ruff format --check`: PASS; `py_compile`: PASS;
  `mypy`: NOT_RUN (binary absent — environmental, unchanged)
- `source_lock.py`, `launcher.py`, `metrics.py`, `writer_lock.py`:
  byte-untouched (read-only per scope); no second implementation surface
  created; no cherry-pick from A/B (mirror/receivepack guard implemented
  natively on verified behavior).

## 7. Publication security gate (STAGE E — STOP)

No push, no PR, no merge performed. Old canonical publisher is the
vulnerable component; the new version is under review. Resuming toward any
production-like canonical publisher run requires, in order: trusted new-code
closure (this seal), policy authorization, active launcher ancestor writer
lock, verified effective push destination, and independent approver/review
under the project contract. None of the latter are satisfied here — STOP.
Exact next action is in the FINAL HANDOFF.
