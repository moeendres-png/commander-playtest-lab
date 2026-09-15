# WS222 ORACLE_IDENTITY_MODEL

Canonical identity strategy (satisfies R-OR-2). Three levels, never conflated:

1. **Denominator identity** — the fixture-level name from
   `COMMON_FIXTURE_MANIFEST_v1.json` `card_identity` (29 values, e.g.
   `"Wear // Tear"`, `"Boseiju Reaches Skyward // Branch of Boseiju"`).
2. **Per-face Oracle identity** — official `oracleName`(s) observed on the
   canonical page: singletons one name; split cards two names with ONE combined
   Oracle text (`Wear` + `Tear`: "Destroy target artifact. // Destroy target
   enchantment. // Fuse ..."); MDFC two names across TWO pages
   (`Boseiju Reaches Skyward` front Saga text on `/177/boseiju-reaches-skyward`,
   `Branch of Boseiju` back text on `/177/branch-of-boseiju`).
3. **Printing identity** — official per-printing `resourceId` + `setCode` +
   `cardNumber` (+ `multiverseId`). Front main-card ids are 32-hex; MDFC
   back-face composite ids are 64-hex (WS222 parsing finding; tooling accepts
   `{32,64}`). The pinned printing is the canonical URL's printing (one per
   face); Oracle function is printing-independent.
4. **Oracle functional identity** — the `oracleText` (+ mana/type/PT) per face
   in `ORACLE_FIELD_SNAPSHOT.json`. Related printings listed on the page share
   it (verified: 3–80 repeated occurrences per page, 1 distinct value each).

Edge coverage in the denominator: 2 split cards (combined-text model), 1 MDFC
Saga (dual-page model, `compositeType: Doublefaced`, back resourceId pinned),
4 partner commanders (Ishai/Rograkh/Esior/Kediss + Jeska), 1 planeswalker
(Narset; Jeska), Sagas, modal/X/Overload/Cleave/Fuse mechanics. Same-name
ambiguity is resolved by pinning the printing; interchangeable-name risk is
none in the denominator (all 29 names distinct at face level).

Machine companion: `artifacts/oracle/ORACLE_FIELD_SNAPSHOT.json`
(30 pages: 29 front + 1 MDFC back; per-record face, URL, SHA, fields).
