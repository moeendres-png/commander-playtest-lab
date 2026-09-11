import hashlib
import json
import pathlib
import subprocess
import sys

from jsonschema import Draft202012Validator

ROOT = pathlib.Path(__file__).resolve().parents[2]
MAT = ROOT / "qualification/materialization"


def load(name):
    return json.loads((MAT / name).read_text(encoding="utf-8"))


def test_schema_and_cardinality():
    schema = load("SEMANTIC_FIXTURE_SCHEMA_v1.json")
    corpus = load("SEMANTIC_FIXTURE_MATERIALIZATION_v1.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(corpus)
    assert corpus["record_count"] == 135
    assert len(corpus["records"]) == 135
    assert len({r["fixture_id"] for r in corpus["records"]}) == 135


def test_materialization_file_checksum_and_subset_counts():
    expected = (MAT / "SEMANTIC_FIXTURE_MATERIALIZATION_v1.sha256").read_text().split()[0]
    actual = hashlib.sha256(
        (MAT / "SEMANTIC_FIXTURE_MATERIALIZATION_v1.json").read_bytes()
    ).hexdigest()
    assert actual == expected
    assert load("DIFFERENTIAL_STARTER_18.json")["fixture_count"] == 18
    assert load("KNOWN_PASS_UNION_50.json")["fixture_count"] == 50
    assert load("MATERIALIZATION_BLOCKERS.json")["blocker_count"] == 0


def test_validator_strict_against_repository_sources():
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/validate_ws30_materialization.py"),
            "--repo-root",
            str(ROOT),
        ],
        check=True,
    )
