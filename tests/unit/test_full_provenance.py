from __future__ import annotations

import pytest

from commander_lab.models import (
    SourceRecord,
    SourceType,
    SupersessionRecord,
)


def test_synthetic_assumption_not_observed():
    with pytest.raises(ValueError):
        SourceRecord(
            source_id="s",
            source_type=SourceType.SYNTHETIC_ASSUMPTION,
            title="x",
            content_hash="0" * 64,
            observed=True,
        )


def test_lower_authority_cannot_supersede():
    with pytest.raises(ValueError):
        SupersessionRecord(
            supersession_id="x",
            old_id="a",
            new_id="b",
            reason="x",
            authority_rank_old=5,
            authority_rank_new=4,
        )
