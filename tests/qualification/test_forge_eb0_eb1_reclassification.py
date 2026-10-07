"""E-B0 + E-B1 (#561): AF05 Forge matrix gap-label corrections, never credit.

E-B0: the Lab retains the bridge's stderr, so ``lab_capture.transport_diagnostics`` is
no longer a Lab gap; the channel stays PRESENT_UNAUDITED (retention is not an audit).
E-B1a: ``action_cost_state`` is a Lab execution gap (caused on the engine's own frames),
as ``forge_residuals`` already files it, not a provider construction channel.
E-B1b: a public exile object is a provider *construction* gap (the bootstrap cannot
place a card in exile); its readback is bindable by an exactly-one name rule, so the
UNOBSERVABLE finding is retired only when every requested exile object binds.
"""

from __future__ import annotations

import contextlib
import copy
import os
import signal
import sys
import textwrap
import time
from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary import bridge_launcher as B
from commander_lab.qualification.current_boundary import forge_hidden_information as fh
from commander_lab.qualification.current_boundary import forge_residuals as fr
from commander_lab.qualification.current_boundary import gate_derivations, knowledge_projection
from commander_lab.qualification.current_boundary.materialization import (
    load_effective_materialization,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "src/commander_lab/qualification/current_boundary/bridge_launcher.py"
COST_ROWS = {f"HIDDEN_{index:02d}" for index in range(5, 19)}
# The exact detail both Lab modules must file for action_cost_state (E-B1a). It is
# written out here so the agreement test has an independent expected value instead
# of comparing one module's derived copy against the other module's source.
EXPECTED_COST_STATE_DETAIL = (
    "mid-cast cost state is caused by casting and paying on the engine's own frames "
    "(the bootstrap has no cost field); the lane casts only through its causal stack route "
    "(#520, #561): complete, modeless spells with declared fuel, either one aimed at a "
    "commander for a commander zone choice to the graveyard, exile or hand, or a stack the "
    "record's scripted priority cast, targets and declared payment answer "
    "(scripted_decision_offered)"
)


@pytest.fixture(scope="module")
def records() -> dict[str, dict]:
    materialization = load_effective_materialization(REPO_ROOT)
    return {record["fixture_id"]: record for record in materialization.denominator_records()}


# --------------------------------------------------------------------------- E-B0


def _stub(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "stub_bridge.py"
    script.write_text(textwrap.dedent(body), encoding="utf-8")
    return script


def _process(script: Path) -> B.BridgeProcess:
    plan = B.LaunchPlan(
        candidate="forge",
        lane="stub",
        argv=(sys.executable, str(script)),
        cwd=script.parent,
        env_overrides={},
        expected_engine_commit="0" * 40,
        build_identity={},
        workspace="",
    )
    return B.launch(plan)


_CHATTY = """\
    import json, sys
    sys.stderr.write("[bridge] starting\\n")
    sys.stderr.flush()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        # Far more than one pipe buffer: an undrained pipe blocks this write.
        sys.stderr.write(("diag " + req["message_type"] + " " + "x" * 90 + "\\n") * 4000)
        sys.stderr.flush()
        sys.stdout.write(json.dumps({"request_id": req["request_id"], "ok": True}) + "\\n")
        sys.stdout.flush()
        if req["message_type"] == "shutdown_engine":
            sys.stderr.write("[bridge] exiting\\n")
            break
"""


def test_the_launcher_retains_the_whole_stderr_stream(tmp_path) -> None:
    proc = _process(_stub(tmp_path, _CHATTY))
    try:
        assert proc.request("handshake", {}, timeout_s=30.0)["ok"] is True
    finally:
        proc.close(timeout_s=30.0)
    capture = proc.stderr_capture()
    assert capture.complete is True
    assert capture.truncated is False
    assert capture.scannable is True
    assert capture.text.startswith("[bridge] starting\n")
    assert capture.text.endswith("[bridge] exiting\n")
    assert capture.text.count("diag handshake ") == 4000
    assert capture.text.count("diag shutdown_engine ") == 4000


def test_a_chatty_child_does_not_stall_on_an_undrained_pipe(tmp_path) -> None:
    """Before E-B0 nothing drained stderr: a child writing >64 KiB blocked forever."""
    proc = _process(_stub(tmp_path, _CHATTY))
    try:
        started = time.monotonic()
        assert proc.request("handshake", {}, timeout_s=15.0)["ok"] is True
        assert time.monotonic() - started < 15.0
    finally:
        proc.close(timeout_s=30.0)


def test_stderr_never_enters_the_persisted_transcript(tmp_path) -> None:
    proc = _process(_stub(tmp_path, _CHATTY))
    try:
        proc.request("handshake", {}, timeout_s=30.0)
    finally:
        proc.close(timeout_s=30.0)
    # Booleans, not the strings: a failing diff over megabytes of stderr is pathological.
    leaked = "diag handshake" in repr(proc.transcript)
    retained = "diag handshake" in proc.stderr_capture().text
    assert leaked is False
    assert retained is True


def test_an_over_limit_capture_is_marked_truncated_and_unscannable(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(B, "STDERR_RETAIN_LIMIT_CHARS", 1000)
    proc = _process(_stub(tmp_path, _CHATTY))
    try:
        proc.request("handshake", {}, timeout_s=30.0)
    finally:
        proc.close(timeout_s=30.0)
    capture = proc.stderr_capture()
    assert capture.complete is True
    assert capture.truncated is True
    assert capture.scannable is False
    assert len(capture.text) <= 1000


def test_a_live_capture_is_incomplete_and_unscannable(tmp_path) -> None:
    proc = _process(_stub(tmp_path, _CHATTY))
    try:
        proc.request("handshake", {}, timeout_s=30.0)
        live = proc.stderr_capture()
        assert live.complete is False
        assert live.scannable is False
    finally:
        proc.close(timeout_s=30.0)


def test_a_closed_stdout_still_reports_the_stderr_tail(tmp_path) -> None:
    script = _stub(
        tmp_path,
        """\
        import sys
        sys.stdin.readline()
        sys.stderr.write("fatal: engine boot failed\\n")
        sys.stderr.flush()
        """,
    )
    proc = _process(script)
    try:
        with pytest.raises(B.BridgeLaunchError, match="engine boot failed"):
            proc.request("handshake", {}, timeout_s=30.0)
    finally:
        proc.close(timeout_s=10.0)


def test_a_long_unterminated_stderr_line_is_retained_in_bounded_chunks(
    tmp_path, monkeypatch
) -> None:
    """E-B0 P3: a long line is drained in bounded chunks, not buffered whole."""
    monkeypatch.setattr(B, "STDERR_READ_CHUNK_BYTES", 1024)
    line = "y" * 5000
    script = _stub(
        tmp_path,
        f"""\
        import json, sys
        sys.stderr.write("{line}")
        sys.stderr.flush()
        for raw in sys.stdin:
            req = json.loads(raw)
            sys.stdout.write(json.dumps({{"request_id": req["request_id"], "ok": True}}) + "\\n")
            sys.stdout.flush()
            if req["message_type"] == "shutdown_engine":
                break
        """,
    )
    proc = _process(script)
    try:
        assert proc.request("handshake", {}, timeout_s=30.0)["ok"] is True
        # The unterminated line is visible while the child is still alive: a
        # blocking readline would hold it in an unbounded buffer until newline.
        deadline = time.monotonic() + 5.0
        while proc.stderr_capture().text != line and time.monotonic() < deadline:
            time.sleep(0.01)
        assert proc.stderr_capture().text == line
    finally:
        proc.close(timeout_s=30.0)
    capture = proc.stderr_capture()
    assert capture.complete is True
    assert capture.truncated is False
    assert capture.text == line


def test_a_descendant_held_pipe_does_not_leak_the_drain(tmp_path, monkeypatch) -> None:
    """E-B0 P3: close reclaims a drain a descendant's inherited pipe holds open."""
    monkeypatch.setattr(B, "STDERR_TAIL_WAIT_S", 0.5)
    script = _stub(
        tmp_path,
        """\
        import json, os, subprocess, sys
        descendant = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(300)"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
        )
        # stderr is inherited: the descendant holds the pipe after this process exits.
        with open(os.path.join(os.path.dirname(__file__), "descendant.pid"), "w") as pid:
            pid.write(str(descendant.pid))
        sys.stderr.write("[bridge] starting\\n")
        sys.stderr.flush()
        for raw in sys.stdin:
            req = json.loads(raw)
            sys.stdout.write(json.dumps({"request_id": req["request_id"], "ok": True}) + "\\n")
            sys.stdout.flush()
            break
        """,
    )
    pid_file = tmp_path / "descendant.pid"
    proc = _process(script)
    try:
        try:
            assert proc.request("handshake", {}, timeout_s=30.0)["ok"] is True
        finally:
            proc.close(timeout_s=5.0)
        # The direct child is gone; the descendant still holds stderr open. The
        # drain must be stopped and reclaimed, not pinned for the process life.
        assert proc._stderr_draining() is False
        capture = proc.stderr_capture()
        assert capture.text == "[bridge] starting\n"
        assert capture.complete is False
    finally:
        if pid_file.exists():
            with contextlib.suppress(ProcessLookupError, ValueError):
                os.kill(int(pid_file.read_text(encoding="utf-8")), signal.SIGTERM)


def test_a_closed_stdout_reports_only_complete_tail_lines(tmp_path) -> None:
    """E-B0 P3: the error tail must not start in the middle of a line."""
    script = _stub(
        tmp_path,
        """\
        import sys
        sys.stdin.readline()
        sys.stderr.write("first\\n" + "y" * 5000 + "\\nlast complete\\ntail partial")
        sys.stderr.flush()
        """,
    )
    proc = _process(script)
    try:
        with pytest.raises(B.BridgeLaunchError) as error:
            proc.request("handshake", {}, timeout_s=30.0)
    finally:
        proc.close(timeout_s=10.0)
    tail = str(error.value).split("(stderr tail: ", 1)[1].removesuffix(")")
    assert tail.startswith("last complete\n")
    assert "y" * 50 not in tail
    assert tail.endswith("tail partial")


def test_the_error_tail_drops_a_partial_first_line() -> None:
    """E-B0 P3: the tail helper keeps whole lines only."""
    assert B._stderr_tail("short\n", 100) == "short\n"
    lines = "".join(f"line {index:04d}\n" for index in range(500))
    tail = B._stderr_tail(lines, 100)
    assert tail
    assert lines.endswith(tail)
    assert all(line.startswith("line ") for line in tail.splitlines())
    assert B._stderr_tail("x" * 200, 100) == ""
    assert B._stderr_tail("head\n" + "x" * 200, 100) == ""


def test_the_error_tail_wait_is_one_bounded_budget(tmp_path, monkeypatch) -> None:
    """E-B0 P3: the tail collection shares one deadline instead of two serial waits."""
    monkeypatch.setattr(B, "STDERR_TAIL_WAIT_S", 2.0)
    script = _stub(
        tmp_path,
        """\
        import os, sys, time
        sys.stdin.readline()
        sys.stdout.flush()
        os.close(1)
        sys.stderr.write("still alive\\n")
        sys.stderr.flush()
        time.sleep(300)
        """,
    )
    proc = _process(script)
    try:
        started = time.monotonic()
        with pytest.raises(B.BridgeLaunchError, match="closed stdout"):
            proc.request("handshake", {}, timeout_s=5.0)
        assert time.monotonic() - started < 6.0
    finally:
        proc.popen.kill()
        proc.popen.wait(timeout=5)
        proc.close(timeout_s=1.0)


def test_transport_diagnostics_is_retained_not_a_lab_gap(records) -> None:
    assert fh.LAB_CAPTURE_GAPS == {}
    assert set(fh.LAB_CAPTURE_RETAINED) == {"transport_diagnostics"}
    assert set(fh.LAB_CAPTURE_ASSERTIONS) == set(fh.LAB_CAPTURE_GAPS) | set(fh.LAB_CAPTURE_RETAINED)
    fh.assert_lab_capture()
    for fixture in knowledge_projection.ROWS:
        row = fh.classify_row(records[fixture])
        assert not any(gap["dimension"].startswith("lab_capture.") for gap in row.lab_gaps)
        # Retention is not an audit: the row's channel scan still has to run.
        assert "transport_diagnostics" in row.unaudited_channels, fixture
        assert "lab_capture" not in row.reason(), fixture


@pytest.mark.parametrize(
    "edit",
    [
        # The drain thread is gone: stderr is piped and discarded again.
        lambda text: text.replace("target=self._drain_stderr", "target=None"),
        # stderr is no longer piped at all.
        lambda text: text.replace("stderr=subprocess.PIPE,", "stderr=subprocess.DEVNULL,"),
        # A direct read races the drain and can steal the stream.
        lambda text: text + "\nx = self.popen.stderr.read()[-2000:]\n",
        # The cap no longer marks truncation.
        lambda text: text.replace("self._stderr_truncated = True", "pass"),
        # EOF is no longer recorded, so a live capture would look complete.
        lambda text: text.replace("self._stderr_complete = True", "pass"),
    ],
)
def test_a_launcher_that_stops_retaining_stderr_is_drift(edit) -> None:
    launcher = LAUNCHER.read_text(encoding="utf-8")
    fh.assert_lab_capture(launcher)
    with pytest.raises(fh.HiddenChannelDrift, match="Lab capture"):
        fh.assert_lab_capture(edit(launcher))


@pytest.mark.parametrize(
    "edit",
    [
        # The bounded raw read is replaced by an unbounded one.
        lambda text: text.replace("os.read(fd, STDERR_READ_CHUNK_BYTES)", "os.read(fd, -1)"),
        # close() no longer stops a drain a descendant's pipe is holding open.
        lambda text: text.replace("self._stderr_stop.set()", "pass"),
    ],
)
def test_a_launcher_that_drops_the_capture_edges_is_drift(edit) -> None:
    launcher = LAUNCHER.read_text(encoding="utf-8")
    fh.assert_lab_capture(launcher)
    with pytest.raises(fh.HiddenChannelDrift, match="Lab capture"):
        fh.assert_lab_capture(edit(launcher))


def test_a_channel_cannot_be_both_gap_and_retained(monkeypatch) -> None:
    monkeypatch.setitem(fh.LAB_CAPTURE_GAPS, "transport_diagnostics", "stale gap")
    with pytest.raises(fh.HiddenChannelDrift, match="both"):
        fh.assert_lab_capture()


# --------------------------------------------------------------------------- E-B1a


def test_cost_state_is_a_lab_execution_gap(records) -> None:
    seen = set()
    for fixture in knowledge_projection.ROWS:
        row = fh.classify_row(records[fixture])
        assert all(gap["dimension"] != "action_cost_state" for gap in row.provider_gaps), fixture
        assert all(gap["channel"] != "cost_state_construction" for gap in row.provider_gaps)
        lab = [gap for gap in row.lab_gaps if gap["dimension"] == "action_cost_state"]
        if lab:
            seen.add(fixture)
            assert len(lab) == 1, fixture
            assert lab[0]["basis"] == fr.LAB_EXECUTION_GAP
            assert lab[0]["status"] == "UNSUPPORTED"
            assert "engine's own frames" in lab[0]["detail"]
            assert "action_cost_state" in row.reason().split("Lab Forge lane has no execution")[1]
        # No reclassification moves a row's class: the provider gaps remain.
        assert row.classification == fh.PROVIDER_ADAPTER_GAP, fixture
    assert seen == COST_ROWS


def test_both_modules_file_cost_state_the_same_way() -> None:
    """Independent expected value: both modules must file action_cost_state exactly so."""
    assert fh._LAB_DIMENSIONS == {"action_cost_state": EXPECTED_COST_STATE_DETAIL}
    assert fr._CONSTRUCTION["action_cost_state"] == (
        fr.LAB_EXECUTION_GAP,
        EXPECTED_COST_STATE_DETAIL,
    )
    assert "action_cost_state" not in fh._PROVIDER_DIMENSIONS


def test_a_cost_row_without_cost_state_drops_the_lab_entry(records) -> None:
    """Wrong-reason control: the entry follows the record, not the row id."""
    record = copy.deepcopy(records["HIDDEN_07"])
    record["action_cost_state"] = []
    row = fh.classify_row(record)
    assert all(gap["dimension"] != "action_cost_state" for gap in row.lab_gaps)
    assert row.classification == fh.PROVIDER_ADAPTER_GAP


# --------------------------------------------------------------------------- E-B1b


def _exile(semantic_id: str, name: str, owner: str = "P2", **extra) -> dict:
    return {
        "semantic_id": semantic_id,
        "card_identity": name,
        "owner": owner,
        "controller": owner,
        "zone": "exile",
        "face_down": False,
        **extra,
    }


def test_the_binder_binds_a_unique_name_exactly_once() -> None:
    objects = [_exile("obj:a", "Sol Ring"), _exile("obj:b", "Mox Opal", owner="P3")]
    readback = {"P2": ["Sol Ring", "Island"], "P3": ["Mox Opal"]}
    assert fh.bind_exile_identities(objects, readback) == {
        "obj:a": "Sol Ring",
        "obj:b": "Mox Opal",
    }


@pytest.mark.parametrize(
    ("objects", "readback"),
    [
        # Two requested objects share a name in one owner's exile: names cannot tell them apart.
        ([_exile("obj:a", "Sol Ring"), _exile("obj:b", "Sol Ring")], {"P2": ["Sol Ring"] * 2}),
        # Two requested objects, one readback card: both would bind the same card.
        ([_exile("obj:a", "Sol Ring"), _exile("obj:b", "Sol Ring")], {"P2": ["Sol Ring"]}),
        # The readback holds the name twice although one object was requested.
        ([_exile("obj:a", "Sol Ring")], {"P2": ["Sol Ring", "Sol Ring"]}),
        # The name is absent from the owner's exile.
        ([_exile("obj:a", "Sol Ring")], {"P2": ["Island"]}),
        # The name is in another owner's exile only.
        ([_exile("obj:a", "Sol Ring")], {"P3": ["Sol Ring"]}),
        # A face-down exiled card is named to nobody but its entitled viewers.
        ([_exile("obj:a", "Sol Ring", face_down=True)], {"P2": ["Sol Ring"]}),
        # Redaction placeholders never bind, whatever the record claims.
        ([_exile("obj:a", "<hidden>")], {"P2": ["<hidden>"]}),
        ([_exile("obj:a", "<face-down>")], {"P2": ["<face-down>"]}),
        # No card identity at all.
        ([_exile("obj:a", "")], {"P2": [""]}),
    ],
)
def test_the_binder_refuses_anything_but_exactly_one(objects, readback) -> None:
    bound = fh.bind_exile_identities(objects, readback)
    assert bound["obj:a"] is None


def test_public_exile_is_a_construction_gap_not_a_readback_limit(records) -> None:
    for fixture in knowledge_projection.ROWS:
        row = fh.classify_row(records[fixture])
        exile = [g for g in row.provider_gaps if g["dimension"] == "semantic_objects.zone:exile"]
        assert len(exile) == 1, fixture
        assert exile[0]["channel"] == "exile_construction"
        assert exile[0]["readback_binding"] == {"obj:public-exile": "Sol Ring"}
        unobservable = {gap["dimension"] for gap in row.unobservable}
        assert "semantic_objects.zone:exile" not in unobservable, fixture
        # The library is still never projected.
        assert "semantic_objects.zone:library" in unobservable, fixture
        assert "semantic_objects.zone:exile (exile_construction)" in row.reason()


def test_an_unbindable_exile_keeps_the_unobservable_finding(records) -> None:
    """Wrong-reason control: two same-named exile objects cannot be told apart by name."""
    record = copy.deepcopy(records["HIDDEN_01"])
    twin = copy.deepcopy(
        next(obj for obj in record["semantic_objects"] if obj.get("zone") == "exile")
    )
    twin["semantic_id"] = "obj:public-exile-twin"
    record["semantic_objects"].append(twin)
    row = fh.classify_row(record)
    exile = [g for g in row.provider_gaps if g["dimension"] == "semantic_objects.zone:exile"]
    assert len(exile) == 1
    assert exile[0]["readback_binding"] == {
        "obj:public-exile": None,
        "obj:public-exile-twin": None,
    }
    assert "semantic_objects.zone:exile" in {gap["dimension"] for gap in row.unobservable}


def test_a_bindable_exile_does_not_retire_a_face_down_siblings_limit(records) -> None:
    """M21 control: one bound face-up exile plus one face-down exile stays UNOBSERVABLE."""
    record = copy.deepcopy(records["HIDDEN_01"])
    public = next(obj for obj in record["semantic_objects"] if obj.get("zone") == "exile")
    face_down = copy.deepcopy(public)
    face_down["semantic_id"] = "obj:face-down-exile"
    face_down["card_identity"] = "Mystery Card"
    face_down["face_down"] = True
    record["semantic_objects"].append(face_down)
    row = fh.classify_row(record)
    exile = [g for g in row.provider_gaps if g["dimension"] == "semantic_objects.zone:exile"]
    assert len(exile) == 1
    assert exile[0]["readback_binding"] == {
        "obj:public-exile": "Sol Ring",
        "obj:face-down-exile": None,
    }
    # One bound sibling must not retire the limit the face-down object keeps.
    assert "semantic_objects.zone:exile" in {gap["dimension"] for gap in row.unobservable}


def test_a_record_without_exile_has_no_exile_entry(records) -> None:
    record = copy.deepcopy(records["HIDDEN_01"])
    record["semantic_objects"] = [
        obj for obj in record["semantic_objects"] if obj.get("zone") != "exile"
    ]
    row = fh.classify_row(record)
    assert all(g["dimension"] != "semantic_objects.zone:exile" for g in row.provider_gaps)
    assert all(g["dimension"] != "semantic_objects.zone:exile" for g in row.unobservable)


def test_the_exile_channels_are_bound_to_source() -> None:
    construction = fh.CHANNELS_BY_NAME["exile_construction"]
    assert construction.status == fh.CHANNEL_ABSENT
    assert construction.source == "bootstrap"
    assert construction.fields == fh.BOOTSTRAP_FIELDS
    readback = fh.CHANNELS_BY_NAME["exile_name_readback"]
    assert readback.status == fh.CHANNEL_SUPPORTED
    assert readback.source == "projection"
    # A readback fact satisfies no obligation: no row requires it.
    assert all(
        "exile_name_readback" not in fh.required_channels(kind)
        for kind in fh.OBSERVATION_REQUIREMENTS
    )


# --------------------------------------------------------------------------- never credit


def test_the_corrections_create_no_credit(records) -> None:
    documents = [fh.classify_row(records[f]).to_document() for f in knowledge_projection.ROWS]
    assert {doc["classification"] for doc in documents} == {fh.PROVIDER_ADAPTER_GAP}
    assert {doc["af05_effect"] for doc in documents} == {"UNKNOWN"}
    for doc in documents:
        assert "PASS" not in doc["reason"]
        assert {"event_log", "replay_transcript"} <= set(doc["missing_principal_channels"])
    rows = {
        fixture: {"exit_state": "UNKNOWN", "reason": fh.row_reason(records[fixture])}
        for fixture in knowledge_projection.ROWS
    }
    hidden_document = {"verdict": "PRINCIPAL_SCOPED", "credible_as_principal_scoped_evidence": True}
    assert gate_derivations.af05_hidden_information("forge", rows, hidden_document)["verdict"] == (
        "UNKNOWN"
    )
