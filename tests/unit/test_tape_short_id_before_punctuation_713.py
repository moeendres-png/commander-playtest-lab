"""#713: the WS218 tape path strips XMage's process-local short-id tag wherever
the engine appends it, not only at the end of the text.

``redact_text`` kept the tag when the message continued past it ("Cast
Siege-Gang Commander [3a4]?"), so two processes with the same seed produced
different ``option_fingerprint`` digests for the same Rules option -- the defect
#710/#712 fixed in the full-game runner's ``_semantic_text``.

Impact adjudication (recorded on #713): the change only removes more of the same
process-local noise and is a strict superset of the old rewriting. Every string
stored in the sealed WS218 tapes is byte-identical under the old and the new
function (proved below), and sealed fingerprints are never recomputed from live
labels (the meta-qualification consumer records a fresh tape and replays it with
the same code). ``CANONICALIZATION_VERSION`` therefore stays 1.0.0: the declared
contract always excluded process-local identity; the old behaviour violated it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from commander_lab.engine.rules.full_game import XmageFullGameRunner
from commander_lab.semantic_replay import canonicalization
from commander_lab.semantic_replay.canonicalization import redact_choice_text, redact_text
from commander_lab.semantic_replay.fingerprint import option_fingerprint

REPO_ROOT = Path(__file__).resolve().parents[2]
TAPES = sorted((REPO_ROOT / "qualification/ws218-semantic-replay-tape-v1/tapes").glob("*.json"))


def _old_redact_text(value: object) -> object:
    """The pre-#713 function, reconstructed from the unchanged module patterns."""
    if not isinstance(value, str):
        return value
    text = canonicalization._OBJECT_ID_ATTR_RE.sub("", value)
    text = canonicalization._UUID_RE.sub("<engine-object>", text)
    text = canonicalization._SHORT_ID_SUFFIX_RE.sub(r"\1", text)
    text = canonicalization._SHORT_ID_TAIL_RE.sub("", text)
    return text


def _label_option(label: str) -> dict:
    return {"option_type": "boolean", "label": label, "metadata": {}}


def test_red_control_labels_from_710_fingerprint_identically() -> None:
    """Red on the pre-#713 function: the two twins' digests differed."""
    first = "Cast Siege-Gang Commander [3a4]?"
    second = "Cast Siege-Gang Commander [14d]?"
    assert _old_redact_text(first) != _old_redact_text(second), "the defect being fixed"
    assert redact_text(first) == redact_text(second) == "Cast Siege-Gang Commander?"
    assert option_fingerprint(_label_option(first)) == option_fingerprint(_label_option(second))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "Change this 1 of 1 target: Siege-Gang Commander [3a4]?",
            "Change this 1 of 1 target: Siege-Gang Commander?",
        ),
        (
            "<font color='x'>Llanowar Elves</font> [0b1c2d3e] attacks",
            "<font color='x'>Llanowar Elves</font> attacks",
        ),
        ("Sacrifice Goblin [abc], then draw", "Sacrifice Goblin, then draw"),
        ("<b>Bear</b>[a1b2] enters", "<b>Bear</b> enters"),
        ("Grizzly Bears [3a4]", "Grizzly Bears"),
    ],
)
def test_appended_tags_are_stripped_wherever_the_engine_puts_them(raw: str, expected: str) -> None:
    assert redact_text(raw) == expected


@pytest.mark.parametrize(
    "rules_text",
    [
        "Choose [Mountain] or [Forest]",  # not hex
        "Pay {X}[ab12]x",  # tag glued to a following word char: not an appended tag
        "Mode [cafe-babe]",  # not the 3-8 hex shape
    ],
)
def test_genuine_bracketed_text_survives(rules_text: str) -> None:
    assert redact_text(rules_text) == rules_text


def test_parity_with_the_full_game_runner_on_the_710_shapes() -> None:
    samples = [
        "Cast Siege-Gang Commander [3a4]?",
        "Change this 1 of 1 target: Siege-Gang Commander [3a4]?",
        "<font color='x'>Llanowar Elves</font> [0b1c2d3e] attacks",
        "Sacrifice Goblin [abc], then draw",
    ]
    checked = list(samples)
    assert checked, "nothing was checked: samples is empty"
    for sample in checked:
        assert redact_text(sample) == XmageFullGameRunner._semantic_text(sample), sample


def test_new_patterns_only_remove_further_appended_tags() -> None:
    """The new patterns run on the old output and only remove more appended tags."""
    unchanged = [
        "<font>Name</font> [3a4]",
        "Name [3a4]</div>",
        "Name[3a4]",
        "x object_id='abc' y",
        "uuid 12345678-1234-1234-1234-123456789abc here",
        "Choose [Mountain] or [Forest]",
    ]
    for sample in unchanged:
        assert redact_text(sample) == _old_redact_text(sample), sample
    # Where they must differ: a tag the old end-of-text pattern left mid-message.
    assert _old_redact_text("A [3a4] B [5b6]") == "A [3a4] B"
    assert redact_text("A [3a4] B [5b6]") == "A B"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(" Pay [100].", " Pay."), ("Choose [add] mode", "Choose mode")],
)
def test_accepted_hex_shaped_bracket_text_is_stripped_like_the_runner(raw, expected) -> None:
    """Recorded limitation, accepted in #712: hex-shaped bracket words read as tags."""
    assert redact_text(raw) == expected == XmageFullGameRunner._semantic_text(raw)


def _strings(node: object):
    if isinstance(node, dict):
        for value in node.values():
            yield from _strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _strings(value)
    elif isinstance(node, str):
        yield node


def test_sealed_ws218_tapes_are_byte_identical_under_old_and_new() -> None:
    """Impact adjudication: no stored tape string changes under the new function.

    The tapes store selected labels only; offered-but-unchosen labels and metadata
    behind the sealed digests are not stored. That is safe because sealed digests are
    compared, never recomputed from labels (live replay re-derives fresh tapes only).
    """
    assert len(TAPES) == 4
    tag = re.compile(r"\[[0-9a-fA-F]{3,8}\]")
    checked = 0
    for tape in TAPES:
        document = json.loads(tape.read_text(encoding="utf-8"))
        for value in _strings(document):
            checked += 1
            assert redact_text(value) == _old_redact_text(value), (tape.name, value)
            assert redact_choice_text(value) == _old_choice(value), (tape.name, value)
            assert not tag.search(value), (tape.name, value)
    assert checked > 9000


def _old_choice(value: object) -> object:
    redacted = _old_redact_text(value)
    if not isinstance(redacted, str):
        return redacted
    return canonicalization._CHOICE_SHORT_ID_RE.sub(" [#]", redacted)
