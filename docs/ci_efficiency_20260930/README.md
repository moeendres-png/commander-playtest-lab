# CI efficiency and repository hygiene (2026-09-30)

These are the measurements, the changes made, and the open recommendations. Author: Claude Opus 5.5, with user authorization for hygiene and efficiency work.

## Measured before the change (PR #370, bridge test and docs only)

A PR that touches `engine-bridge/**` started 7 workflows and used about **48 runner-minutes**. The largest items:

| Repeated work | Workflows | Cost |
|---|---|---|
| XMage built from source, 4× | conformance, real-4p-smoke, external-engine-integration, H4 | 2.4–3.7 min each |
| Full bridge test suite, 4× | the same four | about 2 min each |
| XMage Docker image | H4 | 5.9 min |
| Forge Docker image, for an XMage-only change | H4 `h4-forge` | 10.3 min |

## Changed (#374, merged)

- **`.github/actions/pinned-xmage-engine`.** The `org.mage` artifacts are cached under the full commit of the checked-out XMage source, which is verified against the pin. They are built only on a miss. The action logs the engine jar digests. H4 deliberately keeps its direct-source build, because that is the materialization evidence.
- **Bridge test suite.** It runs in conformance and H4. real-4p-smoke and external-engine-integration only (test-)compile and package.
- **Conformance trigger.** Conformance now also runs on `config/rules_engines.json`, so every repin runs the bridge suite against the new engine.
- **H4 provider scope.** The Forge image is not built for `engine-bridge/**`- or Markdown-only PRs. The XMage image is not built for Forge-only PRs. Pushes and manual runs build both.
- **Verified live.** On the first run all three cache users missed in parallel. One saved the cache, and the other two skipped saving without error. Caches keyed by pin now exist on `main` and on other lanes' PRs.

## Recommendations that need the repository owner

1. **Required checks.** The `CPL - Canonical Main Protection` ruleset requires only `quality`, `security` and `infrastructure`. Auto-merge therefore merges even when the bridge suite (`conformance`), H4 or the real-4P smoke fails. Until this is fixed, bridge PRs must be merged manually, after checking every check.
   - Making `conformance` required directly would block every PR that doesn't touch the bridge. The workflow is path-filtered, and a required check that never reports stays "expected" forever.
   - Recommendation, planned after #360 lands, because #360 edits these workflow files: merge the four engine workflows into one.
     - A `scope` job derives the needed parts from the changed paths.
     - A final `engine-gate` job (`needs:` all, `if: always()`) fails if any needed job failed and passes when nothing engine-related changed.
     - Then make `engine-gate` required.
     - This avoids an aggregator that occupies a runner while polling.
2. **Dead workflow registrations.** GitHub has 289 workflows registered for this repository, and only 20 exist on `main`. `DEAD_WORKFLOW_REGISTRATIONS.json` lists 181 of them. Each is absent from `main` and from every open PR head, and has had no runs for 14 days.
   - Disabling is reversible (`gh workflow enable <id>`). The automated session was not permitted to do it.
   - Command:

     ```bash
     jq -r '.workflows[].id' docs/ci_efficiency_20260930/DEAD_WORKFLOW_REGISTRATIONS.json | xargs -n1 gh workflow disable -R moeendres-png/commander-playtest-lab
     ```

3. **Codex review bot.** Its quota is exhausted, so it posts a "usage limits" comment on every PR. Each comment triggers `opencode.yml`, which then skips its job, and each is an Auto-fix event. Recommendation: pause the connector for this repository, or restore its quota.
4. **Digest-manifest conflicts.** `WS17_SHA256SUMS` also hashes `qualification/SHA256SUMS`. That entry is redundant, because every file under `qualification/` is already listed directly. It changes in every qualification PR, so it is a constant merge-conflict source (#333, #337, #360).
   - Two ways to resolve a conflict: regenerate with `scripts/regenerate_hash_manifests.py` after merging, or remove the redundant nested entry. Removing it is a small WS17 contract change for the Coordinator; it does not weaken integrity, because the nested manifest is still verified against the tree.
