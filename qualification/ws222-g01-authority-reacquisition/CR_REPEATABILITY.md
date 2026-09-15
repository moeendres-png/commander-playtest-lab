# WS222 CR_REPEATABILITY

- Repeat acquisition during the workstream returns IDENTICAL bytes:
  two consecutive live fetches of the resolved TXT URL both yield 977822 bytes
  with SHA-256 `4381ad1b…27423f` (MATCH: true), plus the tooling's own
  acquire-then-verify cycle (`VERIFY_PASS 4381ad1b…27423f`).
- `tooling/acquire_cr.py --verify-only` re-hashes captured bytes offline and
  re-checks the effective-date line; current result: match.
- Verdict: `CR_BYTE_EXACT = YES`, `CR_REPEATABLE = YES` (during-workstream server
  behavior; long-term refresh is governed by the successor lock's refresh
  procedure, not by assuming permanence).

Evidence class: DIRECTLY_VERIFIED.
