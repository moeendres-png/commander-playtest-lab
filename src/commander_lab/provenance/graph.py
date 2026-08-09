from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from commander_lab.models.provenance import (
    ArtifactRecord,
    CitationRecord,
    DerivedDataRecord,
    ProvenanceGraph,
    SourceRecord,
    SourceType,
    SupersessionRecord,
    VerificationStatus,
)
from commander_lab.storage.hashing import sha256_value


class ProvenanceError(RuntimeError):
    pass


class ProvenanceStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.base = self.root / "data" / "provenance"
        self.base.mkdir(parents=True, exist_ok=True)
        self.path = self.base / "provenance_graph.json"

    def load(self) -> ProvenanceGraph:
        if not self.path.exists():
            return ProvenanceGraph(graph_id="commander-playtest-lab")
        return ProvenanceGraph.model_validate_json(self.path.read_text(encoding="utf-8"))

    def save(self, graph: ProvenanceGraph) -> Path:
        self.validate(graph)
        self.path.write_text(
            json.dumps(
                graph.model_dump(mode="json"),
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return self.path

    @staticmethod
    def all_ids(graph: ProvenanceGraph) -> list[str]:
        return (
            [x.source_id for x in graph.sources]
            + [x.artifact_id for x in graph.artifacts]
            + [x.derived_id for x in graph.derived_data]
            + [x.transformation_id for x in graph.transformations]
        )

    def validate(self, graph: ProvenanceGraph) -> None:
        ids = self.all_ids(graph)
        duplicates = sorted({x for x in ids if ids.count(x) > 1})
        if duplicates:
            raise ProvenanceError(f"duplicate provenance ids: {duplicates}")
        known = set(ids)
        edges: dict[str, set[str]] = {x: set() for x in known}
        for source in graph.sources:
            for parent in source.derived_from:
                if parent not in known:
                    raise ProvenanceError(f"missing source parent: {parent}")
                edges[source.source_id].add(parent)
        for art in graph.artifacts:
            for parent in art.derived_from:
                if parent not in known:
                    raise ProvenanceError(f"missing artifact parent: {parent}")
                edges[art.artifact_id].add(parent)
        for item in graph.derived_data:
            for parent in item.derived_from:
                if parent not in known:
                    raise ProvenanceError(f"missing derived parent: {parent}")
                edges[item.derived_id].add(parent)

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ProvenanceError(f"circular derivation at {node}")
            if node in visited:
                return
            visiting.add(node)
            for parent in edges[node]:
                visit(parent)
            visiting.remove(node)
            visited.add(node)

        for node in sorted(edges):
            visit(node)
        for link in graph.supersessions:
            if link.old_id not in known or link.new_id not in known:
                raise ProvenanceError("supersession references unknown record")
        for citation in graph.citations:
            for ref in (*citation.source_ids, *citation.derived_ids):
                if ref not in known:
                    raise ProvenanceError(f"citation references unknown record: {ref}")

    def trace(self, record_id: str) -> dict[str, Any]:
        graph = self.load()
        self.validate(graph)
        by_id = (
            {x.source_id: x for x in graph.sources}
            | {x.artifact_id: x for x in graph.artifacts}
            | {x.derived_id: x for x in graph.derived_data}
            | {x.transformation_id: x for x in graph.transformations}
        )
        if record_id not in by_id:
            raise ProvenanceError(f"unknown record: {record_id}")
        rows = []
        seen = set()

        def walk(rid: str, depth: int) -> None:
            if rid in seen:
                return
            seen.add(rid)
            obj = by_id[rid]
            parents = getattr(obj, "derived_from", ()) or getattr(obj, "input_ids", ())
            rows.append(
                {
                    "record_id": rid,
                    "record_type": type(obj).__name__,
                    "depth": depth,
                    "record": obj.model_dump(mode="json"),
                }
            )
            for parent in parents:
                walk(parent, depth + 1)

        walk(record_id, 0)
        return {
            "record_id": record_id,
            "lineage": rows,
            "lineage_hash": sha256_value(rows),
        }

    def recommendation_sources(self, recommendation_id: str) -> dict[str, Any]:
        return self.trace(recommendation_id)

    def list_superseded(self) -> list[dict[str, Any]]:
        graph = self.load()
        return [x.model_dump(mode="json") for x in graph.supersessions]

    def verify_source_hash(
        self,
        source_id: str,
        candidate_path: str | Path | None = None,
    ) -> dict[str, Any]:
        graph = self.load()
        match = next((x for x in graph.sources if x.source_id == source_id), None)
        if match is None:
            raise ProvenanceError(f"unknown source: {source_id}")
        path = Path(candidate_path) if candidate_path else self.root / (match.url_or_drive_id or "")
        if not path.exists():
            return {
                "source_id": source_id,
                "status": "missing",
                "expected_hash": match.content_hash,
                "actual_hash": None,
            }
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        return {
            "source_id": source_id,
            "status": "match" if actual == match.content_hash else "changed",
            "expected_hash": match.content_hash,
            "actual_hash": actual,
            "path": str(path),
        }

    def audit_claims(self) -> dict[str, Any]:
        graph = self.load()
        known_claims = {x.claim_id for x in graph.citations}
        claims_path = self.base / "claims.json"
        claims = json.loads(claims_path.read_text(encoding="utf-8")) if claims_path.exists() else []
        missing = [
            x
            for x in claims
            if x.get("claim_id") not in known_claims
            or x.get("claim_kind") not in {"source_fact", "model_output", "inference"}
        ]
        return {
            "claim_count": len(claims),
            "referenced_claim_count": len(claims) - len(missing),
            "unreferenced_claims": missing,
            "passed": not missing,
        }

    @staticmethod
    def hash_payload(payload: Any) -> str:
        return sha256_value(payload)
