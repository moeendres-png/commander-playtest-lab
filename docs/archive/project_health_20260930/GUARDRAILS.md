# Pre-Freeze guardrails (LEDGER D-01, D-02, D-04, D-05, D-08)

This file lists what is in place in the repository and what the owner still has to set. The owner steps are account-level settings. No automated session may change them, so each one below comes with the exact command.

**Why before Freeze.** #420 merged on 2026-09-30 at 18:47 UTC while `conformance` on its exact head (`eeab0f70`) was red: 1 failure in 896 tests. The ruleset requires only `quality`, `security` and `infrastructure`, so auto-merge did not wait. #423 repairs it. Required checks together with strict up-to-date merges make this class of evidence breakage impossible.

## In the repository

| Item | Where | State |
|---|---|---|
| Path-scoped engine workflows always report (a scope job decides, a skipped job counts as passed) | `.github/actions/change-scope`, `conformance-scope` / `smoke-scope` / `integration-scope` / `preflight` | done earlier |
| Every source a gated workflow executes is inside its gates | `scripts/audit_workflow_impact.py` (#417) | done |
| Node-24 action pins (D-05) | all workflows | **this change**, see the table below |
| First-option ratchet (D-08) | `tests/unit/test_first_option_ratchet.py`, runs in `quality` (pytest) | **this change** |

**Node-24 pins.** Each target is the lowest major version whose `action.yml` declares `using: node24`, checked at the pinned SHA:

| Action | Before (Node 20) | After |
|---|---|---|
| `actions/checkout` | `11bd7190…` (v4.2.2) | `fbc6f399…` (v5.1.0) |
| `actions/setup-python` | `82c7e631…` (v5) | `ece7cb06…` (v6.3.0) |
| `actions/upload-artifact` | `65462800…` (v4) | `b7c566a7…` (v6.0.0) |

These were already on Node 24 and are unchanged:
- `actions/setup-java` `b6effb05…` (v5.7.0);
- `actions/cache` `55cc8345…` (v6.1.0);
- the single `actions/checkout@d23441a4…` (v6.1.0) in `opencode.yml`.

**First-option ratchet.** It counts `…actions/options/candidates/choices/targets/abilities` followed by `.get(0)` / `[0]` in these trees:
- `engine-bridge/src/{main,test}/java`
- `src/commander_lab`
- `scripts`

The 46 occurrences on `main` are the frozen baseline. Production Java has 0. The rules are:
- no file may gain an occurrence;
- a file not listed may have none;
- a count that drops must be lowered in the baseline.

The behavioural proof for the production validation seam stays in `current_boundary/shortcut_campaign.py`. The ratchet only stops new occurrences from arriving unreviewed. Forge has the equivalent gate in forge#12 (`FirstOptionRatchetTest`).

## Owner actions (exact commands)

Run these as the repository owner with `gh` authenticated. Each step is reversible.

### 1. Lab `main`: required checks + strict up-to-date (D-01, D-04)

```bash
R=moeendres-png/commander-playtest-lab
ID=$(gh api repos/$R/rulesets --jq '.[] | select(.name=="CPL - Canonical Main Protection") | .id')
gh api repos/$R/rulesets/$ID > /tmp/ruleset.json
jq '(.rules[] | select(.type=="required_status_checks") | .parameters) |= (
      .strict_required_status_checks_policy = true
    | .required_status_checks = ([
        "quality","security","infrastructure","repository-tree-integrity",
        "conformance","real-4p-smoke","build-and-integrate","preflight","h4-xmage","h4-forge"
      ] | map({context: .})))
    | {name, target, enforcement, conditions, rules, bypass_actors}' /tmp/ruleset.json > /tmp/ruleset.new.json
gh api -X PUT repos/$R/rulesets/$ID --input /tmp/ruleset.new.json
```

The `jq` edit assumes the ruleset already contains a `required_status_checks` rule, because it requires `quality`, `security` and `infrastructure` today. Check `/tmp/ruleset.new.json` before the `PUT`.

**Name collision to know about.** Two jobs report the check name `conformance`:
- the bridge suite in `xmage-full-game-conformance.yml`, which always reports;
- the path-filtered job in `candidate-lossless-handoff.yml`.

Required checks match by name. If a PR also triggers the second job, it has to pass as well. That is the intended outcome, but read a red `conformance` with both workflows in mind.

**Effect:**
- a PR merges only when every listed check passed on a head that is up to date with `main`;
- auto-merge waits for all of them;
- a path-irrelevant PR passes through the skipped heavy jobs.

### 2. `mage` and `forge`: branch protection (D-04)

These rules forbid force-push and deletion and require a PR. Required status checks are left out on purpose: `mage` master is red today, and `forge` master must not be merged by policy.

```bash
for R in moeendres-png/mage moeendres-png/forge; do
  B=$(gh api repos/$R --jq .default_branch)
  gh api -X PUT repos/$R/branches/$B/protection --input - <<'JSON'
{"required_status_checks": null,
 "enforce_admins": false,
 "required_pull_request_reviews": {"required_approving_review_count": 0},
 "restrictions": null,
 "allow_force_pushes": false,
 "allow_deletions": false}
JSON
done
```

Protect the candidate branches the Lab pins as well. XMage pin `9375f35a` lives on the `mage` candidate branch, and the Forge candidate on `forge`'s #11 branch. Run the same call with `B=<candidate branch>`, so that a force-push cannot orphan a pinned SHA.

### 3. Dead workflow registrations (D-02)

There are 181 of them. Each is absent from `main` and from every open PR head, and none has run for 14 days or more.

```bash
jq -r '.workflows[].id' docs/ci_efficiency_20260930/DEAD_WORKFLOW_REGISTRATIONS.json \
  | xargs -n1 gh workflow disable -R moeendres-png/commander-playtest-lab
```

To undo one: `gh workflow enable <id> -R moeendres-png/commander-playtest-lab`.

`ARCHITECTURE_FREEZE = NOT CLAIMED` · `PRODUCTION_PROVIDER = NOT SELECTED`
