"""Bridge qualification status relative to the sealed qualification epoch.

AGENTS.md §10 (Studio bridge gate) requires a visible ``BRIDGE_AHEAD_OF_QUALIFICATION``
state everywhere current qualification is reported while ``engine-bridge/`` differs from
the sealed source in ``config/rules_engines.json``, and requires that nothing produced on
a later bridge is presented as covered by the sealed epoch.

No ``Any`` annotations and no runtime ``assert`` statements are used here.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

BRIDGE_ALIGNED = "ALIGNED_WITH_SEALED_EPOCH"
BRIDGE_AHEAD = "BRIDGE_AHEAD_OF_QUALIFICATION"
BRIDGE_UNKNOWN = "UNKNOWN"

_RULES_ENGINES_REL = Path("config/rules_engines.json")
_BRIDGE_REL = "engine-bridge"
_HEX40 = re.compile(r"[0-9a-f]{40}")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _git(repo_dir: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_dir), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def bridge_qualification(repo_dir: str | Path | None = None) -> dict[str, object]:
    """Compare live ``engine-bridge/`` against the sealed qualification epoch source.

    Returns a dictionary containing:
    - ``status``: ``ALIGNED_WITH_SEALED_EPOCH``, ``BRIDGE_AHEAD_OF_QUALIFICATION``, or
      ``UNKNOWN`` when provenance cannot be verified (e.g. outside a git checkout or on
      a shallow history missing the sealed lab commit).
    - ``ahead_of_sealed_epoch``: ``True`` when the bridge differs or the pin drifted.
    - ``covered_by_sealed_epoch``: ``True`` only when both pin and ``engine-bridge/``
      match the sealed freeze-eligible qualification with a clean bridge tree.
    """
    root = Path(repo_dir).resolve() if repo_dir is not None else _repo_root()
    config_path = root / _RULES_ENGINES_REL
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raw = None

    if not isinstance(raw, dict):
        return {
            "status": BRIDGE_UNKNOWN,
            "ahead_of_sealed_epoch": False,
            "covered_by_sealed_epoch": False,
            "sealed_epoch": None,
            "sealed_lab_commit": None,
            "sealed_engine_commit": None,
            "live_engine_commit": None,
            "sealed_bridge_tree": None,
            "head_bridge_tree": None,
            "bridge_dirty": None,
            "reason": "config/rules_engines.json unreadable",
        }

    primary = raw.get("primary_engine")
    freeze = raw.get("architecture_freeze")
    primary_map = primary if isinstance(primary, dict) else {}
    freeze_map = freeze if isinstance(freeze, dict) else {}
    current = freeze_map.get("current_qualification")
    current_map = current if isinstance(current, dict) else {}

    sealed_epoch_raw = current_map.get("evidence_epoch")
    sealed_epoch = str(sealed_epoch_raw) if isinstance(sealed_epoch_raw, str) else None
    sealed_lab_raw = current_map.get("lab_commit")
    sealed_lab = (
        sealed_lab_raw
        if isinstance(sealed_lab_raw, str) and _HEX40.fullmatch(sealed_lab_raw)
        else None
    )
    sealed_eng_raw = current_map.get("engine_commit") or freeze_map.get("engine_commit")
    sealed_engine = (
        sealed_eng_raw
        if isinstance(sealed_eng_raw, str) and _HEX40.fullmatch(sealed_eng_raw)
        else None
    )
    live_engine_raw = primary_map.get("commit")
    live_engine = (
        live_engine_raw
        if isinstance(live_engine_raw, str) and _HEX40.fullmatch(live_engine_raw)
        else None
    )
    freeze_eligible = current_map.get("freeze_eligible") is True

    if sealed_lab is None or sealed_engine is None or live_engine is None:
        return {
            "status": BRIDGE_UNKNOWN,
            "ahead_of_sealed_epoch": False,
            "covered_by_sealed_epoch": False,
            "sealed_epoch": sealed_epoch,
            "sealed_lab_commit": sealed_lab,
            "sealed_engine_commit": sealed_engine,
            "live_engine_commit": live_engine,
            "sealed_bridge_tree": None,
            "head_bridge_tree": None,
            "bridge_dirty": None,
            "reason": (
                "current_qualification.lab_commit missing or invalid"
                if sealed_lab is None
                else "sealed or live engine commit missing or invalid"
            ),
        }

    # Check uncommitted changes under engine-bridge/ first. Untracked files count
    # too: a jar built from this tree would contain them, so they must read as
    # dirty. Gitignored build output (target/, db/) stays invisible via .gitignore.
    dirty_out = _git(
        root, "status", "--porcelain", "--untracked-files=normal", "--", f"{_BRIDGE_REL}/"
    )
    bridge_dirty: bool | None = None if dirty_out is None else bool(dirty_out.strip())

    # Resolve both trees via git rev-parse in one subprocess where possible.
    rev_out = _git(root, "rev-parse", f"{sealed_lab}:{_BRIDGE_REL}", f"HEAD:{_BRIDGE_REL}")
    sealed_tree: str | None = None
    head_tree: str | None = None
    if rev_out is not None:
        lines = [line.strip() for line in rev_out.splitlines() if line.strip()]
        if len(lines) == 2 and _HEX40.fullmatch(lines[0]) and _HEX40.fullmatch(lines[1]):
            sealed_tree, head_tree = lines[0], lines[1]

    pin_drifted = sealed_engine != live_engine

    if bridge_dirty is True:
        return {
            "status": BRIDGE_AHEAD,
            "ahead_of_sealed_epoch": True,
            "covered_by_sealed_epoch": False,
            "sealed_epoch": sealed_epoch,
            "sealed_lab_commit": sealed_lab,
            "sealed_engine_commit": sealed_engine,
            "live_engine_commit": live_engine,
            "sealed_bridge_tree": sealed_tree,
            "head_bridge_tree": head_tree,
            "bridge_dirty": True,
            "reason": "engine-bridge/ has uncommitted changes ahead of the sealed epoch",
        }

    if sealed_tree is None or head_tree is None or bridge_dirty is None:
        return {
            "status": BRIDGE_UNKNOWN,
            "ahead_of_sealed_epoch": False,
            "covered_by_sealed_epoch": False,
            "sealed_epoch": sealed_epoch,
            "sealed_lab_commit": sealed_lab,
            "sealed_engine_commit": sealed_engine,
            "live_engine_commit": live_engine,
            "sealed_bridge_tree": sealed_tree,
            "head_bridge_tree": head_tree,
            "bridge_dirty": bridge_dirty,
            "reason": "git history unavailable or missing sealed lab_commit:engine-bridge tree",
        }

    if sealed_tree != head_tree or pin_drifted or not freeze_eligible:
        reasons: list[str] = []
        if sealed_tree != head_tree:
            reasons.append(
                f"engine-bridge/ tree {head_tree[:10]} differs from sealed {sealed_tree[:10]}"
            )
        if pin_drifted:
            reasons.append("engine pin moved ahead of sealed current_qualification")
        if not freeze_eligible:
            reasons.append("current_qualification is not freeze_eligible")
        return {
            "status": BRIDGE_AHEAD,
            "ahead_of_sealed_epoch": True,
            "covered_by_sealed_epoch": False,
            "sealed_epoch": sealed_epoch,
            "sealed_lab_commit": sealed_lab,
            "sealed_engine_commit": sealed_engine,
            "live_engine_commit": live_engine,
            "sealed_bridge_tree": sealed_tree,
            "head_bridge_tree": head_tree,
            "bridge_dirty": False,
            "reason": "; ".join(reasons),
        }

    return {
        "status": BRIDGE_ALIGNED,
        "ahead_of_sealed_epoch": False,
        "covered_by_sealed_epoch": True,
        "sealed_epoch": sealed_epoch,
        "sealed_lab_commit": sealed_lab,
        "sealed_engine_commit": sealed_engine,
        "live_engine_commit": live_engine,
        "sealed_bridge_tree": sealed_tree,
        "head_bridge_tree": head_tree,
        "bridge_dirty": False,
        "reason": "engine-bridge/ and pin match the sealed freeze-eligible qualification epoch",
    }


__all__ = [
    "BRIDGE_AHEAD",
    "BRIDGE_ALIGNED",
    "BRIDGE_UNKNOWN",
    "bridge_qualification",
]
