# Current engine decision matrix

The `current runtime` columns below report actual Phase-8.5 execution, not upstream documentation.

| Criterion | XMage | Forge |
|---|---|---|
| Pinned version | `xmage_1.4.60V3` / `06d166b...` | `forge-2.0.13` / `852066b...` |
| Build in current runtime | Not executed: DNS unavailable and Maven absent | Not executed: DNS unavailable, Maven/Docker absent |
| Headless/test mode | Documented upstream; not executed here | Documented upstream; not executed here |
| Commander | Documented upstream; not executed here | Documented upstream; not executed here |
| Multiplayer | Documented upstream; not executed here | Documented upstream; not executed here |
| Programmatic actions | Protocol prepared; provider binding not executed | Protocol prepared; provider binding not executed |
| Log access | Protocol prepared; provider binding not executed | Protocol prepared; provider binding not executed |
| Reproducible state | Requested by handshake; not confirmed externally | Requested by handshake; not confirmed externally |
| Python adapter effort | High, but best tactical/test fit | Medium-high; useful differential backend |
| License consequences | MIT; simpler integration | GPL-3.0; kept as separate process |
| Maintenance role | Primary | Secondary/fallback |

**Decision:** XMage remains the primary target. Forge remains a differential fallback. This is a provisional engineering decision; no current-runtime external capability is marked validated.
