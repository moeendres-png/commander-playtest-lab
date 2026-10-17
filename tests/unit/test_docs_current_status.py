"""Orientation docs must agree with the claimed Architecture Freeze.

config/rules_engines.json is the machine-readable status (read only here).
When architecture_freeze.status == "CLAIMED", the present-tense orientation
documents in ORIENTATION_DOCS must not repeat the stale NOT CLAIMED /
NOT SELECTED status. Dated historical records are deliberately not covered:
they describe their own moment.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Present-tense orientation documents. New orientation documents are added
# to this tuple; dated historical records stay out on purpose.
ORIENTATION_DOCS = (
    "docs/README.md",
    "docs/REPOSITORY_TRIAGE_INDEX.md",
    "docs/architecture.md",
    "docs/claude/SESSION_PLAYBOOK.md",
    "docs/commander-simulator-next.prd.md",
    "README.md",
)

STALE_TOKENS = ("NOT CLAIMED", "NOT_CLAIMED", "NOT SELECTED", "NOT_SELECTED")
# A stale token survives only on a line that also names the status update or
# states the old status in the past tense (e.g. a dated "Status update"
# note quoting what the baseline used to say).
EXEMPT_LINE_MARKERS = ("Status update", "was ")


def test_orientation_docs_match_claimed_freeze() -> None:
    engines = json.loads((ROOT / "config" / "rules_engines.json").read_text(encoding="utf-8"))
    if engines.get("architecture_freeze", {}).get("status") != "CLAIMED":
        return
    violations = []
    for rel in ORIENTATION_DOCS:
        lines = (ROOT / rel).read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, start=1):
            stale = [token for token in STALE_TOKENS if token in line]
            exempt = any(marker in line for marker in EXEMPT_LINE_MARKERS)
            if stale and not exempt:
                violations.append(f"{rel}:{lineno}: stale status {stale}: {line.strip()}")
    assert not violations, (
        "orientation docs repeat a stale NOT CLAIMED / NOT SELECTED status:\n"
        + "\n".join(violations)
    )
