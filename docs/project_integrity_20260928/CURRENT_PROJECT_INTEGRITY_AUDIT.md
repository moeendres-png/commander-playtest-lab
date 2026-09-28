# Current project integrity audit

Initial main: `e91819ae18166a9f91ca52d101a72c8cb8eddade`.
Integration base: `f96bc7ec6b7ea07c73f74282c16dcaf73daaad40`, tree `c60a0ce2ffff404efcff9ada2b7979ec0cdc9346`.
The separately owned #278 merged while this audit ran; its 94-path change was
integrated by normal merge. No provider evidence is re-adjudicated here.

The fresh inventory covers 34 open PRs, 326
remote branches and seven currently open issues. Nine initially open issues have
explicit dispositions: #204 and #267 were already closed by Coordinator during
this workstream. Their closure is verified, not attributed to Astra.

Five recoverable legacy helper defects and a remote-identity check were repaired.
Operating documentation, permission consistency and source-truth boundaries were
reconciled. See GOVERNANCE_DRIFT_MATRIX and IMPLEMENTED_REPAIRS.

Retained old draft PRs contain paths absent from or different to current main;
the ledger lists each path and exact head. This audit does not establish semantic
obsolescence of historical provider evidence. They stay PROVENANCE, with no
branch deletion or bulk closure. #269 was externally closed after successor #278;
its history was not altered by Astra. The new #279 and sbmax branch are FOREIGN_ACTIVE.

A read-only check recovered exact sealed objects in the known legacy repositories.
Five minimal tooling deltas are ported. Replay validation is preserved for its
owner. Forge review object also resolves at its recorded local repository and is
PROVENANCE_ONLY, not falsely marked inaccessible. Combined histories are retained.

Ownership gate: launcher.py and its tests overlap sbmax/full-completion; proposed
Astra changes were withdrawn before integration. OWNERSHIP_CHECK.json records
zero overlap of the remaining repair commit with both active published lines.
Unpublished active work was not read or changed.

PASS is restricted to the listed tooling tests. Provider/runtime qualification is
outside scope. ARCHITECTURE_FREEZE = NOT CLAIMED; PRODUCTION_PROVIDER = NOT SELECTED.
