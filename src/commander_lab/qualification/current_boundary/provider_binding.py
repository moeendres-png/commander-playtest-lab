"""Provider evidence binding: which candidate head an artifact actually consumed.

Qualification evidence is only valid for the exact candidate build it observed.
A Forge artifact produced against one Rules Core and one bridge revision says
nothing about a later pull request that rewrites either of them. Relabelling
such an artifact with the newer head is the specific failure this module exists
to prevent, because nothing else in the pipeline would catch it: the JSON is
well-formed, the row outcomes are unchanged, and the denominators still add up.

The observed identity is already recorded per artifact in ``runtime_identity``.
This module reads those recorded values and compares them against the heads a
candidate is currently published at, producing one disposition per artifact:

``BOUND_TO_CONSUMED_HEAD``
    The artifact's recorded candidate identities are the heads it was produced
    against, so it is current for them.

``STALE_FOR_PUBLISHED_HEAD``
    A newer candidate head is published and it touches a surface the artifact
    depends on. The artifact is not wrong, but it does not speak for the newer
    head and must be regenerated there before it can be cited.

``BOUND_NO_SUPERSEDED_HEAD``
    The artifact is bound to a head that is not superseded by anything this
    module knows about.

Deliberate non-goals:

* This never relabels an artifact. It reports the recorded head verbatim and
  derives staleness from it; changing what an artifact claims to have consumed
  is an evidence-integrity violation, not a bookkeeping task.
* It never decides whether a candidate head is *correct*. A head being current
  is a fact about the repository; whether it passes is a qualification result.
* A Rules Core change is treated as disqualifying for the artifacts that
  consumed the previous one, because the Rules Core is the sole authority for
  legal actions. A bridge-only change disqualifies the artifacts that consumed
  the previous bridge, for the same reason.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BOUND = "BOUND_TO_CONSUMED_HEAD"
STALE = "STALE_FOR_PUBLISHED_HEAD"
UNSUPERSEDED = "BOUND_NO_SUPERSEDED_HEAD"

# The identity fields an artifact records about the candidate it actually ran
# against. ``rules_core``/``adapter`` are the two that decide disqualification:
# the Rules Core is the sole legality authority and the bridge is what the Lab
# actually spoke to.
_RULES_CORE_FIELD = "engine_candidate_commit"
_ADAPTER_FIELD = "adapter_commit"
_RUNNER_FIELD = "runner_commit"


def _surface_touched(change: dict[str, Any], surface: str) -> bool:
    """Whether a published candidate change touches ``surface``.

    A change is only disqualifying when it actually touches the surface the
    artifact consumed. Unrelated files in the same pull request must not
    invalidate evidence, otherwise a documentation-only change would discard a
    real run for no reason.
    """
    if surface == "rules_core":
        patterns = change.get("rules_core_paths") or []
    elif surface == "adapter":
        patterns = change.get("adapter_paths") or []
    else:
        patterns = change.get("other_paths") or []
    return any(_path_matches(path, patterns) for path in change.get("paths") or [])


def _path_matches(path: str, patterns: list[str]) -> bool:
    if not patterns:
        return False
    normalised = path.replace("\\", "/")
    for pattern in patterns:
        if not pattern:
            continue
        # A directory prefix disables its whole subtree, which is how a module
        # such as forge-game/src/main/java/forge/game is expressed.
        if normalised.startswith(pattern.rstrip("/") + "/") or normalised == pattern:
            return True
        # A bare module or filename fragment matches anywhere in the path.
        if len(pattern) > 4 and "/" not in pattern and pattern in normalised:
            return True
    return False


def assess_artifact_binding(
    artifact: dict[str, Any], published: list[dict[str, Any]]
) -> dict[str, Any]:
    """Classify one artifact against every published candidate change.

    ``published`` is a list of candidate changes, newest first, each carrying
    ``head``, ``paths``, and the per-surface path groupings. Only changes that
    descend from the head the artifact consumed can supersede it, so a change
    published from an unrelated branch is ignored.
    """
    identity = artifact.get("runtime_identity") or {}
    consumed_rules_core = str(identity.get(_RULES_CORE_FIELD) or "")
    consumed_adapter = str(identity.get(_ADAPTER_FIELD) or "")
    consumed_runner = str(identity.get(_RUNNER_FIELD) or "")

    if not consumed_rules_core and not consumed_adapter:
        return {
            "disposition": UNSUPERSEDED,
            "reason": "the artifact records no candidate identity, so no head can supersede it",
        }

    superseding: list[dict[str, Any]] = []
    for change in published:
        # A candidate is forked along two independent lineages, so a single
        # "base" cannot describe it: a pull request may be published on top of
        # a bridge head while rewriting a Rules Core that descends from a
        # different fork point. Each surface therefore declares the prior head
        # it was built on, and only that surface can supersede.
        # A change supersedes a surface when it touches that surface and the
        # artifact did NOT already run code containing it.
        #
        # This is deliberately not an ancestry test against the artifact's own
        # commit. Candidates are forked along parallel lineages, so a change can
        # rewrite the same module without ever descending from the commit an
        # artifact ran: XMage's bridge lives in this repository, and a rewrite
        # merged to main is not an ancestor of the workstream commit that
        # produced the committed evidence. Comparing bases would silently treat
        # that rewrite as irrelevant, which is exactly the failure this guard
        # exists to prevent.
        #
        # ``contained_in`` is the set of heads already known to include the
        # change. When the artifact's consumed commit is one of them, the run
        # already exercised the change and the artifact is not stale.
        contained_in = {str(h) for h in change.get("contained_in") or []}
        for surface, field, consumed in (
            ("rules_core", _RULES_CORE_FIELD, consumed_rules_core),
            ("adapter", _ADAPTER_FIELD, consumed_adapter),
        ):
            if not consumed:
                continue
            if consumed in contained_in or consumed == str(change.get("head") or ""):
                continue
            if not _surface_touched(change, surface):
                continue
            superseding.append(
                {
                    "head": change.get("head"),
                    "surface": surface,
                    "consumed_head": consumed,
                    "field": field,
                }
            )

    if not superseding:
        return {
            "disposition": BOUND,
            "reason": "no published candidate change touches a surface this artifact consumed",
            "consumed": {
                _RULES_CORE_FIELD: consumed_rules_core,
                _ADAPTER_FIELD: consumed_adapter,
                _RUNNER_FIELD: consumed_runner,
            },
        }

    return {
        "disposition": STALE,
        "reason": (
            "a published candidate change rewrites a surface this artifact consumed, so the "
            "artifact does not speak for that head and must be regenerated there before it is "
            "cited; relabelling it with the newer head would be a false credit"
        ),
        "consumed": {
            _RULES_CORE_FIELD: consumed_rules_core,
            _ADAPTER_FIELD: consumed_adapter,
            _RUNNER_FIELD: consumed_runner,
        },
        "superseding_changes": superseding,
        "required_action": (
            "re-execute this qualification on the actually consumed candidate head and regenerate "
            "the artifact; do not relabel, re-point or copy the current run forward"
        ),
    }


def assess_provider_bindings(
    artifacts: dict[str, dict[str, Any]], published: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    """Classify every artifact of every candidate against that candidate's heads."""
    bindings: dict[str, Any] = {}
    for candidate, by_name in sorted(artifacts.items()):
        changes = published.get(candidate) or []
        bindings[candidate] = {
            name: {"artifact": name, **assess_artifact_binding(artifact, changes)}
            for name, artifact in sorted(by_name.items())
        }
    return {
        "schema_version": "commander-lab.provider-evidence-binding/1.0.0",
        "bindings": bindings,
        "counts": {
            key: sum(
                1
                for candidate in bindings.values()
                for entry in candidate.values()
                if entry["disposition"] == key
            )
            for key in (BOUND, STALE, UNSUPERSEDED)
        },
        "honesty_note": (
            "A disposition describes the candidate identity an artifact actually consumed. It is "
            "not a pass: STALE artifacts remain valid evidence of what they did consume, and the "
            "gate they feed is unchanged until the artifact is regenerated on the new head."
        ),
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
