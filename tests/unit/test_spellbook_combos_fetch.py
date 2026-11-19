"""Unit tests for the Spellbook fetch script's variant selection (issue #1378)."""

from __future__ import annotations

import gzip
import io
import json
from pathlib import Path

import pytest
import scripts.spellbook_combos_fetch as fetch
from scripts.spellbook_combos_fetch import _select_variants, _Variant

_COMMANDER = "Chulane, Teller of Tales"
_CORPUS_KEYS = {"card alpha", "card beta"}


def _variant(variant_id: str, produces: tuple[str, ...]) -> _Variant:
    return _Variant(
        variant_id=variant_id,
        identity="WUG",
        status="OK",
        spoiler=False,
        commander_legal=True,
        names=("Card Alpha", "Card Beta"),
        foreign_commander=False,
        produces=produces,
        edhrec_decks=None,
    )


def test_produceless_variant_does_not_consume_its_card_set() -> None:
    facts = [_variant("0001", ()), _variant("0002", ("Infinite mana",))]
    generated, counts = _select_variants(
        facts,
        corpus_keys=set(_CORPUS_KEYS),
        preserved_sets=set(),
        commander=_COMMANDER,
        note="test note",
    )
    assert [entry["combo_id"] for entry in generated] == ["chulane-sb-0002"]
    assert counts["no_produces"] == 1
    assert counts["same_cardset_merged"] == 0
    assert counts["kept"] == 1


def test_duplicate_of_a_kept_variant_still_merges() -> None:
    facts = [_variant("0001", ("Infinite mana",)), _variant("0002", ("Infinite mana",))]
    generated, counts = _select_variants(
        facts,
        corpus_keys=set(_CORPUS_KEYS),
        preserved_sets=set(),
        commander=_COMMANDER,
        note="test note",
    )
    assert [entry["combo_id"] for entry in generated] == ["chulane-sb-0001"]
    assert counts["same_cardset_merged"] == 1
    assert counts["kept"] == 1


# --- network gate, size limits and incremental reading (issue #1546, review of #1618) ---


def _bulk_variant(index: int) -> dict[str, object]:
    return {
        "id": f"v-{index}",
        "identity": "WUG",
        "status": "OK",
        "spoiler": False,
        "legalities": {"commander": True},
        "popularity": index,
        "uses": [
            {"card": {"name": "Card Alpha"}, "mustBeCommander": False},
            {"card": {"name": f"Card {index}"}, "mustBeCommander": False},
        ],
        "produces": [{"feature": {"name": "Infinite mana"}}],
    }


def _document(count: int) -> dict[str, object]:
    return {
        "timestamp": "2026-11-18T00:00:00Z",
        "variants": [_bulk_variant(i) for i in range(count)],
    }


class _FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, declared: str | None = None) -> None:
        super().__init__(body)
        self.headers = {} if declared is None else {"Content-Length": declared}
        self.status = 200
        self.read_calls = 0

    def read(self, size: int | None = -1) -> bytes:
        self.read_calls += 1
        return super().read(size)

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class _Net:
    """A urlopen stand-in that records every call."""

    def __init__(self, response: _FakeResponse | None = None) -> None:
        self.calls: list[str] = []
        self.response = response

    def __call__(self, request: object, timeout: float = 0.0) -> _FakeResponse:
        self.calls.append(str(getattr(request, "full_url", request)))
        if self.response is None:
            raise AssertionError("no network access expected")
        return self.response


def test_no_network_without_allow_network_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    net = _Net()
    monkeypatch.setattr(fetch, "_open_url", net)
    with pytest.raises(SystemExit, match="--allow-network"):
        fetch._load_bulk_variants(None, commander=_COMMANDER)
    assert net.calls == []


def test_command_line_without_bulk_and_flag_exits_before_store_and_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    net = _Net()
    monkeypatch.setattr(fetch, "_open_url", net)

    def no_store(*args: object, **kwargs: object) -> None:
        raise AssertionError("store opened before the network gate")

    monkeypatch.setattr(fetch.StudioStore, "open", no_store)
    monkeypatch.setattr(
        fetch.sys,
        "argv",
        ["spellbook_combos_fetch.py", "--data", "x", "--retrieved-at", "2026-11-19"],
    )
    with pytest.raises(SystemExit) as stop:
        fetch.main()
    assert "--allow-network" in str(stop.value)
    assert net.calls == []


def test_allowed_download_is_streamed_to_a_file_and_parsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = gzip.compress(json.dumps(_document(3)).encode("utf-8"))
    net = _Net(_FakeResponse(body, declared=str(len(body))))
    monkeypatch.setattr(fetch, "_open_url", net)
    facts = fetch._load_bulk_variants(None, commander=_COMMANDER, allow_network=True)
    assert [fact.variant_id for fact in facts] == ["v-0", "v-1", "v-2"]
    assert facts[2].edhrec_decks == 2
    assert net.calls == [fetch.DEFAULT_BULK_URL]


def test_declared_oversize_download_is_refused_before_the_body_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _FakeResponse(b"x" * 10, declared=str(5 * fetch.MIB))
    monkeypatch.setattr(fetch, "_open_url", _Net(response))
    with pytest.raises(SystemExit, match="declared size"):
        fetch._load_bulk_variants(
            None, commander=_COMMANDER, allow_network=True, max_download_bytes=fetch.MIB
        )
    assert response.read_calls == 0


def test_undeclared_oversize_download_stops_at_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _FakeResponse(b"x" * (3 * fetch.MIB))
    monkeypatch.setattr(fetch, "_open_url", _Net(response))
    with pytest.raises(SystemExit, match="exceeds the limit"):
        fetch._load_bulk_variants(
            None, commander=_COMMANDER, allow_network=True, max_download_bytes=fetch.MIB
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://json.commanderspellbook.com/variants.json.gz",
        "https://example.invalid/variants.json.gz",
        "https://backend.commanderspellbook.com/variants/",
        "https://data.scryfall.io/oracle-cards/x.json",
        "https://user:pw@json.commanderspellbook.com/variants.json.gz",
        "https://json.commanderspellbook.com:8443/variants.json.gz",
        "https://json.commanderspellbook.com.evil.example/variants.json.gz",
        "file:///etc/passwd",
    ],
)
def test_bulk_url_outside_the_allowlist_is_refused_without_a_request(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    net = _Net()
    monkeypatch.setattr(fetch, "_open_url", net)
    with pytest.raises(SystemExit, match="refused"):
        fetch._load_bulk_variants(None, bulk_url=url, commander=_COMMANDER, allow_network=True)
    assert net.calls == []


def test_command_line_refuses_a_foreign_bulk_url_before_store_and_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    net = _Net()
    monkeypatch.setattr(fetch, "_open_url", net)

    def no_store(*args: object, **kwargs: object) -> None:
        raise AssertionError("store opened before the URL check")

    monkeypatch.setattr(fetch.StudioStore, "open", no_store)
    monkeypatch.setattr(
        fetch.sys,
        "argv",
        [
            "x",
            "--data",
            "d",
            "--retrieved-at",
            "2026-11-19",
            "--allow-network",
            "--bulk-url",
            "https://example.invalid/v.gz",
        ],
    )
    with pytest.raises(SystemExit, match="refused"):
        fetch.main()
    assert net.calls == []


def test_a_redirect_is_not_followed(tmp_path: Path) -> None:
    import http.server
    import threading
    import urllib.error
    import urllib.request

    hits: list[str] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            hits.append(self.path)
            if self.path == "/start":
                self.send_response(302)
                self.send_header("Location", "/elsewhere")
                self.end_headers()
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"followed")

        def log_message(self, *args: object) -> None:
            return None

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/start")
        with pytest.raises(urllib.error.HTTPError) as stop:
            fetch._open_url(request, 5)
        assert stop.value.code == 302
        stop.value.close()
    finally:
        server.shutdown()
        server.server_close()
    assert hits == ["/start"]


def test_user_agent_cannot_be_chosen_on_the_command_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        fetch.sys,
        "argv",
        ["x", "--data", "d", "--retrieved-at", "2026-11-19", "--user-agent", "anything"],
    )
    with pytest.raises(SystemExit) as stop:
        fetch.main()
    assert stop.value.code == 2  # argparse: unrecognized argument


def test_written_provenance_holds_no_local_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "Users" / "someone" / "Downloads"
    folder.mkdir(parents=True)
    bulk = folder / "variants.json"
    bulk.write_text(json.dumps(_document(2)), encoding="utf-8")
    combos = tmp_path / "combos.json"
    combos.write_text(json.dumps({"combos": []}), encoding="utf-8")
    monkeypatch.setattr(fetch.StudioStore, "open", lambda *a, **k: object())
    monkeypatch.setattr(fetch, "_corpus_keys", lambda *a, **k: ({"card alpha", "card 0"}, 3))
    monkeypatch.setattr(
        fetch.sys,
        "argv",
        [
            "x",
            "--data",
            str(tmp_path),
            "--combos",
            str(combos),
            "--bulk",
            str(bulk),
            "--retrieved-at",
            "2026-11-19",
        ],
    )
    assert fetch.main() == 0
    written = combos.read_text(encoding="utf-8")
    assert json.loads(written)["provenance"]["extension_1378"]["endpoint"] == "variants.json"
    assert str(tmp_path) not in written
    assert "Downloads" not in written and "someone" not in written


def test_gzip_bomb_is_stopped_by_the_unpacked_limit(tmp_path: Path) -> None:
    padding = " " * (4 * fetch.MIB)
    text = (
        '{"variants": ['
        + json.dumps(_bulk_variant(1))
        + ","
        + padding
        + json.dumps(_bulk_variant(2))
        + "]}"
    )
    bomb = tmp_path / "bomb.json.gz"
    bomb.write_bytes(gzip.compress(text.encode("utf-8")))
    assert bomb.stat().st_size < fetch.MIB  # tiny on disk, big when unpacked
    with pytest.raises(SystemExit, match="unpacks to more than"):
        fetch._load_bulk_variants(bomb, commander=_COMMANDER, max_unpacked_bytes=fetch.MIB)
    # the same file under a sufficient limit still parses
    facts = fetch._load_bulk_variants(bomb, commander=_COMMANDER, max_unpacked_bytes=16 * fetch.MIB)
    assert len(facts) == 2


@pytest.mark.parametrize("compressed", [False, True])
@pytest.mark.parametrize("layout", ["pretty", "compact", "bare_list"])
def test_incremental_reader_handles_layouts_and_chunk_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, layout: str, compressed: bool
) -> None:
    monkeypatch.setattr(fetch, "CHUNK_CHARS", 64)  # force objects across many chunk borders
    monkeypatch.setattr(fetch, "COMPACT_AFTER", 128)
    document = _document(12)
    if layout == "bare_list":
        text = json.dumps(document["variants"])
    elif layout == "compact":
        text = json.dumps(document, separators=(",", ":"))
    else:
        text = json.dumps(document, indent=2)
    raw = text.encode("utf-8")
    path = tmp_path / ("v.json.gz" if compressed else "v.json")
    path.write_bytes(gzip.compress(raw) if compressed else raw)
    facts = fetch._load_bulk_variants(path, commander=_COMMANDER)
    assert [fact.variant_id for fact in facts] == [f"v-{i}" for i in range(12)]
    assert facts[11].edhrec_decks == 11


def test_truncated_or_listless_bulk_documents_are_refused(tmp_path: Path) -> None:
    cut = json.dumps(_document(3))[:-40]
    truncated = tmp_path / "cut.json"
    truncated.write_text(cut, encoding="utf-8")
    with pytest.raises(SystemExit):
        fetch._load_bulk_variants(truncated, commander=_COMMANDER)
    listless = tmp_path / "none.json"
    listless.write_text('{"timestamp": "x"}', encoding="utf-8")
    with pytest.raises(SystemExit, match="variants"):
        fetch._load_bulk_variants(listless, commander=_COMMANDER)
