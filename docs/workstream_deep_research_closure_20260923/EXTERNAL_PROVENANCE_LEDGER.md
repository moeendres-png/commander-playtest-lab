# External Provenance Ledger (Phase 0)

No foreign code has been transferred in this workstream as of Phase 0.

Standing license postures (to be reverified before any transfer):

- XMage (`moeendres-png/mage`, pin `db134b9737e951367d65ef5806ad986319cc73ab`,
  Maven `1.4.61`): engine-native API use through the pinned dependency and
  existing project integration is authorized in principle; exact file/project
  provenance must still be verified before copying implementation text.
- Forge (GPL-derived): reference/differential use preferred; no source
  transplantation without explicit license adjudication.
- Manabrew (AGPL/GPL constraints): methodology only, independent
  reimplementation; no code copy without explicit approval.
- Argentum (research-indicated MIT, UNVERIFIED): selective concepts/tests only
  after exact provenance reverification.
- Phase (research-indicated MIT/Apache-2.0, UNVERIFIED): bug/test intelligence
  primarily; reverification required before copying.

Every future external influence (reuse, extract, wrap, port, reference) must
append a dated entry here with: source repository + lock, exact files/symbols,
classification (`REUSE_AS_IS` / `EXTRACT_AND_GENERALIZE` / `WRAP` /
`PORT_FROM_DONOR` / `ENGINE_NATIVE_REUSE` / `REFERENCE_ONLY`), license check,
and the local paths affected.
