"""Measure commander visibility and counterfactual commander-tax impact (#1040 Item 1).

This measurement script inspects request dumps produced by ``scripts/pilot_request_corpus.py``
(such as ``tests/fixtures/pilot_real_requests/real_pod_v1.jsonl.gz`` or full dumps recorded
from real games) to quantify how visible commander state is to the pilot and whether
presenting commander tax in ``PilotActionView.mana_cost`` changes pilot decisions.

Counting rules:
- ``requests_total``: total number of decision requests across all input files.
- ``priority_requests``: requests with ``decision_class == "priority"``.
- ``requests_with_own_commander_damage``: requests where the actor's own commander has
  dealt > 0 damage to any opponent.
- ``requests_with_commander_damage_ge_14``: requests where any commander (own or opponent)
  has dealt >= 14 damage to any player.
- ``commander_zone_cast_options``: priority options whose ``source_object_id`` is in the
  actor's command zone.
- ``commander_zone_cast_options_taxed``: command zone cast options where the commander has
  ``casts_from_command >= 1`` according to the actor's ``commander_status``.
- ``requests_with_taxed_commander_option``: priority requests containing at least one taxed
  command zone cast option.
- ``answers_changed_by_tax``: priority requests whose answered key differs under the
  tax-visible pilot than under the same pilot with the tax hidden (the pilot before #1040).
- ``answers_changed_without_taxed_option``: negative control / wrong-reason check: requests
  where the answer changed even though no taxed commander cast was offered (must be 0).
- ``evidence``: source files, sorted seeds, and evidence classification.

Host-VM >=10-seed measurement:
To produce full-game dumps and run the >=10-seed measurement on the host VM:
    # Record full dumps for each seed (requires JVM and XMage bridge jar):
    for seed in $(seq 1 10); do
        python scripts/pilot_request_corpus.py record --all --jar <bridge-jar> --seeds $seed --out dump-$seed.jsonl.gz
    done
    # Measure across all dumps:
    python scripts/measure_commander_visibility.py dump-*.jsonl.gz --json visibility_results.json

Rules Authority note:
Since #1040 the pilot's view of a commander cast carries the tax (2 per earlier cast). The
counterfactual of this script is now the pilot with the tax hidden, a local subclass that
reports 0 earlier casts; the live pilot is the tax-visible side. No rules or pilot logic are
altered here; XMage remains the single authoritative rules engine for costs, legality, and
execution.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import importlib.util
import json
import sys
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol, cast

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))



class CorpusToolProtocol(Protocol):
    DEFAULT_CORPUS: Path

    def fresh_policy(self, seed: int) -> object: ...

    def answer_key(self, answer: Mapping[str, object]) -> str: ...


class DecidingPolicyProtocol(Protocol):
    def decide(self, request: dict[str, object]) -> dict[str, object]: ...


def _load_corpus_tool() -> CorpusToolProtocol:
    script = ROOT / "scripts" / "pilot_request_corpus.py"
    spec = importlib.util.spec_from_file_location("pilot_request_corpus_module", script)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {script}")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return cast(CorpusToolProtocol, tool)


def _build_tax_blind_policy(base_policy: object) -> DecidingPolicyProtocol:
    """The pilot as it was before #1040: a commander cast is priced without the tax."""
    base_class = type(base_policy)

    class TaxBlindPolicy(base_class):  # type: ignore[valid-type,misc]
        def _commander_casts(self, state: dict[str, object], name: str) -> int:
            return 0

    base_policy.__class__ = TaxBlindPolicy
    return cast(DecidingPolicyProtocol, base_policy)


@contextmanager
def _open_text_lines(path: Path) -> Iterator[Iterator[str]]:
    with path.open("rb") as f:
        magic = f.read(2)
    if magic == b"\x1f\x8b":
        with gzip.open(path, "rt", encoding="utf-8") as gz_handle:
            yield iter(gz_handle)
    else:
        with path.open("rt", encoding="utf-8") as txt_handle:
            yield iter(txt_handle)


def _read_records(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with _open_text_lines(path) as line_iter:
        for idx, line in enumerate(line_iter):
            line_str = line.strip()
            if not line_str:
                continue
            data = json.loads(line_str)
            if not isinstance(data, dict):
                continue
            if idx == 0 and "corpus_version" in data and "request" not in data:
                continue
            records.append(data)
    return records


def measure(paths: Sequence[Path]) -> dict[str, object]:
    """Deterministically measures commander visibility and tax impact across corpus files."""
    corpus_tool = _load_corpus_tool()

    requests_total = 0
    priority_requests = 0
    requests_with_own_commander_damage = 0
    requests_with_commander_damage_ge_14 = 0
    commander_zone_cast_options = 0
    commander_zone_cast_options_taxed = 0
    requests_with_taxed_commander_option = 0
    answers_changed_by_tax = 0
    answers_changed_without_taxed_option = 0

    all_seeds: set[int] = set()

    for path in paths:
        records = _read_records(path)
        for record in records:
            seed_raw = record.get("seed", 1)
            seed = int(seed_raw) if isinstance(seed_raw, (int, str)) else 1
            all_seeds.add(seed)

            req_raw = record.get("request")
            if not isinstance(req_raw, dict):
                continue
            request = req_raw
            requests_total += 1

            pilot_state_raw = request.get("pilot_state")
            pilot_state = pilot_state_raw if isinstance(pilot_state_raw, dict) else {}

            actor_id = str(pilot_state.get("actor_id") or request.get("actor_id") or "")
            players_raw = pilot_state.get("players")
            players = players_raw if isinstance(players_raw, list) else []
            for player in players:
                if isinstance(player, dict) and player.get("is_actor") is True:
                    actor_id = str(player.get("player_id") or actor_id)
                    break

            cmd_status_raw = pilot_state.get("commander_status")
            cmd_status = cmd_status_raw if isinstance(cmd_status_raw, list) else []

            has_own_commander_damage = False
            has_commander_damage_ge_14 = False

            for entry in cmd_status:
                if not isinstance(entry, dict):
                    continue
                owner_id = str(entry.get("owner_id") or "")
                is_own = bool(actor_id and owner_id == actor_id)
                dmg_list_raw = entry.get("commander_damage_to_player")
                dmg_list = dmg_list_raw if isinstance(dmg_list_raw, list) else []
                for dmg in dmg_list:
                    if not isinstance(dmg, dict):
                        continue
                    target_player = str(dmg.get("player_id") or "")
                    total = int(dmg.get("total", 0) or 0)
                    if is_own and target_player and target_player != actor_id and total > 0:
                        has_own_commander_damage = True
                    if total >= 14:
                        has_commander_damage_ge_14 = True

            if has_own_commander_damage:
                requests_with_own_commander_damage += 1
            if has_commander_damage_ge_14:
                requests_with_commander_damage_ge_14 += 1

            decision_class = str(request.get("decision_class") or "")
            if decision_class != "priority":
                continue

            priority_requests += 1

            command_ids: set[str] = set()
            command_names_by_id: dict[str, str] = {}
            for player in players:
                if isinstance(player, dict) and (
                    player.get("is_actor") is True or str(player.get("player_id")) == actor_id
                ):
                    cmd_zone_raw = player.get("command")
                    cmd_zone = cmd_zone_raw if isinstance(cmd_zone_raw, list) else []
                    for item in cmd_zone:
                        if isinstance(item, dict) and item.get("object_id"):
                            oid = str(item["object_id"])
                            command_ids.add(oid)
                            command_names_by_id[oid] = str(item.get("name") or "")
                    break

            casts_by_name: dict[str, int] = {}
            for entry in cmd_status:
                if isinstance(entry, dict) and str(entry.get("owner_id")) == actor_id:
                    name = str(entry.get("name") or "").casefold()
                    casts_by_name[name] = int(entry.get("casts_from_command", 0) or 0)

            req_has_taxed_option = False
            legal_options_raw = request.get("legal_options")
            legal_options = legal_options_raw if isinstance(legal_options_raw, list) else []
            for option in legal_options:
                if not isinstance(option, dict):
                    continue
                meta_raw = option.get("metadata")
                meta = meta_raw if isinstance(meta_raw, dict) else {}
                source_id = str(meta.get("source_object_id") or "")
                if source_id and source_id in command_ids:
                    commander_zone_cast_options += 1
                    name = command_names_by_id.get(source_id, "").casefold()
                    if not name:
                        name = str(meta.get("source_name") or option.get("label") or "").casefold()
                    casts = casts_by_name.get(name, 0)
                    if casts >= 1:
                        commander_zone_cast_options_taxed += 1
                        req_has_taxed_option = True

            if req_has_taxed_option:
                requests_with_taxed_commander_option += 1

            p_blind = _build_tax_blind_policy(corpus_tool.fresh_policy(seed))
            ans_blind = p_blind.decide(copy.deepcopy(request))
            key_orig = corpus_tool.answer_key(ans_blind)

            p_tax = cast(DecidingPolicyProtocol, corpus_tool.fresh_policy(seed))
            ans_tax = p_tax.decide(copy.deepcopy(request))
            key_tax = corpus_tool.answer_key(ans_tax)

            if key_orig != key_tax:
                answers_changed_by_tax += 1
                if not req_has_taxed_option:
                    answers_changed_without_taxed_option += 1

    evidence: dict[str, object] = {
        "source": [p.name for p in paths],
        "seeds": sorted(all_seeds),
        "classification": (
            "DIRECTLY_VERIFIED on the given dumps; a stratified 2-seed corpus "
            "is not the >=10-seed real-game measurement the issue asks for"
        ),
    }

    return {
        "requests_total": requests_total,
        "priority_requests": priority_requests,
        "requests_with_own_commander_damage": requests_with_own_commander_damage,
        "requests_with_commander_damage_ge_14": requests_with_commander_damage_ge_14,
        "commander_zone_cast_options": commander_zone_cast_options,
        "commander_zone_cast_options_taxed": commander_zone_cast_options_taxed,
        "requests_with_taxed_commander_option": requests_with_taxed_commander_option,
        "answers_changed_by_tax": answers_changed_by_tax,
        "answers_changed_without_taxed_option": answers_changed_without_taxed_option,
        "evidence": evidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure commander visibility and counterfactual tax impact (#1040)."
    )
    parser.add_argument(
        "dumps",
        nargs="*",
        type=Path,
        help="Corpus dump files (.jsonl or .jsonl.gz). Defaults to real_pod_v1 fixture.",
    )
    parser.add_argument(
        "--json",
        type=Path,
        dest="json_out",
        default=None,
        help="Optional path to write results as formatted JSON.",
    )
    args = parser.parse_args()

    paths = list(args.dumps)
    if not paths:
        tool = _load_corpus_tool()
        corpus_path = getattr(tool, "DEFAULT_CORPUS", None)
        if isinstance(corpus_path, Path) and corpus_path.exists():
            paths = [corpus_path]
        else:
            paths = [ROOT / "tests" / "fixtures" / "pilot_real_requests" / "real_pod_v1.jsonl.gz"]

    results = measure(paths)

    for k, v in results.items():
        if k != "evidence":
            print(f"{k}: {v}")
    print(f"evidence: {results['evidence']}")

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(results, indent=2), encoding="utf-8")

    wrong_reason_count = int(results.get("answers_changed_without_taxed_option", 0) or 0)
    if wrong_reason_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
