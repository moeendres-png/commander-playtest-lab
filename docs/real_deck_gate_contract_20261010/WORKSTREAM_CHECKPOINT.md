# #669 — existing real-deck gate contract

Direct Owner takeover: Codex implements and integrates; no further OC dispatch.
Earlier cancelled monthly-quota receipts remain provenance, not test evidence.
Source lock: Lab main `977e1d64eab5f1b9ad1a071bd378267cbc89d3a4`, tree
`69811693d3a320e21cfae3a48977507cb5ce6fda`; branch
`fix/real-deck-gate-contract-20261010`. Writable existing driver, dedicated test
and this directory only. #668 batch module and Claude #662/#634/#441 surfaces,
semantic replay implementation, pins/contracts/config/decks remain read-only.

Reuse-first: REUSE_AS_IS canonical deck_content_digest and recorder validation,
EXTRACT_AND_GENERALIZE existing driver. No new runner or replay system. Ordered
deck material and canonical source bytes stay unchanged; only seat-bound hashes
now match the recorder's sorted-material contract.

CLI and direct batch entry reject nonpositive counts before constructing an
engine or writing artifacts. Batch success requires every requested case's
completed terminal result, not merely zero failures. Single also requires an
observed terminal result. Replay keeps the existing tape verdict and diagnostic
twin hashes, and separately requires two terminal conformance runs for usability.
Output explicitly names bounded decision-tape/native-concession scope, with
full_natural_terminal_replay_validated and bit_exact_replay_validated both false.
The bounded replay is a separate recording, not consumption of the natural
terminal twin games. No matchup/all-card/official campaign evidence claimed.

Old-source corrected controls: 10 FAIL/2 PASS (exit1), including actual deck
hash/recorder incompatibility, vacuous batch and missing/nonterminal evidence.
Synthetic driver tests prove these acceptance boundaries only. Actual local
native command is unavailable; no local native full-game success is inferred.
Hosted required native gates, source-bound tests and fresh-context independent
Codex evidence review are recorded in issue/PR receipts. Existing #654 native
Foundry review tooling remains separate; no fake certificate.

Status: implementation candidate, not COMPLETE before normal integration and
actual merge/check receipts. Engine rules, legal options, principal information,
Rules RNG, native replay/cancellation/event semantics and qualification contract
are unchanged. Historical old-pin10/10 evidence receives no current credit.
