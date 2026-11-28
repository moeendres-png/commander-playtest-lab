# D7: check and filing of the 52 PLAY/SIMULATE research filings

- **Date:** 2026-11-28 · **Refs:** `#1167` · Owner go: D7 („hier mein los also prüfen“, register entry of 2026-11-28)
- **Source:** the Owner's prepared filing list of 2026-11-26 (52 blocks; the full research reports stay local with the Owner).
- **Check:** every block against `main` `70985971`, read-only code reading (`CODE_DERIVED`). The external sources in the blocks were not re-verified.

## How it was filed

- 12 of the 13 target issues (#1586, #1818 to #1829) were already closed, because their packages were built. Comments there would be lost, so each block for a closed issue went into a new follow-up issue that names the closed one and states only what is still open.
- Blocks for the same closed issue share one follow-up issue. Every other block got its own issue, and SIMULATE B6 went as a comment on the open #1528.
- PLAY B13 (reconnect, AI takeover) is filed inside #1901: the Studio is local with one human seat, and an AI takeover would decide for a seat, which needs its own Owner decision.
- SIMULATE B17 was not filed, because #1858 built it.
- Each filing starts with a „Prüfstand“ line: what exists (path:line), what is open, and any rule condition.
- The local report paths were replaced by „liegt lokal beim Owner“.

## Rule conditions recorded in the filings

- **Rules authority (AGENTS.md §2):** commander tax (PLAY B3, B9) only as published by the engine. Graying out unaffordable costs (B8) and „nothing real to do“ auto-pass (B11) only from the engine's legal options. Legality (B34) only through the XMage deck validator. Mulligan and range of influence (B27, B28) only as XMage game options. The interaction simulator (B30) only as an engine-driven seat.
- **Nothing goes outward (§12):** a shareable review link (PLAY B20), a spectator count for remote viewers (B29) and a hosted report share (SIMULATE B13) are out of scope; a local link or an export file is fine.
- **Hidden information (§5):** spectator perspectives (B29) and table rollback (B33) stay seat-scoped.
- **Simulation never feeds ratings (§1):** PLAY B23 counts only real games; SIMULATE B8 deltas stay `SIMULATED_RESULT`.
- **Language:** PLAY is English (Owner 2026-11-27); German example sentences in B10, B19 and B22 describe content, not wording.

## Block to filing

| Block | Filed as | Status on main |
|---|---|---|
| PLAY B1 | #1896 | TEILWEISE |
| PLAY B2 | #1896 | TEILWEISE |
| PLAY B3 | #1896 | TEILWEISE |
| PLAY B4 | #1896 | TEILWEISE |
| PLAY B5 | #1896 | TEILWEISE |
| PLAY B6 | #1897 | TEILWEISE |
| PLAY B7 | #1898 | UNKLAR/TEILWEISE |
| PLAY B8 | #1898 | TEILWEISE |
| PLAY B9 | #1898 | OFFEN |
| PLAY B10 | #1899 | TEILWEISE |
| PLAY B11 | #1900 | TEILWEISE |
| PLAY B12 | #1900 | OFFEN |
| PLAY B13 | in #1901 | EINGEORDNET |
| PLAY B14 | #1901 | TEILWEISE |
| PLAY B15 | #1902 | TEILWEISE |
| PLAY B16 | #1903 | TEILWEISE |
| PLAY B17 | #1904 | TEILWEISE |
| PLAY B18 | #1904 | TEILWEISE |
| PLAY B19 | #1905 | TEILWEISE |
| PLAY B20 | #1906 | TEILWEISE |
| PLAY B21 | #1907 | OFFEN |
| PLAY B22 | #1908 | OFFEN |
| PLAY B23 | #1909 | TEILWEISE |
| PLAY B24 | #1910 | OFFEN |
| PLAY B25 | #1911 | OFFEN |
| PLAY B26 | #1912 | OFFEN |
| PLAY B27 | #1913 | TEILWEISE |
| PLAY B28 | #1914 | TEILWEISE |
| PLAY B29 | #1915 | Auflage |
| PLAY B30 | #1916 | Regel-Auflage |
| PLAY B31 | #1917 | TEILWEISE |
| PLAY B32 | #1896 | TEILWEISE |
| PLAY B33 | #1918 | TEILWEISE |
| PLAY B34 | #1919 | Regel-Auflage |
| SIMULATE B1 | #1920 | TEILWEISE |
| SIMULATE B2 | #1920 | TEILWEISE |
| SIMULATE B3 | #1922 | TEILWEISE |
| SIMULATE B4 | #1921 | TEILWEISE |
| SIMULATE B5 | #1920 | TEILWEISE |
| SIMULATE B6 | #1528 comment 7237551624 | TEILWEISE |
| SIMULATE B7 | #1923 | TEILWEISE |
| SIMULATE B8 | #1924 | OFFEN |
| SIMULATE B9 | #1925 | OFFEN |
| SIMULATE B10 | #1926 | TEILWEISE |
| SIMULATE B11 | #1927 | TEILWEISE |
| SIMULATE B12 | #1928 | TEILWEISE |
| SIMULATE B13 | #1929 | OFFEN |
| SIMULATE B14 | #1930 | OFFEN |
| SIMULATE B15 | #1920 | TEILWEISE |
| SIMULATE B16 | #1920 | TEILWEISE |
| SIMULATE B17 | nicht eingereicht | ERLEDIGT (#1858) |
| SIMULATE B18 | #1931 | OFFEN |

Totals: 52 blocks; 50 filed (36 issues #1896 to #1931, 1 comment on #1528), 1 folded into #1901, 1 not filed (done in #1858).
