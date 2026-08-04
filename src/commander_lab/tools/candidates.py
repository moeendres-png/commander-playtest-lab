from __future__ import annotations

import json
from pathlib import Path

from commander_lab.models import CandidateProfile


def load_candidate_profiles(root: str | Path) -> dict[str, CandidateProfile]:
    path = Path(root) / "data/cards/phase5_upgrade_candidates.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        item["candidate_id"]: CandidateProfile.model_validate(item)
        for item in payload["candidates"]
    }
