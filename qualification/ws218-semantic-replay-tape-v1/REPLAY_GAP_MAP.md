# WS218 REPLAY_GAP_MAP

What WS215 left open (PARTIAL) and how WS218 closes each item without
state/outcome injection or a second Rules engine.

| # | Gap (WS213/WS215 absent) | WS218 closure | Evidence |
|---|---|---|---|
| G1 | No versioned tape schema (ad-hoc JSON dumps) | `semantic-replay-tape/1.0.0` strict pydantic schema: source_lock, manifest, rng_contract, initial/terminal checkpoints, ordered steps, seal | `TAPE_SCHEMA.md`, `TAPE_SCHEMA.json`, unit schema tests |
| G2 | No source/domain lock enforcement | Material lock (lab commit/tree, provider, engine commit/version, adapter/protocol + schema digest, rules authority, snapshots, deck hashes, N, seats, commanders, starting config); refuse-before-execution on mismatch | `SOURCE_LOCK.md`, tamper `TAMPER_SOURCE/DECK/SEED` negatives |
| G3 | No semantic option identity (raw UUIDs/positions/labels/first-option) | `semantic-option-identity-1.0.0`: type+redacted label+semantic metadata+observation-joined public projection; UUIDs never hashed; 0-match and >1-match fail closed; no fuzzy match | `SEMANTIC_OPTION_IDENTITY.md`, duplicate-name tests, `TAMPER_OPTION` |
| G4 | Legal set treated as single pick, not compared as domain | Multiset digest (sorted fingerprints, multiplicities preserved); authoritative==recorded required before every resubmission; no requested-option filtering | `LEGAL_SET_MATCHING` negatives (`TAMPER_LEGAL_SET`) |
| G5 | Duplicate cards by name-only | Zone/occurrence + public-characteristics join; identical public projections are AMBIGUOUS (fail closed, never first) | `DUPLICATE_ACTION_DISAMBIGUATION` tests |
| G6 | Single omniscient hash / hidden leakage risk | Three digests: internal checkpoint, public state, per-principal observation; hashes only on pilot surfaces; honeycard/oracle-style hidden scans | `STATE_DIGEST_CONTRACT.md`, `HIDDEN_INFORMATION_REPLAY` |
| G7 | No canonicalization version | `semantic-canonical-1.0.0`: UTF-8, sorted keys, stable scalars, ordered stays ordered, unordered sorted by fingerprint, no timestamps/wall-clock/process ids unless proven nonsemantic | `CANONICALIZATION_CONTRACT.md`, canonical unit tests |
| G8 | No RNG attribution beyond total calls | Root seed + explicit/require + per-step calls before/after from live binding; calls-coordinate-plus-state-transition model; fresh engine regenerates; mismatch fails; RandomUtil never authoritative | `RNG_TAPE_CONTRACT.md`, `TAMPER_RNG` |
| G9 | No event tape (or raw-string equality) | Decision-offset range + canonical event digest (class/actor/selection/numeric/calls/turn/observation/post); debug strings excluded; material transitions bound | `EVENT_TAPE_CONTRACT.md`, `TAMPER_EVENT` |
| G10 | No checkpoints (or checkpoints-as-restore) | Evidence-only checkpoints (seed/calls/turn/phase/step/offset/digests); progress by native decisions from normal construction; no zone/life/counter/ledger/stack/winner writes | `CHECKPOINT_CONTRACT.md`, `NO_STATE_INJECTION` scan |
| G11 | No shipped consumer (twin stream-following only) | First-class fresh-process consumer implementing the 14-step algorithm; resolves recorded print to EXACTLY ONE native option; submits CURRENT native ids | `REPLAY_CONSUMER_CONTRACT.md`, `REPLAY_2P/3P/4P/5P` |
| G12 | No divergence taxonomy (warn-and-continue risk) | 18 fail-closed classes; existing vocabulary reused where exact; no WARN_AND_CONTINUE | `DIVERGENCE_TAXONOMY.md`, `TAMPER_MATRIX` |
| G13 | `replay_supported` unqualified | Tape-lane flag true only after full contract qualified; bridge flag stays false; mere exporter/twin insufficient | `CAPABILITY_TRUTH.md` |
| G14 | No fresh-process positive per count | Representative 2P/3P/4P/5P via production lane; RNG-after-start, target/object, numeric, Commander branch, elimination/concession coverage | `REPLAY_2P..5P` + `PROCESS_ISOLATION` |
| G15 | No tamper negatives | Source/deck/seed/actor/class/revision/missing/extra/legal/option/RNG/event/state/terminal/malformed matrix; no partial-mutation PASS | `TAMPER_MATRIX` |

Machine companion: `REPLAY_GAP_MAP.json`.
