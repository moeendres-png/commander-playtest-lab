# WS230 Source Lock

Research-only workstream. No authority mutation. No PASS claims.

## CPL repository (writer worktree)

- Repository: `moeendres-png/commander-playtest-lab`
- Branch: `ws230/provider-integration-topology-preflight-20260915`
- Audit base (WS226): `fb156d2b4cf8c5c21d0c84e844a53160032c0992`
- Audit base tree (verified `git rev-parse HEAD^{tree}`): `52359f47eea7ddc1e4ec8187e89b67fa67d63616`
- HEAD at WS230 start: `fb156d2b4cf8c5c21d0c84e844a53160032c0992` (clean, verified `git status --short --branch`)
- `ARCHITECTURE_FREEZE = NOT_CLAIMED`, `PRODUCTION_PROVIDER = NOT_SELECTED` (inherited; unchanged by WS230)

## Read-only external provider authority (Forge WS227)

Declared via `FOUNDRY_REFERENCE_ROOTS`, verified read-only:

- Label: `ws227-forge-semantic-replay`
- Repo: `moeendres-png/forge`
- Reference commit: `8ff3e7a48271eaba847608701f4c284c20dcdf68`
- Reference tree: `be5e3f3a9207c23ca6b2673a95086b718236d0c4`
- WS227 provider code (per `ws227-lab-successor-spec.json` SOURCE_LOCK): `eb87b31759c2a9989a819f408c52b3da5c00301d` / tree `cb4e5dbd54f55490308379a32de94dd859234707`
- WS227 replay Core (per same spec): `d52e890538dc0380d1b26d781349312e310b3a2b` / tree `302938b7f66cd1524d784f9bc85fb445beb21179`
- WS227 audit base: `e152688a33bf69a840b74ae86149d881e64538ec`
- Forge reference root was never written by WS230 (read-only; no build inside it).

## Active sibling

- WS229 (XMage numeric/decision-boundary S6 implementation) is active and unpublished.
- WS230 did NOT inspect unpublished WS229 local state and did NOT mutate WS229 surfaces.
- Post-WS229 delta predicates are defined in `POST_WS229_DELTA_REVALIDATION.json`.

## Mutation ownership (enforced)

- WS230 modified ONLY `research/provider-integration-topology/ws230/**` plus external Foundry state.
- No modification to `src/**`, `engine-bridge/**`, `qualification/**`, `config/**`, `integrations/**`, `.github/**`, `requirements/**`, Dockerfiles, protocol authority, manifests, standing, Foundry tooling, or the Forge reference root.
- Verification: terminal `git status` + `git diff --stat` scoped to the ws230 directory (see `VALIDATION.md`).

## CPL pins consumed (authority, not restated as new truth)

- XMage Rules-Core pin: `db134b9737e951367d65ef5806ad986319cc73ab` (source: `config/rules_engines.json` `primary_engine.commit`; corroborated by `XmageProvider.ENGINE_COMMIT` and WS226 `CANDIDATE_FACTS.json` xmage source).
- Forge Rules-Core pin (current CPL): `a37a865a53280dd8ad6fad3384d69611e8c5a42f` with bridge source `4753bb7c72ea60d653121e0bab989077b4009f9c` (source: `config/rules_engines.json` `secondary_engine`; WS230 does NOT conflate this with the newer WS227 Forge pins above — the WS227 pins live in the Forge repo, not in CPL).
- RSP authority: `commander-lab.rules-service/1.1.0` (`qualification/protocol/ws10r/RULES_SERVICE_PROTOCOL_V1.md` + `rules_service_protocol_v1.schema.json`).
- Freeze catalog: `architecture_freeze_gate_catalog_v1.json` (AF00–AF11, all required).
- Obligations: `FULL_RULES_REQUIREMENTS_CONTRACT_v1.json` (G00–G15; G15 optional).
- Standing: `qualification/ws226-consolidated-cpl-authority-integration/*` (AF01/G12/AF11 all non-PASS; see `CURRENT_BLOCKER_MAP.json`).
