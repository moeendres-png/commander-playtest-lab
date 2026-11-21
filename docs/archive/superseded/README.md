# docs/archive/superseded/

Provenance only; not current instruction. See `../README.md`.

**What this folder holds.** Guidance replaced by a later document or decision. Entries keep their path under `docs/`:

- `PROJECT_UPDATE_CURRENT_STATE.md`
- `rules-engine-bridge-protocol.md`
- `STUDIO_SCOPE.md`, `STUDIO_PLAN_SIMULATOR.md`, `STUDIO_ROADMAP_20261112.md` (archived 2026-11-21)

**Why archived.** `PROJECT_UPDATE_CURRENT_STATE.md` duplicated `docs/OWNER_DECK_FOCUS_CURRENT.md`; `rules-engine-bridge-protocol.md` (Phase 8, XMage or Forge) is replaced by `docs/engine_adapter_protocol.md` and `schemas/engine_adapter_protocol.schema.json`. (`external_runtime_setup.md` belongs to the same superseded group — replaced by `docs/engine_setup.md` and `docs/owner_decision_20261013_forge_removal` — and stays anchored under `docs/` because a machine-readable historical YAML under `research/` cites its basename.) No removed code is described, so the commit is current `main` at archiving time.

The three Studio planning documents (former binding scope, simulator plan, roadmap of 2026-11-12)
were archived by the Owner answer 8a of 2026-11-21 (#1656, #1167, #1667): the charter
`../../STUDIO_CHARTA_V2.md` with the decision register `../../OWNER_DECISIONS_STUDIO_20261118.md`
is the required reading. Archiving did not lift their binding rules: every rule that was in
neither the charter nor the register was carried into the register, section 6, with its source
line; the fixed reference set of the Studio bridge gate moved verbatim to
`../../STUDIO_BRIDGE_GATE_TOOLING.md`. Their last commits on `main` before archiving are
`aef76b8e0b345ab61c216bfeb7890bf2d7b9998f` (scope) and `41938a58dc8489aa3121a98bab3c64990ac9a7c3`
(plan and roadmap; the plan's header lines 6 to 8 were corrected once more before the move).

**Last commit at which the described code existed:** `5e31a2712beb641a55e231c5c7378b401f89563a`. For the three Studio planning documents (no code described): `2a481efbe77d74a36859ba2b829a70f07307405d`, `main` at archiving time.

Contents are byte-identical to what they were under `docs/`; links inside them are history
and are not maintained.
