# RQ-X1 — Test Corpus Inventory (DIRECTLY_VERIFIED counts; semantics CODE_DERIVED)

Pin: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c`. Clean tree. No builds, no
runs, no imports. Counts are static file/annotation counts — methodology
signal only, NEVER Rules authority, NEVER correctness evidence.

## 1. Raw counts (commands + results; all DIRECTLY_VERIFIED by worker unless noted)

| # | Command (workdir `/tmp/rq-xmage-src`) | Result |
|---|---|---|
| 1 | `find Mage.Tests/src/test -name '*Test.java' \| wc -l` | **1957** |
| 2 | `find . -path '*/src/test*' -name '*Test.java' \| wc -l` | **1977** repo-wide (Mage.Tests 1957 + Mage 7 + Server 2 + Client 7 + Common 2) |
| 3 | `find . -path '*/src/test*' -name '*.java' \| wc -l` | 2040 (test-tree java files) |
| 4 | `rg -N '^\s*@Test\b' Mage.Tests/src/test -g '*.java' --no-filename \| wc -l` | **6851** strict `@Test` (CODE_DERIVED count, worker re-ran: confirmed 6851) |
| 5 | `rg -N '^\s*@Test\b' Mage Mage.Server Mage.Client Mage.Common --glob '*.java' --no-filename \| wc -l` | 135 outside Mage.Tests ⇒ **~6986 repo-wide** (CODE_DERIVED) |
| 6 | `rg -o '@ParameterizedTest\|@TestFactory\|@RepeatedTest'` | 0 — plain JUnit4 `@Test` only |
| 7 | per-package file counts (`org.mage.test/*/`) | cards 1817 · serverside 38 · commander 33 · AI 28 · multiplayer 18 · utils 15 · combat 12 · decks 16 · game 5 · player 5 · testapi 5 · rollback 7 · mulligan 7 · load 4 (CODE_DERIVED) |
| 8 | per-package `@Test` | cards ~6109 (~89%) · commander 81 · multiplayer 69 · combat 101 · AI 137 · serverside 130 · utils 64 · game 19 · rollback 15 · mulligan 29 · testapi 30 (CODE_DERIVED) |
| 9 | `rg -l -i 'CommanderFreeForAll\|CommanderDuel\|EDH' … \| wc -l` | 60 files touch Commander concepts (broad) |
| 10 | `rg -l 'MultiPlayer\|FreeForAll\|TwoHeadedGiant\|RangeOfInfluence' … \| wc -l` | 62 files (broad) |
| 11 | `rg -l 'choose(\|chooseTarget\|chooseMode\|…\|setChoice' … \| wc -l` | 1160 files use the decision-scripting DSL (broad) |
| 12 | `rg -l -i 'Random\|shuffle\|dice\|coin\|flip\|roll' … \| wc -l` | 441 files (broad; dedicated RNG tests are 3 files, §3) |
| 13 | `rg -l 'GameView\|CardView\|…\|faceDown\|reveal' … \| wc -l` | 134 files (broad; dedicated view test is 1 file, §3) |

Top files by `@Test` (CODE_DERIVED): `MutateTest` 134 · modal-D
...[truncated 6158 chars]