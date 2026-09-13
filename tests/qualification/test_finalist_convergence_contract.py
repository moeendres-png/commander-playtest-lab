import hashlib
import json
import pathlib
import unittest

from jsonschema import Draft202012Validator


ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "qualification" / "finalist_convergence"
VERSION = "commander-lab.semantic-fixture-materialization/1.0.1"
COMMON_SHA = "e7f34ea4b2543132440e7e5fdb47c6cb4d4908f05fb49f6fa59f3e0592ca3bd4"


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def canonical_sha(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class FinalistConvergenceContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = load("SEMANTIC_FIXTURE_SCHEMA_v1_0_1.json")
        cls.corpus = load("SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_1.json")
        cls.report = load("SEMANTIC_EXECUTABILITY_REPORT.json")

    def test_schema_and_denominator(self):
        self.assertEqual([], list(Draft202012Validator(self.schema).iter_errors(self.corpus)))
        records = self.corpus["records"]
        self.assertEqual(VERSION, self.corpus["schema_version"])
        self.assertEqual(135, len(records))
        self.assertEqual(135, len({record["fixture_id"] for record in records}))
        self.assertTrue(all(record["frozen_contract_binding"]["manifest_sha256"] == COMMON_SHA for record in records))

    def test_immutable_digests(self):
        for record in self.corpus["records"]:
            value = dict(record)
            observed = value.pop("materialization_digest")
            self.assertEqual(observed, canonical_sha(value), record["fixture_id"])
        value = dict(self.corpus)
        observed = value.pop("canonical_bundle_digest")
        self.assertEqual(observed, canonical_sha(value))

    def test_semantic_gate(self):
        self.assertEqual(135, self.report["terminal_result_count"])
        self.assertEqual(18, self.report["starter_18"]["pass"])
        self.assertEqual([], self.report["starter_18"]["defects"])
        self.assertEqual("PASS", self.report["schema_status"])

    def test_starter_and_union_bind_exact_record_digests(self):
        by_id = {record["fixture_id"]: record for record in self.corpus["records"]}
        for name, count in (("DIFFERENTIAL_STARTER_18_v1_0_1.json", 18), ("KNOWN_PASS_UNION_50_v1_0_1.json", 50)):
            subset = load(name)
            self.assertEqual(count, subset["fixture_count"])
            for record in subset["records"]:
                self.assertEqual(by_id[record["fixture_id"]]["materialization_digest"], record["materialization_digest"])

    def test_checksums(self):
        for line in (OUT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
            digest, name = line.split("  ", 1)
            self.assertEqual(digest, hashlib.sha256((OUT / name).read_bytes()).hexdigest(), name)


if __name__ == "__main__":
    unittest.main()
