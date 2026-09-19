"""WS218 capability truth for the semantic replay tape lane.

``replay_supported`` is True ONLY for the versioned tape lane after the
full record/export/fresh-consume/semantic-compare/fail-closed contract is
qualified (positive 2-5P plus tamper matrix). A mere exporter or a
same-seed twin never flips this flag. The generic bridge
``replay_supported`` stays False (no ``export_replay`` on the full-game
lane); this module is the single truthful advertisement for tape replay.

Qualification: WS218 2026-09-15 — 2P(611)/3P(155)/4P(257)/5P(158) Lions
tapes, each dual fresh-process replay PASS, 19-case tamper matrix all
fail-closed, hidden-info/process-isolation evidenced. See
qualification/ws218-semantic-replay-tape-v1/.
"""

from __future__ import annotations

TAPE_REPLAY_LANE = "semantic-replay-tape/1.0.0 over xmage_full_game_external_pilots"
TAPE_REPLAY_SUPPORTED = True
TAPE_REPLAY_QUALIFICATION = "WS218_20260915_2P611_3P155_4P257_5P158_DUAL_REPLAY_PASS_TAMPER19_FAIL_CLOSED"

__all__ = ["TAPE_REPLAY_LANE", "TAPE_REPLAY_QUALIFICATION", "TAPE_REPLAY_SUPPORTED"]
