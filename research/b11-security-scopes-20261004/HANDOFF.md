# B11 checkpoint

Issue492, PR526; branch hardening/b11-scoped-security-evidence-20261004.
Base d9d2eda2 was integrated with main eede8227 by ordinary merge. Claude's
provider surfaces are reserved; this branch owns only CI/security scope work.
Local source4d37273b produced a complete PASS with all seven actual collection
outcomes success on Python3.14.4. Raw scoped inventories/audits/SBOMs/licenses,
wheel-smoke receipt, seal and exact commands are retained in LIVE_AFTER.json.gz;
VALIDATION.json binds SHA/TREE, input hashes, wheel, tools and archive digest.
The previous live source5a5acf36 is retained as LIVE_FAILURE_BEFORE.json.gz:
runtime audit clean, tooling pip25.1.1 had12 advisory records, overallFAIL.
No exception/ignore was used; hash-pinned pip26.2 resolved the local red.
138 affected tests pass. Hosted Python3.12, other required contexts and fresh
independent review remain before merge/closing492. Green local security scope
does not prove gameplay, package general functionality or hostile CI containment.

Reproduce: create a clean Python>=3.12 venv with system-site-packages=false;
install requirements/security-bootstrap.txt using --require-hashes --only-binary=:all:;
install requirements/lock.txt using --require-hashes; build wheel using
--no-deps --no-build-isolation; install that wheel with --no-index --no-deps;
run pip check. Run security_evidence.py prepare into an external evidence dir
with a fresh external runtime path. Execute the six audit/SBOM/license steps
from ci.yml, using that evidence directory and the exact prepared interpreter.
Set B11_STEP_RESULTS to their actual outcomes plus prepare-scopes; run seal.
The two wrappers document local path mappings; LOCAL_EXECUTION.json inside the
raw bundle records exact commands. Current vulnerability results can change.

Local wheels/envs/logs are disposable; all material observations are committed.
Source changes after4d must be impact-adjudicated; new hosted CI binds exact head.
No engine pin, provider selection, Freeze, production repo or required-gate change.
