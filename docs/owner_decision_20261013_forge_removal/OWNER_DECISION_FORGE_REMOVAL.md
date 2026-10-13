# Owner decision 2026-10-13: Forge is removed; XMage is the only rules engine

**Decided by:** Owner (project chat, 2026-10-13). Recorded by the Coordinator, who is the sole writer.

**Owner's words:** "es soll nicht mehr optional sein sondern komplett entfernt werden und alle verweise
darauf um dinge zu vereinfachen und eine rules engine zu haben auf die wir uns konzentrieren und wo
alles funktionieren soll". In English: Forge is not to stay optional; remove it completely, together
with every reference to it, to simplify the project around one rules engine on which everything must work.

## What this supersedes

- The Forge role in the Engine Strategy ADR (`docs/engine_strategy_20261009/ENGINE_STRATEGY_ADR.md`):
  "bounded differential reference that runs on demand".
- Owner decisions 2 and 3 of 2026-10-10 (`docs/architecture_freeze_20261010/OWNER_DECISIONS_20261010.md`):
  "Forge stays a reference column only".

From this date on, Forge has no role. It is not a reference, not a differential column, not an optional lane
and not a container image.

## What changes in the active tree

The following are removed:
- **CI:** the Forge jobs and steps (H4 Forge materialization, the PB-03 `forge_reference` path, the PB-03
  shadow parallel Forge overlap, the PB09 Forge identity reference).
- **Integration:** `integrations/forge/`, `docker/forge/` and the Forge entries of the container scripts.
- **Scripts and code:** the Forge-only scripts and modules (scenario lane, residual and hidden-information
  census, causal route, workspace), and the Forge candidate in the current-boundary runner, assembler and
  provider-readiness packet.
- **Configuration:** `config/rules_engines.json` drops `secondary_engine` and the Forge bridge environment.
- **Tests, schemas, Foundry profiles, skills and active docs** that only exist for Forge.

Card names that contain the word ("Battlefield Forge", "Blackblade Reforged", ...) are card data, not
references to the engine, and stay.

## What does not change

- Sealed current-boundary epochs, signed Freeze documents, successor source locks, adjudication records
  and other dated evidence that name Forge keep their content byte for byte. They record what was true
  when they were written; this decision does not relabel them.
- The Owner-signed Architecture Freeze stays CLAIMED and bound to its epoch. It selected XMage. Removing
  the Forge reference narrows nothing XMage relied on.
- AF11 (interop and licence topology) is re-adjudicated for the XMage-only topology together with the
  repin-v6 requalification. Once Forge is gone, there is no GPL component anywhere in the project's
  process topology, so the Forge separate-process condition becomes vacuous rather than relaxed.
