# Forge bridge integration point

Pinned upstream: `forge-2.0.13` / commit
`852066bf4f761b302ed17cb011999d8a8fe08ad6`.

Forge remains a separate-process GPL-3.0 differential backend. This directory
contains no claimed Forge runtime. A real bridge must expose protocol 1.0.0 and
report actual capabilities rather than assumed ones.
