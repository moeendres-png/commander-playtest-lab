# Native mana production: matched game evidence, 2026-11-06

The bridge exposes an advisory, engine-derived palette for the exact unrestricted
board-color mana ability, and the pilot uses validated hints for payment planning and
ranking. Native legal options remain authoritative. This is `ENGINE_NATIVE_REUSE`:
the bridge queries a copy of the native ability against the public board; the pilot does
not reconstruct which permanents determine the colors. Restricted or unsupported modes
receive no such hint. The hint does not establish whether conditional mana can pay a
particular cost.

## Local matched games

These are `DIRECTLY_VERIFIED` local observations, not qualification or CI results. The
baseline is main `7c3a9530`; the candidate uses the frozen four-file runtime recorded in
the [measurement](measurements-2026-11-06/native-mana-production-summary.json). Each
pair used the same frozen public decks and assets, seed 1, and one worker. The runner
checked input and JAR digests, streamed records to compressed archives, and verified
the archive contents and counts. Candidate and baseline JARs contain the same 49,798
pinned engine class contents. Game trajectories may diverge after a different decision.

| Pod | Baseline decisions / cancellations | Candidate decisions / cancellations |
| --- | ---: | ---: |
| 4-player 000 | 1,892 / 0 | 1,892 / 0 |
| 6-player 002 | 4,511 / 16 | 4,282 / 2 |

In the six-player game, Arcane Denial had 9 canceled payments and Destroy Evil 6 at
baseline; both had zero in the candidate. The other baseline cancellation was Captain
America. The candidate had one Captain America and one Hormagaunt Horde cancellation.
The newly observed cancellation illustrates why the total and the two affected cards
are reported separately, without claiming elimination of payment failures.

Among six-player mana-payment decisions, each Plaza of Heroes mode was offered 61 times
at baseline and 43 times in the candidate. The board-color mode was selected 0 and 2
times, the legendary-spell-restricted mode 16 and 1, and colorless 3 and 2. The native
palette was offered 40 times and selected twice. On one selection the offered palette was
red and the subsequent decision spent red. On the other, for Destroy Evil, the palette
was white/red; the pilot chose white, spent white and colorless, and then received
priority with Destroy Evil on the stack. These are after-payment observations, not merely
in-flight selections. Record indices and archive hashes are in the measurement.

The control semantic transcript hash and winner match the baseline. Reported cast
selections were 35 to 35 in the control and 59 to 62 in the six-player pair; these
exclude canceled attempts but do not count resolved spells.

The native build completed Maven verify with 1,164 tests, zero failures or errors, and
one skipped. The focused Python suite passed 91 tests; broader Python checks passed 211
tests, and mypy and the repository Ruff checks passed. Independent review found no
blocking P1/P2 issue; that review was `CODE_DERIVED`, not a runtime test. These two
games do not establish playing strength or a causal speed change. Wall times in the
measurement are descriptive, with shared CPU. A separate four-player 005 baseline hit
an out-of-memory limit at 768 MiB; it is not part of this matched comparison.
