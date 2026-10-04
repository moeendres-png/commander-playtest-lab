# B11 security evidence split

Primary campaign: pre-Freeze coordination/execution, roadmap#479, child#492.
Base: Lab d9d2eda2d30e0825616a690ce4278584d0fcfe5a /
TREE8144004b1fadbffe19ecce9c8cbc2d91473382d1. Sole writer Codex.
Owned branch: hardening/b11-scoped-security-evidence-20261004.

The security job installs its full hash lock once and its actual built wheel; generator versions and every
installed generator/transitive distribution must match that lock. A separate hash-pinned
bootstrap pip26.2 is explicitly identified as CI infrastructure and is never treated
as shipped runtime. Audit resolution uses --disable-pip with exact inventory
pins. No unhashed audit-tool reinstall remains. The full CI inventory is still
audited (except the source-bound private project, as the prior editable exclusion).

B9 supplies wheel/source matching, declared base dependency closure, exact lock
subset, isolated wheel installation, pip check, import and CLI checks. The product
venv drops bootstrap pip unless the wheel actually requires it. Its inventory
must equal the installed wheel plus that exact closure; no extras or copied CI
tooling. A legitimately required tool is not blacklisted from the closure.

Each scope has its own inventory, dependency audit, SBOM and license file. The
seal compares SBOM/license/audit inventories with actual scoped distributions,
requires every collection step to succeed, rechecks both environments, source
bytes/HEAD/TREE and wheel/receipt hashes, then records artifact digests and step
outcomes. Missing steps are NOT_RUN, failure evidence stays FAIL, never PASS.
The private project's omission from public vulnerability-service queries is
explicit; it remains in inventories, SBOMs and license reports. Vulnerability
results depend on the current public service, not a claim of frozen advisories.

B10's pinned broad scan and the existing project sentinel remain independent.
Security job and existing required contexts retain their fail-closed behavior.
No new required gate, provider choice, Freeze, engine pin or Rules change.

Commands: affected pytest tests plus ruff checks; build wheel with pinned host
build tools/no isolation; prepare, execute the seven named inline workflow steps,
seal with their actual outcomes. Exact-head hosted security evidence and independent
review are required before merge and issue closure. This does not claim general
adversarial CI containment or Rules qualification.

The initial live probe rejected duplicate project metadata produced by editable
installation (dist-info plus source egg-info). CI tooling now installs the actual
wheel too; it does not collapse ambiguous duplicate distributions. The retained
before record documents the refusal at source42289b82. Local disposable tooling
environment with system packages was also refused, never used as PASS evidence.

The full live run at5a5acf36 produced both scopes but tooling audit found12
vulnerability records for the local bootstrap pip25.1.1. Seal remainedFAIL.
requirements/security-bootstrap.txt now binds pip26.2 to its exact PyPI wheel
digest; collector checks the installed version and source bytes. No advisory
ignore or runtime blacklist is introduced. Available raw artifacts are hashed
even when preparation/collection fails, so failure evidence is resumable too.
