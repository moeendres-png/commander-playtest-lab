from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from commander_lab.models.provenance import ProvenanceGraph
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
            [item.source_id for item in graph.sources]
            + [item.artifact_id for item in graph.artifacts]
            + [item.derived_id for item in graph.derived_data]
            + [item.transformation_id for item in graph.transformations]
        )

    def validate(self, graph: ProvenanceGraph) -> None:
        ids = self.all_ids(graph)
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        if duplicates:
            raise ProvenanceError(f"duplicate provenance ids: {duplicates}")

        known = set(ids)
        edges: dict[str, set[str]] = {item: set() for item in known}
        for source in graph.sources:
            for parent in source.derived_from:
                if parent not in known:
                    raise ProvenanceError(f"missing source parent: {parent}")
                edges[source.source_id].add(parent)
        for artifact in graph.artifacts:
            for parent in artifact.derived_from:
                if parent not in known:
                    raise ProvenanceError(f"missing artifact parent: {parent}")
                edges[artifact.artifact_id].add(parent)
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
            for reference in (*citation.source_ids, *citation.derived_ids):
                if reference not in known:
                    raise ProvenanceError(f"citation references unknown record: {reference}")

    def trace(self, record_id: str) -> dict[str, Any]:
        graph = self.load()
        self.validate(graph)
        by_id = (
            {item.source_id: item for item in graph.sources}
            | {item.artifact_id: item for item in graph.artifacts}
            | {item.derived_id: item for item in graph.derived_data}
            | {item.transformation_id: item for item in graph.transformations}
        )
        if record_id not in by_id:
            raise ProvenanceError(f"unknown record: {record_id}")

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def walk(item_id: str, depth: int) -> None:
            if item_id in seen:
                return
            seen.add(item_id)
            obj = by_id[item_id]
            parents = getattr(obj, "derived_from", ()) or getattr(obj, "input_ids", ())
            rows.append(
                {
                    "record_id": item_id,
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
        return [item.model_dump(mode="json") for item in graph.supersessions]

    def verify_source_hash(
        self,
        source_id: str,
        candidate_path: str | Path | None = None,
    ) -> dict[str, Any]:
        graph = self.load()
        source = next((item for item in graph.sources if item.source_id == source_id), None)
        if source is None:
            raise ProvenanceError(f"unknown source: {source_id}")
        path = (
            Path(candidate_path)
            if candidate_path
            else self.root / (source.url_or_drive_id or "")
        )
        if not path.exists():
            return {
                "source_id": source_id,
                "status": "missing",
                "expected_hash": source.content_hash,
                "actual_hash": None,
            }
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        return {
            "source_id": source_id,
            "status": "match" if actual == source.content_hash else "changed",
            "expected_hash": source.content_hash,
            "actual_hash": actual,
            "path": str(path),
        }

    def audit_claims(self) -> dict[str, Any]:
        graph = self.load()
        known_claims = {item.claim_id for item in graph.citations}
        claims_path = self.base / "claims.json"
        claims = (
            json.loads(claims_path.read_text(encoding="utf-8"))
            if claims_path.exists()
            else []
        )
        missing = [
            item
            for item in claims
            if item.get("claim_id") not in known_claims
            or item.get("claim_kind") not in {"source_fact", "model_output", "inference"}
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
