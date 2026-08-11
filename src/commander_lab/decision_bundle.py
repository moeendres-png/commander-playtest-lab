from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DecisionBundle:
    """Compact reproducible evidence package for one deckbuilding decision.

    The bundle is descriptive only. Creating it never mutates a canonical deck, inventory,
    allocation, purchase list, or opponent-frequency model.
    """

    bundle_version: str
    baseline_identity: dict[str, Any]
    variant_identity: dict[str, Any]
    context_snapshot: dict[str, Any]
    physical_legal_validation: dict[str, Any]
    feature_confidence_summary: dict[str, Any]
    mana_impact: dict[str, Any]
    central_paired_result: dict[str, Any]
    worst_case_sensitivity_result: dict[str, Any]
    commander_denial_result: dict[str, Any]
    ablation_result: dict[str, Any]
    cache_provenance: dict[str, Any]
    simulation_counts: dict[str, Any]
    stopping_reason: str
    evidence_class: str
    known_limitations: tuple[str, ...]
    recommendation_status: str
    extra: dict[str, Any] = field(default_factory=dict)

    def payload(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def bundle_hash(self) -> str:
        raw = json.dumps(
            self.payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


def render_decision_bundle_markdown(bundle: DecisionBundle) -> str:
    payload = bundle.payload()
    lines = [
        "# Commander Playtest Lab - Decision Bundle",
        "",
        f"- Bundle hash: `{bundle.bundle_hash}`",
        f"- Evidence class: `{bundle.evidence_class}`",
        f"- Recommendation status: `{bundle.recommendation_status}`",
        f"- Stopping reason: {bundle.stopping_reason}",
        "",
    ]
    for title, key in (
        ("Baseline identity", "baseline_identity"),
        ("Variant identity", "variant_identity"),
        ("Context snapshot", "context_snapshot"),
        ("Physical / legal validation", "physical_legal_validation"),
        ("Feature confidence", "feature_confidence_summary"),
        ("Mana impact", "mana_impact"),
        ("Central paired result", "central_paired_result"),
        ("Worst-case / sensitivity", "worst_case_sensitivity_result"),
        ("Commander denial", "commander_denial_result"),
        ("Ablation", "ablation_result"),
        ("Cache provenance", "cache_provenance"),
        ("Simulation counts", "simulation_counts"),
    ):
        lines.extend(
            [
                f"## {title}",
                "",
                "```json",
                json.dumps(payload[key], indent=2, ensure_ascii=False, sort_keys=True),
                "```",
                "",
            ]
        )
    lines.extend(["## Known limitations", ""])
    lines.extend(f"- {item}" for item in bundle.known_limitations)
    lines.append("")
    return "\n".join(lines)


def write_decision_bundle(
    bundle: DecisionBundle,
    output_directory: str | Path,
    *,
    stem: str = "decision_bundle",
) -> dict[str, str]:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    payload = {"bundle_hash": bundle.bundle_hash, **bundle.payload()}
    json_path = output / f"{stem}.json"
    markdown_path = output / f"{stem}.md"
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_decision_bundle_markdown(bundle), encoding="utf-8")
    return {
        "bundle_hash": bundle.bundle_hash,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
