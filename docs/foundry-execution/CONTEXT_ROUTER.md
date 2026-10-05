# Commander Context Router — shadow contract

Status: **EXPERIMENTAL / SHADOW ONLY / NOT DEFAULT**.

The router is a deterministic retrieval planner layered on the existing
`context_capsule.py` and schema-2.0 workstream state. It is deliberately not a new
authority store and it does not replace the capsule, state, contract, `AGENTS.md`, live Git,
tests, or sealed evidence.

## Design

`tools/foundry/context_router.py plan`:

1. validates the same state + live-Git identity through the existing capsule gate;
2. verifies the selected CPL/Mage/Forge repository profile matches the state's canonical slug
   **and** the worktree's single `remote.origin.url` matches that canonical GitHub repository;
3. chooses only repository **read domains** from explicit changed paths and bounded state signals;
4. emits references and deterministic helper commands, never conclusions;
5. broadens to the full state when routing is unknown or a risk marker is present;
6. emits the symbolic `$FOUNDRY_STATE_PATH` reference rather than echoing the local state-file path.

Broad fallback is mandatory when no deterministic route matches, more than 20 changed paths are
declared, an authority gate exists, failure classification is UNKNOWN, validation credit was
invalidated, or the state itself is STALE/SUPERSEDED.

The output intentionally does not repeat objective/failure prose. It names route reasons rather
than echoing state content.

## On-demand engine repo maps

`context_router.py repo-map` produces a bounded directory map from exact committed `HEAD`.
It does **not** read file contents and never runs automatically. Mage/Forge plans return the command
as `ON_DEMAND_ONLY`; the caller supplies an already declared reference root. Before listing names,
the command is restricted to Mage/Forge reference roots and loads the corresponding canonical
repo profile. It then requires the exact launcher-provided `FOUNDRY_REFERENCE_ROOTS`
declaration for that profile and re-verifies its root, canonical slug, exact HEAD, exact tree,
cleanliness and read-only intent. The checkout must be the declared Git toplevel, and any
`url.*.insteadOf` rewrite or `FOUNDRY_ROUTING_SUPPRESSED=1` fails closed. The caller cannot
self-assert a replacement HEAD.

The map records declared/live HEAD and tree identity plus directory names up to an explicit
maximum depth. Traversal is breadth-first with non-recursive `git ls-tree` calls and stops at
the requested depth; it never performs a whole-tree recursive walk and then post-filters.
Repository-relative prefixes are syntax-bounded (no absolute paths, traversal, wildcard/pathspec
magic or whitespace-surrounded values), at most 16 prefixes are accepted, prefix scoping applies
to both directories and root entries, and output fails closed above 500 directories or 200 root
entries. Directory presence is navigation data only, never evidence that a mechanic or API
behaves as expected.

## Authority and promotion boundary

- Root `AGENTS.md` remains privileged always-on policy. The router never summarizes or replaces
  its MUST/NEVER, Rules, Source-Truth, Evidence, privacy, Git, ownership, nonclaim, or completion
  invariants.
- The workstream state remains an operational index, not Source Authority.
- The router cannot produce qualification credit, Rules conclusions, legal actions, defaults,
  ownership, or a merge decision.
- Unknown routing means **more context**, never less.
- No `/work`, `AGENTS.md`, launcher, model-routing, or OpenCode default consumes this router yet.

Default activation requires representative real-session A/B evidence through the #546 measurement
harness with no evidence/review/defect loss. Until that exists,
`default_activation_authorized = false`.

This implements the architecture direction “less always-on context → better routing → on-demand
retrieval” as a testable shadow component, without claiming any token or time saving.

## Provider and fallback boundary

Provider identity is never inferred from free-text mentions of XMage, Mage or Forge. The selected
repository profile is the only provider-routing authority. A CPL engine-bridge task therefore
broadens until a provider-specific workstream/profile exists. `BROAD_FALLBACK` emits no
provider-specific repo-map commands.

Changed repository paths are routed only through the explicit path table; they are not recycled
into free-text signal matching. Dot-directories such as `.github/`, `.opencode/` and
`.foundry/` retain their leading dot and have positive regression controls.
