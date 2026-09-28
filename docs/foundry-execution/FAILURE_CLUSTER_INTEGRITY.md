# Failure-cluster integrity

```sh
python3 tools/foundry/cluster_failures.py --input failures.json --output clusters.json
```

Clustering remains advisory. It does not establish common root cause, validate evidence
references, grant qualification credit, or convert supplied verdicts to PASS.

Input is a JSON array; an empty array produces an empty cluster list. Every record must
contain nonempty string `id`, `message`, and `evidence` fields. IDs must be unique across
the entire input and cannot have surrounding whitespace. Evidence references are opaque
strings, preserved exactly and never fetched. If present, `verdict` must be a nonempty
string and is preserved exactly; an absent verdict remains UNKNOWN. Extra fields are
not emitted. No input object is mutated.

The existing normalization heuristic is unchanged. Grouping uses the complete normalized
signature, avoiding truncated-digest identity. Clusters sort by descending size and then
signature; members sort by original ID. Input permutations therefore yield identical
output. Every valid input record appears once, with its original ID and evidence reference.

Invalid shapes, duplicate IDs/JSON keys and malformed JSON return exit 1 with
`CLUSTER_INVALID` on stderr, no stdout report, and no newly published file. Diagnostics
include only fixed field names/record positions, not offending values or decoder context.

File publication uses same-directory temporary output followed by atomic replacement.
The input cannot also be the output, including hardlink/symlink aliases. Failed publication
before replacement retains the previous file. Check the current exit code: an existing
report does not imply current success. Output parent directories must already exist.

Use stable inputs and output paths with no concurrent writer. Atomic replacement is not
an fsync durability guarantee, a source lock, or a filesystem transaction. The parser
cannot detect omitted source records or distinguish relabeled duplicates with different
IDs. Legacy inputs lacking identity/evidence now require correction, not invented defaults.

Normalized signatures may retain sensitive details from messages. This tool is not a
redactor and does not make input suitable for public or cross-principal sharing. Keep
input and generated reports within the same authorized evidence/privacy scope.

Validate with the new `tests/foundry/test_failure_cluster_integrity.py`, existing
`tests/foundry/test_foundry_tools.py`, then the Foundry suite. No engine suite or live
provider execution is required by this local advisory-tool change.
