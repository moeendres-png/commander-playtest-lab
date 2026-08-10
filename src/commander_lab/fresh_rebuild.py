from __future__ import annotations

import base64
import copy
import gzip
import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from commander_lab.engine.structural.profiles import build_default_profile
from commander_lab.models import (
    CandidateProfile,
    CardIdentity,
    CardLegality,
    Color,
    DataQuality,
    StructuralCardProfile,
    StructuralDeckProfile,
)
from commander_lab.storage import sha256_value
from commander_lab.storage.run_identity import sha256_run_value
from commander_lab.tools.candidates import BASIC_LANDS, load_candidate_profiles

ROGSHAI_DECK_ID = "rogshai/current"
ROGSHAI_COMMANDERS = (
    "Ishai, Ojutai Dragonspeaker",
    "Rograkh, Son of Rohgahh",
)
ROGSHAI_COLORS = frozenset({Color.WHITE, Color.BLUE, Color.RED})
FRESH_ROGSHAI_PREFIX = "rogshai/fresh/"
RUNTIME_CONTRACT_PATH = Path("data/rogshai_mvp/K1_K2_RUNTIME_CONTRACT.json")
RUNTIME_SNAPSHOT_PATH = Path("data/rogshai_mvp/CURRENT_DRIVE_RUNTIME.json.gz.b64")
DISABLED_QUALITY_PRIORS = {
    "current_deck_membership_prior": "disabled",
    "historical_include_prior": "disabled",
    "historical_cut_prior": "disabled",
    "protected_card_quality_bonus": "disabled",
    "allocation_quality_prior": "disabled",
    "popularity_prior": "disabled",
}


class FreshRebuildDataError(RuntimeError):
    """Fail-closed error for stale or inconsistent RogShai fresh-rebuild inputs."""


@dataclass(frozen=True, slots=True)
class FreshRogShaiUniverse:
    """Current, bias-neutral RogShai construction universe.

    Membership and physical feasibility come from the current Drive projection. Structural
    profiles are attached separately and may be missing. Missing modeling lowers confidence
    and creates a review gate; it never removes the card from ``candidate_names``.
    """

    candidates: Mapping[str, CandidateProfile]
    review_required: Mapping[str, CardIdentity]
    candidate_names: frozenset[str]
    available_quantities: Mapping[str, int]
    verified_physical_names: frozenset[str]
    coverage_status_by_name: Mapping[str, str]
    candidate_facts_by_name: Mapping[str, Mapping[str, object]]
    source_inventory_path: str
    runtime_sha256: str

    @property
    def candidate_count(self) -> int:
        return len(self.candidate_names)

    @property
    def structurally_scorable_count(self) -> int:
        return len({candidate.card.oracle_name for candidate in self.candidates.values()})

    @property
    def review_required_count(self) -> int:
        return len(self.review_required)

    def candidate_by_name(self) -> dict[str, CandidateProfile]:
        return {candidate.card.oracle_name: candidate for candidate in self.candidates.values()}


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        raise FreshRebuildDataError(f"required RogShai MVP input missing: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_object(path: Path) -> dict[str, Any]:
    try:
        if path.name.endswith(".json.gz.b64"):
            compressed = base64.b64decode(path.read_text(encoding="ascii"))
            text = gzip.decompress(compressed).decode("utf-8")
        elif path.suffix == ".gz":
            text = gzip.decompress(path.read_bytes()).decode("utf-8")
        else:
            text = path.read_text(encoding="utf-8")
        payload = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FreshRebuildDataError(f"cannot read RogShai MVP input: {path}") from exc
    if not isinstance(payload, dict):
        raise FreshRebuildDataError(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


def load_fresh_rebuild_runtime(root: str | Path) -> dict[str, Any]:
    """Load the checked-in current-Drive projection and reject drift fail-closed."""

    root_path = Path(root)
    contract = _json_object(root_path / RUNTIME_CONTRACT_PATH)
    runtime_spec = contract.get("current_drive_runtime")
    if not isinstance(runtime_spec, dict):
        raise FreshRebuildDataError("current_drive_runtime contract is missing")

    relative_path = Path(str(runtime_spec.get("path", RUNTIME_SNAPSHOT_PATH.as_posix())))
    runtime_path = root_path / relative_path
    observed_sha = _sha256_file(runtime_path)
    expected_sha = str(runtime_spec.get("content_sha256", ""))
    if observed_sha != expected_sha:
        raise FreshRebuildDataError(
            f"current Drive runtime hash mismatch: {observed_sha} != {expected_sha}"
        )

    compact = _json_object(runtime_path)
    compact_rows = compact.get("cards")
    if not isinstance(compact_rows, list):
        raise FreshRebuildDataError("current Drive runtime cards must be a list")
    expected_count = int(runtime_spec.get("candidate_count", 0))
    if len(compact_rows) != expected_count or int(compact.get("expected", -1)) != expected_count:
        raise FreshRebuildDataError(
            "current RogShai candidate universe incomplete: "
            f"{len(compact_rows)} != {expected_count}"
        )

    rows: list[dict[str, object]] = []
    for raw in compact_rows:
        if not isinstance(raw, dict):
            raise FreshRebuildDataError("candidate row must be an object")
        color_text = str(raw.get("ci", ""))
        rows.append(
            {
                "card_id": str(raw.get("id", "")),
                "oracle_name": str(raw.get("n", "")),
                "color_identity": list(color_text),
                "commander_legal": raw.get("l") is True,
                "mana_value": raw.get("mv"),
                "type_line": str(raw.get("t", "Unknown")),
                "basic_land": raw.get("b") is True,
                "physical": {
                    "available": int(raw.get("a", 0) or 0),
                    "allocated_to_korvold": int(raw.get("k", 0) or 0),
                },
                "coverage": {
                    "status": str(raw.get("cv", "UNKNOWN")),
                    "requires_model_review": raw.get("cv") != "STRUCTURALLY_MODELED",
                },
            }
        )

    names = [str(row["oracle_name"]) for row in rows]
    card_ids = [str(row["card_id"]) for row in rows]
    if "" in names or len(set(names)) != expected_count:
        raise FreshRebuildDataError("candidate universe has missing or duplicate oracle names")
    if "" in card_ids or len(set(card_ids)) != expected_count:
        raise FreshRebuildDataError("candidate universe has missing or duplicate card IDs")

    bias = compact.get("bias")
    if not isinstance(bias, dict):
        raise FreshRebuildDataError("fresh-rebuild bias policy is missing")
    for key, expected in DISABLED_QUALITY_PRIORS.items():
        if bias.get(key) != expected:
            raise FreshRebuildDataError(f"forbidden quality prior is not disabled: {key}")
    if bias.get("allocation_may_affect_physical_feasibility_only") is not True:
        raise FreshRebuildDataError("allocation is not constrained to physical feasibility")
    if bias.get("control_deck_visible_in_independent_stage") is not False:
        raise FreshRebuildDataError("current RogShai control is visible in independent stage")

    relations = compact.get("relations", [])
    normalized_relations = [
        {"source_name": str(row.get("s", "")), "target": str(row.get("t", ""))}
        for row in relations
        if isinstance(row, dict)
    ]
    re²È="24¥˜‘ÕÁ±¥…Ñ•}¹½¹‰…Í¥Ìè(€€€€€€€É…¥Í”Y…±Õ•ÉÉ½È¡˜‰Í¥¹±•Ñ½¸Ù¥½±…Ñ¥½¸èí‘ÕÁ±¥…Ñ•}¹½¹‰…Í¥Íôˆ¤(€€€½Ù•É}‰…Í¥}Á½±¥ä€ôÍ½ÉÑ• (€€€€€€€¹…µ”™½È¹…µ”°½Õ¹Ð¥¸½Õ¹ÑÌ¹¥Ñ•µÌ ¤¥˜¹…µ”¥¸	M%}19L…¹½Õ¹Ð€ø€ÔÀ(€€€€¤(€€€¥˜½Ù•É}‰…Í¥}Á½±¥äè(€€€€€€€É…¥Í”Y…±Õ•ÉÉ½È¡˜‰‰…Í¥Œµ±…¹ÁÉ½©•Ð…Ù…¥±…‰¥±¥Ñä•á••‘•èí½Ù•É}‰…Í¥}Á½±¥åôˆ¤((€€€µ¥ÍÍ¥¹}Õ¹¥Ù•ÉÍ”€ôÍ½ÉÑ•¡Í•Ð¡µ…¥¹‰½…É‘}¹…µ•Ì¤€´Í•Ð¡Õ¹¥Ù•ÉÍ”¹…¹‘¥‘…Ñ•}¹…µ•Ì¤¤(€€€¥˜µ¥ÍÍ¥¹}Õ¹¥Ù•ÉÍ”è(€€€€€€€É…¥Í”Y…±Õ•ÉÉ½È¡˜‰…É‘Ì½ÕÑÍ¥‘”™É•Í I½M¡…¤…¹‘¥‘…Ñ”Õ¹¥Ù•ÉÍ”èíµ¥ÍÍ¥¹}Õ¹¥Ù•ÉÍ•ôˆ¤(€€€Õ¹…Ù…¥±…‰±”€ôÍ½ÉÑ• (€€€€€€€¹…µ”(€€€€€€€™½È¹…µ”°½Õ¹Ð¥¸½Õ¹ÑÌ¹¥Ñ•µÌ ¤(€€€€€€€¥˜Õ¹¥Ù•ÉÍ”¹…Ù…¥±…‰±•}ÅÕ…¹Ñ¥Ñ¥•Ì¹•Ð¡¹…µ”°€À¤€ð½Õ¹Ð(€€€€¤(€€€¥˜Õ¹…Ù…¥±…‰±”è(€€€€€€€É…¥Í”Y…±Õ•ÉÉ½È (€€€€€€€€€€€€‰Í¥µÕ±Ñ…¹•½ÕÌÁ¡åÍ¥…°‰Õ¥±‘…‰¥±¥Ñä™…¥±•…™Ñ•È-½ÉÙ½±É•Í•ÉÙ…Ñ¥½¹Ìè€ˆ(€€€€€€€€€€€˜‰íÕ¹…Ù…¥±…‰±•ôˆ(€€€€€€€€¤((€€€‰å}¹…µ”€ôÕ¹¥Ù•ÉÍ”¹…¹‘¥‘…Ñ•}‰å}¹…µ” ¤(€€€Õ¹É•Í½±Ù•€ôÍ½ÉÑ• (€€€€€€€¹…µ”(€€€€€€€™½È¹…µ”¥¸Í•Ð¡µ…¥¹‰½…É‘}¹…µ•Ì¤(€€€€€€€¥˜¹…µ”¥¸Õ¹¥Ù•ÉÍ”¹É•Ù¥•Ý}É•ÅÕ¥É•…¹¹…µ”¹½Ð¥¸½Ù•ÉÉ¥‘•Ì(€€€€¤(€€€¥˜Õ¹É•Í½±Ù•è(€€€€€€€É…¥Í”Y…±Õ•ÉÉ½È (€€€€€€€€€€€€‰µ•¡…¹¥ÍÑ¥ŒÁÉ½™¥±”É•ÅÕ¥É•‰•™½É”ÍÑÉÕÑÕÉ…°Í½É¥¹œ½Í¥µÕ±…Ñ¥½¸è€ˆ(€€€€€€€€€€€˜‰íÕ¹É•Í½±Ù•‘ôˆ(€€€€€€€€¤((€€€…É‘Ìè±¥ÍÑmMÑÉÕÑÕÉ…±…É‘AÉ½™¥±•t€ômt(€€€™½È¹…µ”¥¸µ…¥¹‰½…É‘}¹…µ•Ìè(€€€€€€€½Ù•ÉÉ¥‘”€ô½Ù•ÉÉ¥‘•Ì¹•Ð¡¹…µ”¤(€€€€€€€¥˜½Ù•ÉÉ¥‘”¥Ì¹½Ð9½¹”è(€€€€€€€€€€€¥˜½Ù•ÉÉ¥‘”¹½É…±•}¹…µ”€„ô¹…µ”è(€€€€€€€€€€€€€€€É…¥Í”Y…±Õ•ÉÉ½È¡˜‰ÁÉ½™¥±”½Ù•ÉÉ¥‘”¹…µ”µ¥Íµ…Ñ ™½Èí¹…µ”…Éôˆ¤(€€€€€€€€€€€…É‘Ì¹…ÁÁ•¹¡½Ù•ÉÉ¥‘”¤(€€€€€€€•±Í”è(€€€€€€€€€€€ÑÉäè(€€€€€€€€€€€€€€€…É‘Ì¹…ÁÁ•¹¡‰å}¹…µ•m¹…µ•t¹…É¤(€€€€€€€€€€€•á•ÁÐ-•åÉÉ½È…Ì•áŒè(€€€€€€€€€€€€€€€É…¥Í”Y…±Õ•ÉÉ½È¡˜‰µ¥ÍÍ¥¹œÍÑÉÕÑÕÉ…°ÁÉ½™¥±”™½Èí¹…µ”…Éôˆ¤™É½´•áŒ((€€€µ¥ÍÍ¥¹}½µµ…¹‘•ÉÌ€ôÍ½ÉÑ•¡Í•Ð¡I=M!%}=559IL¤€´Í•Ð¡‰å}¹…µ”¤¤(€€€¥˜µ¥ÍÍ¥¹}½µµ…¹‘•ÉÌè(€€€€€€€É…¥Í”Y…±Õ•ÉÉ½È¡˜‰½µµ…¹‘•ÈÍÑÉÕÑÕÉ…°ÁÉ½™¥±”µ¥ÍÍ¥¹œèíµ¥ÍÍ¥¹}½µµ…¹‘•ÉÍôˆ¤(€€€™½È½µµ…¹‘•È¥¸I=M!%}=559ILè(€€€€€€€¥˜Õ¹¥Ù•ÉÍ”¹…Ù…¥±…‰±•}ÅÕ…¹Ñ¥Ñ¥•Ì¹•Ð¡½µµ…¹‘•È°€À¤€ð€Äè(€€€€€€€€€€€É…¥Í”Y…±Õ•ÉÉ½È (€€€€€€€€€€€€€€€˜‰½µµ…¹‘•È¥Ì¹½ÐÁ¡åÍ¥…±±ä…Ù…¥±…‰±”Ý¥Ñ -½ÉÙ½±‰Õ¥±Ðèí½µµ…¹‘•Éôˆ(€€€€€€€€€€€€¤(€€€€€€€…É‘Ì¹…ÁÁ•¹¡‰å}¹…µ•m½µµ…¹‘•Ét¹…É¤((€€€‘•­}¡…Í €ôÍ¡„ÈÔÙ}Ù…±Õ” (€€€€€€€ì(€€€€€€€€€€€€‰µ½‘”ˆè€‰™É•Í¡}É•‰Õ¥±ˆ°(€€€€€€€€€€€€‰½µµ…¹‘•ÉÌˆèI=M!%}=559IL°(€€€€€€€€€€€€‰µ…¥¹‰½…ÉˆèÍ½ÉÑ•¡½Õ¹ÑÌ¹¥Ñ•µÌ ¤¤°(€€€€€€€€€€€€‰ÁÉ½™¥±•}½Ù•ÉÉ¥‘•}¹…µ•ÌˆèÍ½ÉÑ•¡½Ù•ÉÉ¥‘•Ì¤°(€€€€€€€€€€€€‰ÕÉÉ•¹Ñ}‘É¥Ù•}ÉÕ¹Ñ¥µ•}Í¡„ÈÔØˆèÕ¹¥Ù•ÉÍ”¹ÉÕ¹Ñ¥µ•}Í¡„ÈÔØ°(€€€€€€€ô(€€€€¤(€€€Í…™•}±…‰•°€ô€ˆˆ¹©½¥¸ (€€€€€€€ ™½È ¥¸Ù…É¥…¹Ñ}±…‰•°¹…Í•™½± ¤¥˜ ¹¥Í…±¹Õ´ ¤½È ¥¸ìˆ´ˆ°€‰|‰ô(€€€€¥lèÌÉt(€€€‘•­}¥€ô˜‰íIM!}I=M!%}AI%aõíÍ…™•}±…‰•°½È‘•­}¡…Í¡lèÄÉuôµí‘•­}¡…Í¡lèÄÁuôˆ(€€€É•ÑÕÉ¸MÑÉÕÑÕÉ…±•­AÉ½™¥±” (€€€€€€€‘•­}¥õ‘•­}¥°(€€€€€€€‘•­}¡…Í õ‘•­}¡…Í °(€€€€€€€½µµ…¹‘•É}¹…µ•ÌõI=M!%}=559IL°(€€€€€€€…É‘ÌõÑÕÁ±”¡…É‘Ì¤°(€€€€€€€½µµ…¹‘•É}‰…Í•}½ÍÑÌõì(€€€€€€€€€€€€‰%Í¡…¤°=©ÕÑ…¤É…½¹ÍÁ•…­•Èˆè€Ð¸À°(€€€€€€€€€€€€‰I½É…­ °M½¸½˜I½¡…¡ ˆè€À¸À°(€€€€€€€ô°(€€€€€€€½µµ…¹‘•É}‰…Í•}Á½Ý•Èõì(€€€€€€€€€€€€‰%Í¡…¤°=©ÕÑ…¤É…½¹ÍÁ•…­•Èˆè€Ä¸À°(€€€€€€€€€€€€‰I½É…­ °M½¸½˜I½¡…¡ ˆè€À¸À°(€€€€€€€ô°(€€€€€€€½µµ…¹‘•É}ÍÑÉ…Ñ•äô‰É½Í¡…¤ˆ°(€€€€€€€‘…Ñ…}Í¹…ÁÍ¡½Ñ}¡…Í õÕ¹¥Ù•ÉÍ”¹ÉÕ¹Ñ¥µ•}Í¡„ÈÔØ°(€€€€¤(()‘•˜}ÅÕ…±¥Ñå}ÁÉ½©•Ñ¥½¸¡É½Üè5…ÁÁ¥¹mÍÑÈ°½‰©•Ñt¤€´ø‘¥ÑmÍÑÈ°½‰©•Ñtè(€€€É•ÑÕÉ¸ì(€€€€€€€€‰…É‘}¥ˆèÉ½Ü¹•Ð ‰…É‘}¥ˆ¤°(€€€€€€€€‰½É…±•}¹…µ”ˆèÉ½Ü¹•Ð ‰½É…±•}¹…µ”ˆ¤°(€€€€€€€€‰½±½É}¥‘•¹Ñ¥ÑäˆèÉ½Ü¹•Ð ‰½±½É}¥‘•¹Ñ¥Ñäˆ¤°(€€€€€€€€‰½µµ…¹‘•É}±•…°ˆèÉ½Ü¹•Ð ‰½µµ…¹‘•É}±•…°ˆ¤°(€€€€€€€€‰µ…¹…}Ù…±Õ”ˆèÉ½Ü¹•Ð ‰µ…¹…}Ù…±Õ”ˆ¤°(€€€€€€€€‰ÑåÁ•}±¥¹”ˆèÉ½Ü¹•Ð ‰ÑåÁ•}±¥¹”ˆ¤°(€€€ô(()‘•˜™É•Í¡}ÅÕ…±¥Ñå}™¥¹•ÉÁÉ¥¹Ð¡ÉÕ¹Ñ¥µ”è5…ÁÁ¥¹mÍÑÈ°¹åt¤€´øÍÑÈè(€€€Õ¹¥Ù•ÉÍ”€ôÉÕ¹Ñ¥µ”¹•Ð ‰…¹‘¥‘…Ñ•}Õ¹¥Ù•ÉÍ”ˆ°íô¤(€€€¥˜¹½Ð¥Í¥¹ÍÑ…¹”¡Õ¹¥Ù•ÉÍ”°‘¥Ð¤½È¹½Ð¥Í¥¹ÍÑ…¹”¡Õ¹¥Ù•ÉÍ”¹•Ð ‰…¹‘¥‘…Ñ•Ìˆ¤°±¥ÍÐ¤è(€€€€€€€É…¥Í”É•Í¡I•‰Õ¥±‘…Ñ…ÉÉ½È ‰…¹‘¥‘…Ñ”Õ¹¥Ù•ÉÍ”µ¥ÍÍ¥¹œÝ¡¥±”‰Õ¥±‘¥¹œ‰¥…Ì™¥¹•ÉÁÉ¥¹Ðˆ¤(€€€É½ÝÌ€ôl(€€€€€€€}ÅÕ…±¥Ñå}ÁÉ½©•Ñ¥½¸¡…ÍÐ¡5…ÁÁ¥¹mÍÑÈ°½‰©•Ñt°É½Ü¤¤(€€€€€€€™½ÈÉ½Ü¥¸…ÍÐ¡±¥ÍÑm½‰©•Ñt°Õ¹¥Ù•ÉÍ•l‰…¹‘¥‘…Ñ•Ì‰t¤(€€€€€€€¥˜¥Í¥¹ÍÑ…¹”¡É½Ü°‘¥Ð¤(€€€t(€€€É½ÝÌ¹Í½ÉÐ¡­•äõ±…µ‰‘„É½ÜèÍÑÈ¡É½Ýl‰…É‘}¥‰t¤¤(€€€É•ÑÕÉ¸Í¡„ÈÔÙ}ÉÕ¹}Ù…±Õ”¡É½ÝÌ¤(()‘•˜ÉÕ¹}¬É}‰¥…Í}ÍÕ¥Ñ”¡É½½ÐèÍÑÈðA…Ñ ¤€´ø‘¥ÑmÍÑÈ°½‰©•Ñtè(€€€€ˆˆ‰á•ÕÑ”,Èµ¥¹Ù…É¥…¹”¡•­Ì……¥¹ÍÐÑ¡”ÕÉÉ•¹ÐÉÕ¹Ñ¥µ”ÁÉ½©•Ñ¥½¸¸ˆˆˆ((€€€‰…Í•±¥¹”€ô±½…‘}™É•Í¡}É•‰Õ¥±‘}ÉÕ¹Ñ¥µ”¡É½½Ð¤(€€€‰…Í•±¥¹•}™À€ô™É•Í¡}ÅÕ…±¥Ñå}™¥¹•ÉÁÉ¥¹Ð¡‰…Í•±¥¹”¤(€€€Õ¹¥Ù•ÉÍ”€ô…ÍÐ¡‘¥ÑmÍÑÈ°¹åt°‰…Í•±¥¹•l‰…¹‘¥‘…Ñ•}Õ¹¥Ù•ÉÍ”‰t¤(€€€É½ÝÌ€ô…ÍÐ¡±¥ÍÑm‘¥ÑmÍÑÈ°¹åut°Õ¹¥Ù•ÉÍ•l‰…¹‘¥‘…Ñ•Ì‰t¤((€€€‘•˜½Ù•É±…å}™¥¹•ÉÁÉ¥¹Ð¡­•äèÍÑÈ°Ù…±Õ”è½‰©•Ð¤€´øÍÑÈè(€€€€€€€…±Ñ•É•€ô½Áä¹‘••Á½Áä¡‰…Í•±¥¹”¤(€€€€€€€…±Ñ•É•‘}É½ÝÌ€ô…ÍÐ (€€€€€€€€€€€±¥ÍÑm‘¥ÑmÍÑÈ°¹åut°(€€€€€€€€€€€…ÍÐ¡‘¥ÑmÍÑÈ°¹åt°…±Ñ•É•‘l‰…¹‘¥‘…Ñ•}Õ¹¥Ù•ÉÍ”‰t¥l‰…¹‘¥‘…Ñ•Ì‰t°(€€€€€€€€¤(€€€€€€€™½ÈÉ½Ü¥¸…±Ñ•É•‘}É½ÝÌè(€€€€€€€€€€€É½Ým­•åt€ôÙ…±Õ”(€€€€€€€É•ÑÕÉ¸™É•Í¡}ÅÕ…±¥Ñå}™¥¹•ÉÁÉ¥¹Ð¡…±Ñ•É•¤((€€€Ñ•ÍÑÌ€ôì(€€€€€€€€‰}ÕÉÉ•¹Ñ}‘•­}‰±¥¹‘¹•ÍÌˆè½Ù•É±…å}™¥¹•ÉÁÉ¥¹Ð ‰ÕÉÉ•¹Ñ}‘•­}µ•µ‰•Èˆ°QÉÕ”¤(€€€€€€€€ôô‰…Í•±¥¹•}™À°(€€€€€€€€‰	}¡¥ÍÑ½É¥…±}ÕÑ}‰±¥¹‘¹•ÍÌˆè½Ù•É±…å}™¥¹•ÉÁÉ¥¹Ð ‰¡¥ÍÑ½É¥…±}ÕÐˆ°QÉÕ”¤€ôô‰…Í•±¥¹•}™À°(€€€€€€€€‰}ÁÉ½Ñ•Ñ•‘}…É‘}‰±¥¹‘¹•ÍÌˆè½Ù•É±…å}™¥¹•ÉÁÉ¥¹Ð ‰ÁÉ½Ñ•Ñ•ˆ°QÉÕ”¤€ôô‰…Í•±¥¹•}™À°(€€€ô((€€€…±±½…Ñ¥½¹}¡…¹•€ô½Áä¹‘••Á½Áä¡‰…Í•±¥¹”¤(€€€…±±½…Ñ¥½¹}É½ÝÌ€ô…ÍÐ (€€€€€€€±¥ÍÑm‘¥ÑmÍÑÈ°¹åut°(€€€€€€€…ÍÐ¡‘¥ÑmÍÑÈ°¹åt°…±±½…Ñ¥½¹}¡…¹•‘l‰…¹‘¥‘…Ñ•}Õ¹¥Ù•ÉÍ”‰t¥l‰…¹‘¥‘…Ñ•Ì‰t°(€€€€¤(€€€™½ÈÉ½Ü¥¸…±±½…Ñ¥½¹}É½ÝÍlèÈÁtè(€€€€€€€Á¡åÍ¥…°€ôÉ½Ü¹•Ð ‰Á¡åÍ¥…°ˆ¤(€€€€€€€¥˜¥Í¥¹ÍÑ…¹”¡Á¡åÍ¥…°°‘¥Ð¤è(€€€€€€€€€€€Á¡åÍ¥…±l‰…±±½…Ñ•‘}Ñ½}­½ÉÙ½±‰t€ô€ää(€€€€€€€€€€€Á¡åÍ¥…±l‰…±±½…Ñ•‘}Ñ½}ÕÉÉ•¹Ñ}É½Í¡…¤‰t€ô€ää(€€€Ñ•ÍÑÍl‰}…±±½…Ñ¥½¹}‰±¥¹‘¹•ÍÍ}…Í}ÅÕ…±¥Ñå}ÁÉ¥½È‰t€ô€ (€€€€€€€™É•Í¡}ÅÕ…±¥Ñå}™¥¹•ÉÁÉ¥¹Ð¡…±±½…Ñ¥½¹}¡…¹•¤€ôô‰…Í•±¥¹•}™À(€€€€¤((€€€½Ù•É…•}¡…¹•€ô½Áä¹‘••Á½Áä¡‰…Í•±¥¹”¤(€€€½Ù•É…•}É½ÝÌ€ô…ÍÐ (€€€€€€€±¥ÍÑm‘¥ÑmÍÑÈ°¹åut°(€€€€€€€…ÍÐ¡‘¥ÑmÍÑÈ°¹åt°½Ù•É…•}¡…¹•‘l‰…¹‘¥‘…Ñ•}Õ¹¥Ù•ÉÍ”‰t¥l‰…¹‘¥‘…Ñ•Ì‰t°(€€€€¤(€€€‰•™½É•}¹…µ•Ì€ôíÍÑÈ¡É½Ýl‰½É…±•}¹…µ”‰t¤™½ÈÉ½Ü¥¸½Ù•É…•}É½ÝÍô(€€€½Ù•É…”€ô½Ù•É…•}É½ÝÍlÁt¹•Ð ‰½Ù•É…”ˆ¤(€€€¥˜¥Í¥¹ÍÑ…¹”¡½Ù•É…”°‘¥Ð¤è(€€€€€€€½Ù•É…•l‰ÍÑ…ÑÕÌ‰t€ô€‰MQIUQUI11e}U95=1ˆ(€€€€€€€½Ù•É…•l‰É•ÅÕ¥É•Í}µ½‘•±}É•Ù¥•Ü‰t€ôQÉÕ”(€€€…™Ñ•É}¹…µ•Ì€ôíÍÑÈ¡É½Ýl‰½É…±•}¹…µ”‰t¤™½ÈÉ½Ü¥¸½Ù•É…•}É½ÝÍô(€€€Ñ•ÍÑÍl‰}ÍÑÉÕÑÕÉ…±}½Ù•É…•}¹•ÕÑÉ…±¥Ñä‰t€ô€ (€€€€€€€‰•™½É•}¹…µ•Ì€ôô…™Ñ•É}¹…µ•Ì…¹™É•Í¡}ÅÕ…±¥Ñå}™¥¹•ÉÁÉ¥¹Ð¡½Ù•É…•}¡…¹•¤€ôô‰…Í•±¥¹•}™À(€€€€¤((€€€É•¥ÍÑÉä€ô‰…Í•±¥¹”¹•Ð ‰½ÁÁ½¹•¹Ñ}É•¥ÍÑÉäˆ°íô¤(€€€½ÁÁ½¹•¹Ñ}É½ÝÌ€ô€ (€€€€€€€É•¥ÍÑÉä¹•Ð ‰½ÁÁ½¹•¹ÑÌˆ°mt¤¥˜¥Í¥¹ÍÑ…¹”¡É•¥ÍÑÉä°‘¥Ð¤•±Í”mt(€€€€¤(€€€Íå¹Ñ¡•Ñ¥}É½ÝÌ€ôl(€€€€€€€É½Ü(€€€€€€€™½ÈÉ½Ü¥¸½ÁÁ½¹•¹Ñ}É½ÝÌ(€€€€€€€¥˜¥Í¥¹ÍÑ…¹”¡É½Ü°‘¥Ð¤…¹€‰Íå¹Ñ¡•Ñ¥Œˆ¥¸ÍÑÈ¡É½Ü¹•Ð ‰‘•­}Í½ÕÉ•}ÑåÁ”ˆ°€ˆˆ¤¤(€€€t(€€€Ñ•ÍÑÍl‰}Íå¹Ñ¡•Ñ¥}½ÁÁ½¹•¹Ñ}¹•Ù•É}½‰Í•ÉÙ•‰t€ô‰½½°¡Íå¹Ñ¡•Ñ¥}É½ÝÌ¤…¹…±° (€€€€€€€É½Ü¹•Ð ‰‘•­}ÍÑ…ÑÕÌˆ¤€„ô€‰½‰Í•ÉÙ•ˆ…¹É½Ü¹•Ð ‰™Õ±±}±¥ÍÑ}­¹½Ý¸ˆ¤¥Ì…±Í”(€€€€€€€™½ÈÉ½Ü¥¸Íå¹Ñ¡•Ñ¥}É½ÝÌ(€€€€¤((€€€‰¥…Ì€ô‰…Í•±¥¹”¹•Ð ‰‰¥…Í}Á½±¥äˆ°íô¤(€€€Ñ•ÍÑÍl‰}½¹ÑÉ½±}Õ¹…Ù…¥±…‰±•}‘ÕÉ¥¹}¥¹‘•Á•¹‘•¹Ñ}ÍÑ…”‰t€ô€ (€€€€€€€¥Í¥¹ÍÑ…¹”¡‰¥…Ì°‘¥Ð¤(€€€€€€€…¹‰¥…Ì¹•Ð ‰½¹ÑÉ½±}‘•­}Ù¥Í¥‰±•}¥¹}¥¹‘•Á•¹‘•¹Ñ}ÍÑ…”ˆ¤¥Ì…±Í”(€€€€€€€…¹…±° ‰ÕÉÉ•¹Ñ}‘•­}…É‘Ìˆ¹½Ð¥¸É½Ü™½ÈÉ½Ü¥¸É½ÝÌ¤(€€€€¤(€€€É•ÑÕÉ¸ì(€€€€€€€€‰ÍÑ…ÑÕÌˆè€‰AMLˆ¥˜…±°¡Ñ•ÍÑÌ¹Ù…±Õ•Ì ¤¤•±Í”€‰%0ˆ°(€€€€€€€€‰Ñ•ÍÑÌˆèÑ•ÍÑÌ°(€€€€€€€€‰ÅÕ…±¥Ñå}™¥¹•ÉÁÉ¥¹Ðˆè‰…Í•±¥¹•}™À°(€€€€€€€€‰…¹‘¥‘…Ñ•}½Õ¹Ðˆè±•¸¡É½ÝÌ¤°(€€€ô(