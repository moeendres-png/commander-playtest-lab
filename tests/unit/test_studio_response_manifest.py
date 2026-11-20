"""The response manifest of the D-0 measuring net (``scripts/studio_response_manifest.py``, #1612).

A new file rather than an extension of ``test_studio_perf_equivalence.py``: that file is being
changed by an open pull request (#1611), and the tool tested here is a script, not a Studio
module. CI has no real store, so the end-to-end tests start a small stand-in ``commander_lab.studio``
package (a standard-library HTTP server written into ``tmp_path``) through the real process
start, copy, template guard, normalisation and stop of the tool; the real-store runs are in the
pull request.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "studio_response_manifest_under_test", ROOT / "scripts" / "studio_response_manifest.py"
)
assert spec and spec.loader
tool = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = tool  # dataclasses look their module up here
spec.loader.exec_module(tool)

INPUTS = tool.DeckInputs(
    "Chulane, Teller of Tales",
    "chulane",
    "chulane@1",
    (("c:cmd", 1, "commander"), ("c:a", 1, "main"), ("c:b", 1, "main"), ("c:c", 2, "main")),
)


def _json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def test_studio_manifest_asks_twenty_nine_distinct_read_routes_without_writes() -> None:
    """30 read routes until Q1-b2 (#1677) removed ``/api/rating-layers``."""
    requests = tool.read_requests(INPUTS)
    keys = [request.key for request in requests]
    assert len(keys) == 29
    assert len(set(keys)) == 29
    assert {request.method for request in requests} == {"GET", "POST"}
    paths = {request.path.split("?")[0] for request in requests}
    for route in (
        "/",
        "/tierliste.html",
        "/api/status",
        "/api/data-report",
        "/api/strength",
        "/api/universe/counted",
        "/api/revisions/chulane%401",
        "/api/packages",
    ):
        assert route in paths, route
    assert "commander=Chulane%2C%20Teller%20of%20Tales" in keys[4]
    assert "/api/rating-layers" not in paths
    assert "/api/layers" in paths  # data layers, a name trap: stays


def test_studio_write_matrix_covers_every_kind_of_user_state() -> None:
    names = [name for name, _request in tool.write_requests(INPUTS)]
    assert names == [
        "favorite",
        "mark",
        "label",
        "draft",
        "revision",
        "primer",
        "universe_profile",
    ]
    assert all(request.method in {"PUT", "POST"} for _n, request in tool.write_requests(INPUTS))


def _status(folder: object, cards: int = 3) -> bytes:
    return _json({"cards": cards, "image_cache": {"exists": False, "folder": folder}})


def test_studio_status_folder_of_the_run_is_normalised(tmp_path: Path) -> None:
    first, second = tmp_path / "one", tmp_path / "two"
    a, applied_a = tool.normalize("GET /api/status", _status(str(first / "images")), first)
    b, applied_b = tool.normalize("GET /api/status", _status(str(second / "images")), second)
    assert applied_a == applied_b == ["image_cache.folder"]
    assert a == b
    assert b"<STUDIO_DATA>/images" in a


def test_studio_status_folder_with_backslashes_survives_json_escaping(tmp_path: Path) -> None:
    folder = tmp_path / "C:\\Users\\owner\\Studio"
    body = _status(str(folder / "images"))
    assert b"\\\\" in body  # escaped in the JSON text
    normalised, applied = tool.normalize("GET /api/status", body, folder)
    assert applied == ["image_cache.folder"]
    assert json.loads(normalised)["image_cache"]["folder"] == "<STUDIO_DATA>/images"


def test_studio_normalisation_never_hides_another_difference(tmp_path: Path) -> None:
    one, two = tmp_path / "one", tmp_path / "two"
    a, _ = tool.normalize("GET /api/status", _status(str(one / "images"), cards=3), one)
    b, _ = tool.normalize("GET /api/status", _status(str(two / "images"), cards=4), two)
    assert a != b
    # a folder that is not this run's copy stays as served
    foreign, applied = tool.normalize("GET /api/status", _status("/elsewhere/images"), one)
    assert applied == []
    assert foreign == _status("/elsewhere/images")
    # other routes are never touched, even with the same field
    other = _status(str(one / "images"))
    assert tool.normalize("GET /api/data-report", other, one) == (other, [])


def test_studio_normalisation_refuses_a_body_that_does_not_reserialise(tmp_path: Path) -> None:
    body = b'{"image_cache": {"folder": null}}'  # spaces: not FastAPI's serialisation
    with pytest.raises(tool.ManifestError):
        tool.normalize("GET /api/status", body, tmp_path)


def _record(
    key: str, sha: str = "a" * 64, status: int = 200, length: int = 10
) -> dict[str, object]:
    return {"key": key, "status": status, "length": length, "sha256": sha, "stable": True}


def _manifest(records: list[dict[str, object]], deck: str = "chulane") -> dict[str, object]:
    return {"format": tool.FORMAT, "inputs": {"deck_id": deck}, "requests": records}


def test_studio_compare_reports_every_kind_of_difference() -> None:
    base = [_record("GET /a"), _record("GET /b")]
    assert tool.compare_manifests(_manifest(base), _manifest(list(base))) == []
    assert tool.compare_manifests(_manifest(base), _manifest([_record("GET /a")])) == [
        "only in A: GET /b"
    ]
    assert tool.compare_manifests(
        _manifest([_record("GET /a")]), _manifest([_record("GET /a"), _record("GET /c")])
    ) == ["only in B: GET /c"]
    for changed in (
        _record("GET /b", status=500),
        _record("GET /b", length=11),
        _record("GET /b", sha="b" * 64),
        {**_record("GET /b"), "stable": False},
    ):
        found = tool.compare_manifests(_manifest(base), _manifest([_record("GET /a"), changed]))
        assert len(found) == 1, found
        assert found[0].startswith("GET /b:")
    inputs = tool.compare_manifests(_manifest(base), _manifest(base, deck="other"))
    assert len(inputs) == 1
    assert inputs[0].startswith("inputs differ")
    with pytest.raises(tool.ManifestError):
        tool.compare_manifests({"format": "x"}, _manifest(base))


def test_studio_compare_command_exits_zero_or_one(tmp_path: Path) -> None:
    a, b, c = tmp_path / "a.json", tmp_path / "b.json", tmp_path / "c.json"
    a.write_text(json.dumps(_manifest([_record("GET /a")])), encoding="utf-8")
    b.write_text(json.dumps(_manifest([_record("GET /a")])), encoding="utf-8")
    c.write_text(json.dumps(_manifest([_record("GET /a", sha="c" * 64)])), encoding="utf-8")
    assert tool.main(["compare", str(a), str(b)]) == 0
    assert tool.main(["compare", str(a), str(c)]) == 1


# ---------- field comparison: answers that lose declared fields (Q1-b2 #1677, R5) ----------

BEFORE = {
    "cards": [{"id": "a", "tier": "S", "layers": {"tempo": 1}}, {"id": "b", "tier": "A"}],
    "layer_summary": {"pod_size": 4, "layers": []},
    "settings": {"bracket": "cedh", "layer_weights": {"tempo": 0.0}, "pod_size": 4},
    "notices": [],
}
AFTER = {
    "cards": [{"id": "a", "tier": "S"}, {"id": "b", "tier": "A"}],
    "settings": {"bracket": "cedh"},
    "notices": [],
}
REMOVED = ["cards[]/layers", "layer_summary", "settings/layer_weights", "settings/pod_size"]


def test_studio_key_paths_join_keys_and_merge_list_items() -> None:
    assert tool.key_paths(BEFORE) >= {
        "cards",
        "cards[]/id",
        "cards[]/layers",
        "cards[]/layers/tempo",
        "layer_summary/pod_size",
        "settings/layer_weights/tempo",
    }
    assert tool.key_paths([1, {"x": [{"y": 2}]}]) == {"[]/x", "[]/x[]/y"}
    assert tool.key_paths(3) == set()


def test_studio_fields_pass_when_exactly_the_declared_paths_are_removed() -> None:
    assert tool.field_check(BEFORE, AFTER, REMOVED) == []
    assert tool.value_differences(tool.prune(BEFORE, REMOVED), AFTER) == []


def test_studio_fields_fail_on_an_added_field() -> None:
    """The fixture pair with one extra field is red (acceptance of #1677)."""
    added = {**AFTER, "settings": {"bracket": "cedh", "new_flag": True}}
    assert tool.field_check(BEFORE, added, REMOVED) == ["added: settings/new_flag"]


def test_studio_fields_fail_on_an_undeclared_or_a_still_present_field() -> None:
    assert tool.field_check(BEFORE, AFTER, REMOVED[:-1]) == [
        "removed, not declared: settings/pod_size"
    ]
    kept = {**AFTER, "layer_summary": {"pod_size": 4, "layers": []}}
    assert tool.field_check(BEFORE, kept, REMOVED) == ["declared, still present: layer_summary"]
    assert tool.field_check(BEFORE, AFTER, [*REMOVED, "nowhere"]) == [
        "declared, not in the answer before: nowhere"
    ]
    # a field removed from one list item only is still present in the merged path
    partly = {**AFTER, "cards": [{"id": "a", "tier": "S", "layers": {}}, {"id": "b", "tier": "A"}]}
    assert tool.field_check(BEFORE, partly, REMOVED) == [
        "removed, not declared: cards[]/layers/tempo",
        "declared, still present: cards[]/layers",
    ]


def test_studio_values_outside_the_removed_paths_must_stay_equal() -> None:
    changed = {**AFTER, "cards": [{"id": "a", "tier": "A"}, {"id": "b", "tier": "A"}]}
    assert tool.field_check(BEFORE, changed, REMOVED) == []  # keys alone cannot see it
    assert tool.value_differences(tool.prune(BEFORE, REMOVED), changed) == ["cards[0]/tier"]
    shorter = {**AFTER, "cards": AFTER["cards"][:1]}
    assert tool.value_differences(tool.prune(BEFORE, REMOVED), shorter) == ["cards (length 2 != 1)"]
    assert tool.value_differences(1, 1.0) == ["<root>"]  # the JSON type counts


def test_studio_fields_command_exits_zero_or_one(tmp_path: Path) -> None:
    before, after, extra = tmp_path / "b.json", tmp_path / "a.json", tmp_path / "x.json"
    before.write_text(json.dumps(BEFORE), encoding="utf-8")
    after.write_text(json.dumps(AFTER), encoding="utf-8")
    extra.write_text(json.dumps({**AFTER, "more": 1}), encoding="utf-8")
    declared = [arg for path in REMOVED for arg in ("--removed", path)]
    assert tool.main(["fields", str(before), str(after), *declared, "--values"]) == 0
    assert tool.main(["fields", str(before), str(extra), *declared]) == 1
    assert tool.main(["fields", str(before), str(after), *declared[:-2]]) == 1


def test_studio_manifest_never_lands_in_the_repository(tmp_path: Path) -> None:
    with pytest.raises(tool.ManifestError):
        tool.check_out_path(ROOT / "manifest.json", [ROOT])
    assert tool.check_out_path(tmp_path / "manifest.json", [ROOT]) is None


def test_studio_store_copy_refuses_overlap_and_leaves_the_template_alone(tmp_path: Path) -> None:
    template = tmp_path / "template"
    template.mkdir()
    (template / "studio.sqlite3").write_bytes(b"database")
    before = tool.template_fingerprint(template)
    with pytest.raises(tool.ManifestError):
        tool.copy_store(template, template)
    with pytest.raises(tool.ManifestError):
        tool.copy_store(template, template / "copy")
    copy = tool.copy_store(template, tmp_path / "work" / "store")
    (copy / "studio.sqlite3").write_bytes(b"written by the server")
    assert tool.template_fingerprint(template) == before
    (template / "studio.sqlite3").write_bytes(b"changed")
    assert tool.template_fingerprint(template) != before
    with pytest.raises(tool.ManifestError):
        tool.copy_store(tmp_path / "missing", tmp_path / "x")


_FAKE_SERVER = """
import json, os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DATA = Path(os.environ["COMMANDER_LAB_STUDIO_DATA"])
FOLDER = os.environ.get("FAKE_STUDIO_FOLDER") or str(DATA / "images")


def dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def answer(self, body, status=200):
        self.send_response(status)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.path.startswith("/api/"):
            return self.answer(b"<html>" + self.path.encode() + b"</html>")
        if self.path == "/api/status":
            database = (DATA / "studio.sqlite3").read_bytes().decode()
            return self.answer(dump({"database": database, "image_cache": {"folder": FOLDER}}))
        if self.path == "/api/decks":
            return self.answer(dump([{"deck_id": "chulane",
                "branches": [{"branch": "main", "revision_id": "chulane@1"}]}]))
        if self.path == "/api/revisions/chulane%401":
            cards = [{"card_id": c, "quantity": 1, "zone": z} for c, z in
                     (("c:cmd", "commander"), ("c:a", "main"), ("c:b", "main"), ("c:c", "main"))]
            return self.answer(dump({"cards": cards}))
        return self.answer(dump({"path": self.path}))

    def do_POST(self):
        length = int(self.headers.get("content-length") or 0)
        body = json.loads(self.rfile.read(length) or b"null")
        if self.headers.get("x-studio") != "1":
            return self.answer(b"{}", 403)
        return self.answer(dump({"path": self.path, "body": body}))

    do_PUT = do_POST


port = int(sys.argv[sys.argv.index("--port") + 1])
ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
"""


def _fake_src(tmp_path: Path) -> Path:
    src = tmp_path / "fake_src"
    package = src / "commander_lab" / "studio"
    package.mkdir(parents=True)
    (src / "commander_lab" / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "__main__.py").write_text(textwrap.dedent(_FAKE_SERVER), encoding="utf-8")
    return src


def _template(tmp_path: Path) -> Path:
    template = tmp_path / "template"
    template.mkdir()
    (template / "studio.sqlite3").write_text("store-v1", encoding="utf-8")
    return template


def test_studio_two_runs_on_fresh_copies_give_the_same_manifest(tmp_path: Path) -> None:
    src, template = _fake_src(tmp_path), _template(tmp_path)
    before = tool.template_fingerprint(template)
    manifests = []
    for run in ("one", "two"):
        out = tmp_path / f"manifest_{run}.json"
        code = tool.main(
            ["run", "--store", str(template), "--out", str(out), "--src", str(src),
             "--work-dir", str(tmp_path / f"work_{run}"), "--start-timeout", "60"]
        )  # fmt: skip
        assert code == 0
        assert not (tmp_path / f"work_{run}" / "store").exists(), "the copy is removed"
        manifests.append(json.loads(out.read_text(encoding="utf-8")))
    first, second = manifests
    assert len(first["requests"]) == 29
    status = next(r for r in first["requests"] if r["key"] == "GET /api/status")
    assert status["normalized"] == ["image_cache.folder"]
    assert (
        status["raw_sha256"]
        != next(r for r in second["requests"] if r["key"] == "GET /api/status")["raw_sha256"]
    ), "the raw answers differ by the copy folder"
    assert first["inputs"]["revision_id"] == "chulane@1"
    assert first["run"]["template_database_sha256"] == before["studio.sqlite3"]["sha256"]
    assert tool.compare_manifests(first, second) == []
    assert tool.template_fingerprint(template) == before

    # a different store gives a different manifest
    (template / "studio.sqlite3").write_text("store-v2", encoding="utf-8")
    out = tmp_path / "manifest_three.json"
    assert tool.main(
        ["run", "--store", str(template), "--out", str(out), "--src", str(src),
         "--start-timeout", "60", "--repeat", "1"]
    ) == 0  # fmt: skip
    third = json.loads(out.read_text(encoding="utf-8"))
    assert tool.compare_manifests(first, third) == [
        f"GET /api/status: sha256 {status['sha256']!r} != "
        f"{next(r for r in third['requests'] if r['key'] == 'GET /api/status')['sha256']!r}"
    ]


def test_studio_run_stops_when_the_server_reports_another_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src, template = _fake_src(tmp_path), _template(tmp_path)
    monkeypatch.setenv("FAKE_STUDIO_FOLDER", str(tmp_path / "owner_store" / "images"))
    out = tmp_path / "manifest.json"
    code = tool.main(
        ["run", "--store", str(template), "--out", str(out), "--src", str(src),
         "--start-timeout", "60"]
    )  # fmt: skip
    assert code == 3
    assert not out.exists()


def test_studio_write_matrix_compares_running_and_restarted_server(tmp_path: Path) -> None:
    src, template = _fake_src(tmp_path), _template(tmp_path)
    out = tmp_path / "writes.json"
    code = tool.main(
        ["writes", "--store", str(template), "--out", str(out), "--src", str(src),
         "--start-timeout", "60", "--writes", "favorite,primer"]
    )  # fmt: skip
    result = json.loads(out.read_text(encoding="utf-8"))
    assert code == 0, result
    assert result["ok"] is True
    assert [step["write"] for step in result["steps"]] == ["favorite", "primer"]
    assert all(step["differences"] == [] for step in result["steps"])
    assert len(result["steps"][0]["warm"]) == 32
    assert result["steps"][0]["warm"][-3]["key"] == "GET /api/decks/chulane/primer"


def _run_args(template: Path, out: Path, src: Path, *extra: str) -> list[str]:
    return [
        "run", "--store", str(template), "--out", str(out), "--src", str(src),
        "--start-timeout", "60", "--repeat", "1", *extra,
    ]  # fmt: skip


def test_studio_run_never_deletes_a_template_inside_the_work_dir(tmp_path: Path) -> None:
    """``--store X/store --work-dir X``: refused before anything is copied or removed."""
    src = _fake_src(tmp_path)
    work = tmp_path / "x"
    template = work / "store"
    template.mkdir(parents=True)
    (template / "studio.sqlite3").write_text("store-v1", encoding="utf-8")
    (template / "keep.txt").write_text("owner data", encoding="utf-8")
    before = tool.template_fingerprint(template)
    code = tool.main(_run_args(template, tmp_path / "m.json", src, "--work-dir", str(work)))
    assert code == 2
    assert tool.template_fingerprint(template) == before


def test_studio_run_never_deletes_a_store_folder_it_did_not_create(tmp_path: Path) -> None:
    src, template = _fake_src(tmp_path), _template(tmp_path)
    work = tmp_path / "work"
    (work / "store").mkdir(parents=True)
    (work / "store" / "keep.txt").write_text("someone else's", encoding="utf-8")
    code = tool.main(_run_args(template, tmp_path / "m.json", src, "--work-dir", str(work)))
    assert code == 2
    assert (work / "store" / "keep.txt").read_text(encoding="utf-8") == "someone else's"


def test_studio_run_reports_a_changed_template_even_when_the_run_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src, template = _fake_src(tmp_path), _template(tmp_path)

    def broken(base: str, commander: str, deck_id: str) -> object:
        (template / "studio.sqlite3").write_text("changed", encoding="utf-8")
        raise tool.ManifestError("deck missing")

    monkeypatch.setattr(tool, "resolve_inputs", broken)
    assert tool.main(_run_args(template, tmp_path / "m.json", src)) == 3


def test_studio_single_file_template_is_copied_with_its_wal(tmp_path: Path) -> None:
    folder = tmp_path / "t"
    folder.mkdir()
    (folder / "owner.sqlite3").write_bytes(b"main")
    (folder / "owner.sqlite3-wal").write_bytes(b"wal")
    assert set(tool.template_fingerprint(folder / "owner.sqlite3")) == {
        "owner.sqlite3",
        "owner.sqlite3-wal",
    }
    copy = tool.copy_store(folder / "owner.sqlite3", tmp_path / "copy")
    assert (copy / "studio.sqlite3").read_bytes() == b"main"
    assert (copy / "studio.sqlite3-wal").read_bytes() == b"wal"


def test_studio_inputs_record_the_commander_lab_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMMANDER_LAB_TOPDECK_DIR", "/data/topdeck")
    monkeypatch.setenv("COMMANDER_LAB_STUDIO_DATA", "/set/by/the/tool")
    environment = INPUTS.record()["environment"]
    assert environment["COMMANDER_LAB_TOPDECK_DIR"] == "/data/topdeck"
    assert "COMMANDER_LAB_STUDIO_DATA" not in environment
    a = {"format": tool.FORMAT, "inputs": INPUTS.record(), "requests": []}
    monkeypatch.setenv("COMMANDER_LAB_TOPDECK_DIR", "/other")
    b = {"format": tool.FORMAT, "inputs": INPUTS.record(), "requests": []}
    assert tool.compare_manifests(a, b)[0].startswith("inputs differ")
