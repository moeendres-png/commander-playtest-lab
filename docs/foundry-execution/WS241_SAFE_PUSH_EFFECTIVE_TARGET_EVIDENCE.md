# WS241 — safe_push Effective Push-Target Evidence Seal

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
| 37 new `test_safe_push_effective_target.py` tests (positives incl. explicit canonical pushurl, `file://` variant, Forge slug; negatives incl. pushurl/pushInsteadOf/insteadOf × scopes, multivalues both orders, lookalike, dry-run→actual mutation, redaction, metrics) | PASS |
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

## 7. Publication security gate (STAGE E — STOP)

No push, no PR, no merge performed. Old canonical publisher is the
vulnerable component; the new version is under review. Resuming toward any
production-like canonical publisher run requires, in order: trusted new-code
closure (this seal), policy authorization, active launcher ancestor writer
lock, verified effective push destination, and independent approver/review
under the project contract. None of the latter are satisfied here — STOP.
Exact next action is in the FINAL HANDOFF.
