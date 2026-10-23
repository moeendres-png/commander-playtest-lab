# T-3: AppCDS in the evidence lanes (#961), measured and dropped

T-3 of #961 asked for the start flags of the sweeps (serial GC and an AppCDS archive of the
bridge jar) in the evidence lanes too. Serial GC shipped as E1 in the v12 repin (#969) and showed
no measurable PB-03 gain. This note measures the archive part and drops it for the evidence
lanes. Sweeps keep using it (`--fast`, `docs/performance/XMAGE_EFFICIENCY_OFFENSIVE_2026-10-21.md`).

## Measurement (`LOCAL_OBSERVED`, 4 cores, JDK 17, bridge jar `c5c019a2`, pin `4da83f62`)

Evidence lanes play one game per bridge JVM, so the measurement is one game per JVM:
`benchmark_xmage_full_games.py run --seeds 1-4 --workers 1 --games-per-jvm 1`, once with serial GC
only (A) and once with serial GC and the archive (`--fast`, B). Order A B B A after one cold pair
that is not counted. Raw tables: `measurements-2026-10-23/t3/`.

| | Wall, 4 games | Child CPU, 4 games |
|---|---:|---:|
| A (serial GC) | 208.8 s, 198.8 s (mean 203.8) | 359.5 s, 345.0 s (mean 352.3) |
| B (serial GC + archive) | 199.2 s, 202.5 s (mean 200.9) | 330.4 s, 333.2 s (mean 331.8) |
| Difference | -1.4 % | -5.8 % |

The semantic transcript hashes of all 24 games are identical with and without the archive.

## Why it is dropped for the evidence lanes

- The wall gain, 0.7 s per game, is below the 3 % bar of T-1 (dropped at -2 % wall; the runbook
  says a lever below the agreed bar is dropped and written down). The CPU gain, 5 CPU-seconds per game, goes to idle cores, not to
  the time a lane takes.
- The archive has to be trained once per jar: 36 s of build in the measurement above. If PB-03 started one
  bridge JVM for each of its 107 scenarios (not checked here; the authoritative runner takes about
  23 of the 32 minutes of run 39927923126), 107 starts at 0.7 s would save about 75 s and the build
  would cost 36 s: a net gain of about 40 s of 32 minutes, as an upper bound.
- It adds a failure mode to the lane that decides qualification. The JVM recognises a changed jar
  by path, size and modification time only; a mismatch makes it run without the archive and write a
  warning, which must be kept off the protocol's stdout (`build_xmage_cds_archive.py` documents
  this). A change to the PB-03 launch plan also changes the trigger files of PB-03 and needs a
  requalification (PB-03 and a seal).

So the launch flags of the evidence lanes stay as they are (serial GC from E1). The sweep lanes
keep the archive; their gain is large (batching amortises the build, `-37 %` wall in the
efficiency note). A remaining candidate for PB-03 time is the 2 min 43 s "Build pinned XMage"
step, which the Meta Qualification workflow no longer pays after C-1 (#983); doing the same in
PB-03 is a change to a qualification workflow and stays an Owner decision.
