# Evidence-Classification Vocabulary — Decision Package

For the Coordinator / evidence-policy tier. **No policy is proposed or changed here.**

This package exists so that the evidence-classification question can be *decided* rather than
re-investigated. It was raised as deferral `D1` by the project-hygiene campaign of 2026-09-29
and could not be actioned there, because evidence classification is a policy surface.

Measured at `origin/main` = `7055740ec2f08d4864bf7e200f7b48ace521fe57`.

---

## 1. The headline

**A JSON Schema in this repository is a singleton enum that accepts exactly one value —
`RUNTIME_VERIFIED` — and rejects all seven classes that `AGENTS.md` §4 defines.**

`qualification/protocol/ws10r/candidate_fixture_manifest_v1.schema.json:45-49`:

```json
"expected_evidence_class": {
  "enum": [
    "RUNTIME_VERIFIED"
  ]
}
```

Empirically verified with `jsonschema` 4.19.2 (`Draft202012Validator`), one fixture mutated at
a time:

| Value of `expected_evidence_class` | In `AGENTS.md` §4? | Accepted by the schema? |
|---|---|---|
| `DIRECTLY_VERIFIED` | yes | **no** |
| `CODE_DERIVED` | yes | **no** |
| `TECHNICALLY_CONFORMANT` | yes | **no** |
| `EXTERNALLY_RULE_VALIDATED` | yes | **no** |
| `MODELED` | yes | **no** |
| `SYNTHETIC` | yes | **no** |
| `UNKNOWN` | yes | **no** |
| **`RUNTIME_VERIFIED`** | **no** | **yes** |

Seven of seven documented classes rejected. The repository's own
`qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json` uses `RUNTIME_VERIFIED` and
validates cleanly (0 errors).

**The disagreement is total, not partial, and it is machine-enforced in the direction opposite
to the written policy.**

---

## 2. Why `RUNTIME_VERIFIED` is load-bearing, not a stray annotation

It is emitted by code, validated by a schema, asserted by a test, run in CI, and pinned by four
independent hash manifests:

```
qualification/harness.py:113
    "RUNTIME_VERIFIED" if verdict in {"PASS","FAIL"} else "NOT_RUN"
        ↓ writes
qualification/evidence/candidates/*.json                     (evidence_class, 675 assignments)
qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json       (expected_evidence_class, 135)
        ↓ declared by
qualification/evidence/candidate_result_v1.schema.json
qualification/evidence/normalized_evidence_v1.schema.json
qualification/protocol/ws10r/rsp_semantics_v1.schema.json
        ↓ enforced by
tests/qualification/test_ws17_qualification.py:25-27         Draft202012Validator(...).validate(...)
        ↓ run by
.github/workflows/production-qualification.yml:39,41
        ↓ hash-pinned by
WS17_SHA256SUMS:63,67,93 + qualification/SHA256SUMS:60,64,89
        ↓ embedded in
qualification/protocol/ws10r/WS-10R_ENGINE_NEUTRAL_PROTOCOL_BUNDLE.zip (+ .sha256, inner SHA256SUMS)
```

`harness.py:113` means **every provider run that returns `PASS` or `FAIL` is labelled
`RUNTIME_VERIFIED` automatically.** It is the harness's default success class, not a one-off
annotation. Changing the vocabulary changes harness output semantics.

---

## 3. Measured vocabulary inventory

Method: parsed every tracked JSON/YAML with exact whole-string value equality (never
substring) against the keys `expected_evidence_class`, `evidence_classification`,
`evidence_class`, `classification`. **2,670 occurrences, 96 distinct (key, value) pairs.**

### 3.1 A structural caveat that shrinks the apparent defect ~8×

The key `classification` is **overloaded across at least six unrelated axes**. Only a minority
of its 96 values are evidence classes:

| Bucket | Distinct pairs |
|---|---:|
| Non-class axes sharing the key `classification` (conformance verdicts, repo-hygiene dispositions, branch retention, impact adjudication, provider blockers) | **64** |
| Undocumented values in a class position | 11 |
| The 7 documented classes, exact | 9 |
| Sentence- or conditional-valued entries | 8 |
| Verdict tokens sitting in a class-named key | 4 |

So "the repo uses many classification values" is mostly not an evidence defect. The real
finding is narrower and sharper: `RUNTIME_VERIFIED` specifically.

### 3.2 Documented classes, machine-readable

| Class | Occurrences | Files |
|---|---:|---:|
| `DIRECTLY_VERIFIED` | 104 | 10 |
| `EXTERNALLY_RULE_VALIDATED` | 42 | 1 |
| `CODE_DERIVED` | 19 | 4 |
| `TECHNICALLY_CONFORMANT` | 19 | 3 |
| `UNKNOWN` | 8 | 2 |
| `MODELED` | **0** | **0** |
| `SYNTHETIC` | **0** | **0** |

`MODELED` and `SYNTHETIC` are documented but have no machine-readable use anywhere.

### 3.3 Undocumented values in a class position

| Value | Occ | Files | Note |
|---|---:|---:|---|
| **`RUNTIME_VERIFIED`** | **142** | 6 | the subject of this package |
| `NOT_RUN` | 675 | 5 | a *verdict* token on the `evidence_class` key |
| `NOT_EXECUTED_CURRENT_BOUNDARY` | 204 | 2 | |
| `FRESH_CURRENT_BOUNDARY_RUNTIME` | 10 | 2 | |
| `FRESH_CURRENT_BOUNDARY_EXECUTION` | 5 | 3 | |
| `technical_conformance_only` | 11 | 11 | lowercase, free-form, asserted by CI string equality only |
| `structural_model_estimates` | 7 | 3 | same |
| `external_rules_reference` | 1 | 1 | same |
| `verified_card_facts_with_external_crosscheck` | 1 | 1 | same |
| `derived_technical_benchmark_reference_not_canonical_gameplay_truth` | 1 | 1 | |

There is a **fifth concurrent vocabulary** on `evidence_class`: the lowercase free-form axis
(`technical_conformance_only` and friends), enforced only by CI string equality and by no schema.

### 3.4 Compound and sentence values

`IMPLEMENTED_AND_RUNTIME_VERIFIED` (24), `CODE_DERIVED_NE_RUNTIME_VERIFIED` (2 — a live
obligations contract using the negation as a boolean switch name), `RUNTIME_NOT_RUN` (675),
`ALREADY_IMPLEMENTED_VERIFIED`, `REJECTED_BY_RULES_AUTHORITY`, `BLOCKED_FAIL_CLOSED`, and
several entries where a whole policy sentence sits in the `evidence_class` value, including one
conditional: *"CODE_DERIVED unless noted as RUNTIME_VERIFIED by the named test or regression
run"*. No schema constrains any of these, so they pass silently.

---

## 4. Two axes, conflated

Evidence class and verdict are **different axes** and the repository has five verdict
vocabularies:

| Vocabulary | Tokens | Where |
|---|---|---|
| V1 machine | `PASS FAIL UNKNOWN NOT_RUN PARTIAL UNSUPPORTED NOT_APPLICABLE` | the four schemas' `enum`s |
| V2 index | `PASS FAIL PARTIAL TERMINAL SUPERSEDED` | `docs/EVIDENCE_INDEX_REQUIREMENTS.md:34` |
| V3 freeze | `FAIL UNKNOWN PARTIAL NOT_RUN UNSUPPORTED` | `SOURCE_LOCK.json` → `non_pass_verdicts` |
| V4 obligation | `PASS FAIL UNKNOWN` | WS90 adjudication |
| V5 execution | `PASS FAIL UNKNOWN BLOCKED CRASH TIMEOUT PROTOCOL_FAILURE TOTAL` | `full107_counts` |

Measured conflation: 675 `NOT_RUN` in `evidence_class`, 13 `PASS` and 8 `PARTIAL` in
`classification`.

Also: the documented V2 `result` vocabulary has **zero machine-readable usage**, and
`FULL` — which `AGENTS.md:91` mandates in `PARTIAL != FULL` — appears in **no** schema `enum`
anywhere.

### 4.1 Three agent/skill files, three verdict vocabularies

| File:line | Tokens |
|---|---|
| `.opencode/skills/evidence-seal/SKILL.md:11` | `PASS FAIL UNKNOWN NOT_RUN` |
| `.opencode/agents/foundry-reviewer.md:43-46` | `PASS FAIL PARTIAL UNKNOWN` |
| `.opencode/agents/foundry-adjudicator.md:92-93` | `PASS FAIL PARTIAL UNKNOWN` |
| `.opencode/agents/foundry-adjudicator.md:70` | `PASS FAIL UNKNOWN` |

Four conflicts, all real:

1. `PARTIAL` does not exist in the evidence-seal skill — so a partially-delivered run has no
   valid encoding in the one skill whose job is recording run outcomes.
2. `NOT_RUN` does not exist in either agent file — the same physical event (a command never
   run) is a distinct first-class value in one file and inexpressible in the other two.
3. `foundry-adjudicator.md` contradicts **itself**, line 70 versus lines 92-93.
4. `AGENTS.md:91` mandates `FULL`, which no vocabulary defines.

---

## 5. The `QUALIFIED` question, settled

An earlier campaign claimed `QUALIFIED` was an undefined class in positive use. **That was a
substring artifact and is false.** Word-boundary search finds 15 occurrences repo-wide, each
enumerated:

| Count | Nature |
|---|---|
| 4 | the phrase `NOT QUALIFIED` inside quoted PR titles (three JSON ledgers) |
| 1 | a quoted commit subject reading `5 QUALIFIED, 8 UNKNOWN` |
| 10 | this project's own audit text *about* `QUALIFIED` |

**Zero** machine-readable assignments, **zero** prose class-position assignments.
`QUALIFIED` is not a defect. Stated here so it is not raised a third time.

---

## 6. The decision surface

### Branch A — recognise `RUNTIME_VERIFIED` as a class (7 becomes 8)

| # | File | Change | Load-bearing? |
|---|---|---|---|
| A1 | `AGENTS.md:88-89` | add to the class list; reconcile line 91 | policy source |
| A2 | `docs/EVIDENCE_INDEX_REQUIREMENTS.md:31-33` | add to the index vocabulary | canonical companion |
| A3 | `qualification/protocol/ws10r/candidate_fixture_manifest_v1.schema.json:45-49` | expand the singleton `enum` | **yes** |
| A4 | `qualification/evidence/candidate_result_v1.schema.json:106-114` | align enum | **yes** |
| A5 | `qualification/evidence/normalized_evidence_v1.schema.json:45-53` | align enum | **yes** |
| A6 | `qualification/protocol/ws10r/rsp_semantics_v1.schema.json:85-93` | align enum | **yes** |
| A7 | `qualification/harness.py:113` | only if the emitted token changes | **yes** |
| A8 | `qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json` | only if fixture values change | **yes** |
| A9 | `tests/qualification/test_ws17_qualification.py:25-27` | only if assertions change | **yes** |

**Mandatory cascade if A3 or A8 changes** — `test_ws17_qualification.py:181-193` asserts exact
set equality of the hash manifests against the filesystem, so these cannot be skipped:

`WS17_SHA256SUMS` · `qualification/SHA256SUMS` ·
`qualification/protocol/ws10r/WS-10R_ENGINE_NEUTRAL_PROTOCOL_BUNDLE.zip` (+ `.zip.sha256`) ·
`qualification/protocol/ws10r/SHA256SUMS`

Branch A does **not** by itself fix the 6 further undocumented class values in §3.3, the
sentence values in §3.4, the conflation in §4, or the three verdict vocabularies in §4.1.

### Branch B — declare a separate machine axis

Two files change: `AGENTS.md` §4 and `docs/EVIDENCE_INDEX_REQUIREMENTS.md` — stating that a
distinct machine axis exists, naming the schemas as its authority, and defining precedence
against the prose classes. Neither file is enforced.

Residual risk under Branch B, concretely:

1. **No precedence rule exists anywhere today.** Both documents present the 7 as *the*
   definition, with no clause deferring to a schema. Branch B requires writing a new normative
   rule.
2. The divergence stays machine-enforced and silent: an author who follows `AGENTS.md` and
   writes `DIRECTLY_VERIFIED` into a manifest gets a validation failure with no documented
   explanation.
3. In practice the **schema and harness are the de facto authority** while the documents claim
   otherwise.
4. The verdict-axis conflicts in §4.1 are untouched by either branch.
5. S2/S3/S4 permit only 2 of the 7 documented classes, so "the schema defines the machine axis"
   is itself only partly true.

---

## 7. Adjacent findings, recorded not investigated

- `qualification/evidence/BASELINE_COMMON_RESULTS.json` is **INVALID** against
  `candidate_result_v1.schema.json` (145 errors, shape mismatch — missing 12 required fields).
  A shape defect, distinct from the vocabulary question.
- Three schema enums declare values never used outside the schemas: `RUNTIME_PASS`,
  `DIRECT_CODE_FAIL`, `SOURCE_DERIVED`.
- `AUTHORITY_VERIFIED` appears in
  `candidate-qualification/ws47-successor-v1.0.5/WS47_WORKSTREAM_CONTRACT.md:170` alongside
  `CODE_DERIVED` and `RUNTIME_VERIFIED`; broader usage not measured.
- `expected_value` was checked and **excluded**: all 378 occurrences hold SHAs, versions, seeds
  and card names in `RETENTION_PREDICATES.json`. It is not an evidence-classification field.

---

## 8. Classification

Everything in this package is `DIRECTLY_VERIFIED` by quoted line, executed validator run, or
stated count. **No engine, card, or gameplay behaviour was exercised**, so nothing here supports
any card- or engine-level claim.

**The decision is a Coordinator call.** Both branches are laid out with concrete file lists.
