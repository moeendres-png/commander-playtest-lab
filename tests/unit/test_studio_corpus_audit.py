"""Read-only corpus audit (Refs #1549). All data here is synthetic."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from commander_lab.studio import StudioStore
from commander_lab.studio.corpus_audit import REASONS, audit_decks, corpus_audit
from commander_lab.studio.data_report import data_report

TODAY = date(2026, 11, 19)
CHULANE = "o-chulane"


def _store(tmp_path: Path) -> StudioStore:
    store = StudioStore.open(tmp_path / "studio")
    db = store.connection
    db.execute(
        "INSERT INTO source VALUES ('src:s', 'scryfall', 't', 'x', ?, NULL, '2026-11-16')",
        ("2026-11-10",),
    )
    cards = [
        (CHULANE, "Chulane, Teller of Tales", "WUG", "legal"),
        ("o-ok", "Fine Card", "G", "legal"),
        ("o-banned", "Banned Card", "G", "banned"),
        ("o-red", "Red Card", "R", "legal"),
        ("o-odd", "Odd Card", "G", "unknown"),
    ]
    for oid, name, colours, legality in cards:
        db.execute(
            "INSERT INTO scryfall_card(oracle_id, scryfall_id, name, front_name, layout, "
            "color_identity, commander_legality, keywords, produced_mana, source_id) "
            "VALUES (?, ?, ?, ?, 'normal', ?, ?, '[]', '[]', 'src:s')",
            (oid, oid, name, name, colours, legality),
        )
    return store


def _deck(
    store: StudioStore,
    deck_id: str,
    tags: list[str],
    main: list[tuple[str, int]],
    commander: str | None = CHULANE,
    duplicate_of: str | None = None,
) -> None:
    db = store.connection
    db.execute(
        "INSERT INTO corpus_deck VALUES (?, 'chulane', '', 'edhrec', 'community', NULL, '[]', ?, "
        "?, 'not_audited', 'src:s')",
        (deck_id, deck_id, duplicate_of),
    )
    for tag in tags:
        db.execute("INSERT INTO corpus_cohort VALUES (?, ?)", (tag, deck_id))
    rows = [("commander", commander, 1)] if commander else []
    rows += [("main", oid, qty) for oid, qty in main]
    for section, oid, qty in rows:
        db.execute(
            "INSERT INTO corpus_deck_card VALUES (?, ?, ?, ?, ?, 'ok')",
            (deck_id, f"n-{oid}", oid, qty, section),
        )


def _build(store: StudioStore) -> None:
    _deck(store, "legal", ["bracket:3", "source:edhrec"], [("o-ok", 99)])
    _deck(store, "banned", ["bracket:3", "source:edhrec"], [("o-ok", 98), ("o-banned", 1)])
    _deck(store, "colour", ["bracket:2", "source:edhrec"], [("o-ok", 98), ("o-red", 1)])
    _deck(store, "short", ["source:archidekt"], [("o-ok", 98)])
    _deck(store, "nocmd", ["bracket:2"], [("o-ok", 99)], commander="o-ok")
    _deck(store, "odd", ["bracket:2"], [("o-ok", 98), ("o-odd", 1)])
    _deck(store, "dupe", ["bracket:2"], [("o-ok", 99)], duplicate_of="legal")


def test_four_constructed_decks_and_unknown(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _build(store)
    result = audit_decks(store.connection)
    assert "dupe" not in result
    assert result["legal"].status == "ohne_befund"
    assert result["banned"].reasons == ["card_not_legal"]
    assert result["colour"].reasons == ["outside_identity"]
    assert result["short"].reasons == ["card_count_not_100"]
    assert result["nocmd"].reasons == ["commander_not_chulane"]
    assert result["odd"].status == "unbekannt"
    assert result["odd"].unmeasured == ["card_not_legal"]


def _extra(store: StudioStore, deck_id: str, section: str, oid: str, qty: int = 1) -> None:
    store.connection.execute(
        "INSERT INTO corpus_deck_card VALUES (?, ?, ?, ?, ?, 'ok')",
        (deck_id, f"n-{oid}", oid, qty, section),
    )


def test_companion_and_sideboard_stay_outside_the_100(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _deck(store, "comp", [], [("o-ok", 99)])
    _extra(store, "comp", "companion", "o-red")
    _extra(store, "comp", "sideboard", "o-banned")
    result = audit_decks(store.connection)["comp"]
    assert result.status == "ohne_befund"
    assert result.reasons == []


def test_chulane_only_in_main_is_not_the_commander(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _deck(store, "inmain", [], [(CHULANE, 1), ("o-ok", 98)], commander="o-ok")
    assert audit_decks(store.connection)["inmain"].reasons == ["commander_not_chulane"]


def test_card_without_scryfall_row_is_not_measurable(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _deck(store, "norow", [], [("o-ok", 98), ("o-nowhere", 1)])
    result = audit_decks(store.connection)["norow"]
    assert result.status == "unbekannt"
    assert result.reasons == []
    assert result.unmeasured == ["card_not_legal", "outside_identity"]


def test_deck_without_card_rows_is_not_measurable(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _deck(store, "empty", [], [], commander=None)
    result = audit_decks(store.connection)["empty"]
    assert result.status == "unbekannt"
    assert result.has_cards is False
    assert result.unmeasured == list(REASONS)
    assert corpus_audit(store.connection, today=TODAY)["decks_with_card_rows"] == {
        "count": 0,
        "of": 1,
    }


def test_notes_explain_tokens(tmp_path: Path) -> None:
    notes = corpus_audit(_store(tmp_path).connection, today=TODAY)["notes"]
    assert any("token" in n for n in notes)  # type: ignore[attr-defined]


def test_counts_cohorts_and_no_writes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _build(store)
    db = store.connection
    before = db.execute("SELECT deck_id, legality_audit FROM corpus_deck ORDER BY 1").fetchall()
    section = corpus_audit(db, today=TODAY)
    assert section["decks_counted"] == {"count": 6, "of": 7}
    assert section["status"] == {"befund": 4, "unbekannt": 1, "ohne_befund": 1, "of": 6}
    by_reason = section["by_reason"]
    assert by_reason["card_not_legal"] == {"count": 1, "of": 6, "not_measurable": 1}  # type: ignore[index]
    dims = section["by_cohort_dimension"]
    assert dims["bracket"]["3"] == {"decks": 2, "befund": 1, "unbekannt": 0, "ohne_befund": 1}  # type: ignore[index]
    assert dims["bracket"]["unbekannt"]["decks"] == 1  # type: ignore[index]
    assert dims["source"]["unbekannt"]["decks"] == 2  # type: ignore[index]
    assert section["card_facts_snapshot_date"] == "2026-11-10"
    assert section["card_facts_age_days"] == 9
    assert (
        db.execute("SELECT deck_id, legality_audit FROM corpus_deck ORDER BY 1").fetchall()
        == before
    )
    assert data_report(store, today=TODAY)["corpus_audit"] == section


def test_unknown_instead_of_zero_without_facts(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    section = corpus_audit(store.connection, today=TODAY)
    assert section["decks_counted"] == {"count": 0, "of": 0}
    assert section["card_facts_snapshot_date"] == "unbekannt"


STATIC = Path(__file__).resolve().parents[2] / "src" / "commander_lab" / "studio" / "static"


def test_corpus_audit_route_is_the_report_section_and_writes_nothing(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    from fastapi.testclient import TestClient

    from commander_lab.studio.web import create_app

    store = _store(tmp_path)
    _build(store)
    store.connection.commit()
    before = store.connection.execute(
        "SELECT deck_id, legality_audit FROM corpus_deck ORDER BY 1"
    ).fetchall()
    store.close()
    client = TestClient(create_app(tmp_path / "studio"), headers={"X-Studio": "1"})
    got = client.get("/api/corpus-audit")
    assert got.status_code == 200
    body = got.json()
    reopened = StudioStore.open(tmp_path / "studio")
    expected = corpus_audit(reopened.connection, today=datetime.now(UTC).date())
    assert {k: v for k, v in body.items() if k != "card_facts_age_days"} == {
        k: v for k, v in expected.items() if k != "card_facts_age_days"
    }
    assert body["status"] == {"befund": 4, "unbekannt": 1, "ohne_befund": 1, "of": 6}
    assert client.get("/api/corpus-audit").content == got.content  # remembered, same bytes
    # counts only: no card name, no deck address
    assert "Fine Card" not in got.text and "Banned Card" not in got.text
    assert (
        reopened.connection.execute(
            "SELECT deck_id, legality_audit FROM corpus_deck ORDER BY 1"
        ).fetchall()
        == before
    )
    reopened.close()


def test_corpus_audit_js_is_hooked_in_and_free_of_unsafe_patterns() -> None:
    js = (STATIC / "corpusaudit.js").read_text(encoding="utf-8")
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    assert '<script src="corpusaudit.js"></script>' in index
    assert index.index("corpusaudit.js") < index.index('<script src="app.js">')
    assert "mountCorpusAudit(" in app_js and "corpus-audit-slot" in app_js
    for forbidden in (".innerHTML", ".outerHTML", "eval(", "style=", "style:", ".toFixed("):
        assert forbidden not in js
    assert "toLocaleString" not in js  # numbers only through StudioUI.num


def _audit_js(calls: str) -> object:
    """Run corpusaudit.js under node with a tiny DOM stub and return ``calls`` as JSON."""
    import json
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed: corpusaudit.js rendering NOT RUN, not a pass")
    script = (
        "const StudioUI = {num: (v, d = 0) => Number(v).toLocaleString('de-DE', "
        "{minimumFractionDigits: d, maximumFractionDigits: d})};\n"
        "const h = (tag, attrs, ...kids) => ({tag, attrs, kids: kids.flat()});\n"
        "const text = (n) => (n === null || n === undefined) ? '' : typeof n === 'string' ? n : "
        "(n.kids || []).map(text).join('|');\n"
        "const makeSlot = () => ({nodes: null, replaceChildren(...n) { this.nodes = n; }, "
        "text() { return this.nodes === null ? null : this.nodes.map(text).join('||'); }});\n"
        "const cohortName = (key) => 'NAME ' + key;\n"
        + (STATIC / "corpusaudit.js").read_text(encoding="utf-8")
        + f"\n(async () => {{ const out = await ({calls}); "
        "process.stdout.write(JSON.stringify(out)); })();\n"
    )
    out = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, timeout=30, check=True
    )
    return json.loads(out.stdout)


_ANSWER = (
    '{schema: "studio-corpus-audit-1", status: {befund: 4, unbekannt: 1, ohne_befund: 1, of: 6},'
    " by_reason: {card_count_not_100: {count: 1, of: 6, not_measurable: 0},"
    " card_not_legal: {count: 1, of: 6, not_measurable: 1}},"
    " by_cohort_dimension: {source: {edhrec: {decks: 3, befund: 2, unbekannt: 0, ohne_befund: 1},"
    " unbekannt: {decks: 2, befund: 0, unbekannt: 1, ohne_befund: 1}},"
    ' bracket: {"3": {decks: 2, befund: 1, unbekannt: 0, ohne_befund: 1}}, variant: {}},'
    ' card_facts_snapshot_date: "2026-11-10", card_facts_age_days: 9}'
)


def test_corpus_audit_js_shows_n_of_n_and_unknown_never_zero() -> None:
    out = _audit_js(
        "(async () => {"
        f" const answer = {_ANSWER};"
        " const ok = makeSlot();"
        " await mountCorpusAudit(ok, {h, cohortName, commander: 'Chulane, Teller of Tales',"
        "   api: async () => answer});"
        " const other = makeSlot();"
        " await mountCorpusAudit(other, {h, cohortName, commander: 'Someone Else',"
        "   api: async () => { throw new Error('must not be asked'); }});"
        " const undated = makeSlot();"
        " renderCorpusAudit(undated, {...answer, card_facts_snapshot_date: 'unbekannt',"
        "   card_facts_age_days: 'unbekannt'}, {h, cohortName});"
        " const bad = makeSlot();"
        " renderCorpusAudit(bad, {schema: 'other'}, {h, cohortName});"
        " return {ok: ok.text(), other: other.text(), undated: undated.text(), bad: bad.text()};"
        "})()"
    )
    ok = out["ok"]  # type: ignore[index]
    assert "Von 6 gezählten Quelldecks haben 4 einen Befund, 1 sind" in ok
    assert "nicht 100 Karten: 1 von 6" in ok
    assert "Karte nicht legal (auch Spielstein-Zeilen): 1 von 6, 1 nicht messbar" in ok
    assert "NAME source:edhrec" in ok and "davon 2 von 3 mit Befund" in ok
    assert "NAME bracket:3" in ok and "davon 1 von 2 mit Befund" in ok
    assert "ohne Angabe (unbekannt)" in ok  # a deck without a value is its own row
    assert "Stand der Kartenfakten: 2026-11-10 (9 Tage alt)." in ok
    assert "Decks mit Befund bleiben in jeder Zahl oben mitgezählt" in ok
    assert out["other"] is None  # type: ignore[index]  # another commander: slot untouched
    assert "Stand der Kartenfakten: unbekannt" in out["undated"]  # type: ignore[index]
    assert "unbekannt (Antwort nicht lesbar)" in out["bad"]  # type: ignore[index]


def test_corpus_audit_js_names_a_failed_load_as_unknown_and_retries() -> None:
    out = _audit_js(
        "(async () => {"
        f" const answer = {_ANSWER}; let calls = 0;"
        " const api = async () => { calls += 1; if (calls === 1) throw new Error('x'); return answer; };"
        " const first = makeSlot();"
        " await mountCorpusAudit(first, {h, cohortName, commander: 'Chulane, Teller of Tales', api});"
        " const second = makeSlot();"
        " await mountCorpusAudit(second, {h, cohortName, commander: 'Chulane, Teller of Tales', api});"
        " return {first: first.text(), second: second.text(), calls};"
        "})()"
    )
    assert "unbekannt (nicht geladen)" in out["first"]  # type: ignore[index]
    assert "Von 6 gezählten Quelldecks" in out["second"]  # type: ignore[index]
    assert out["calls"] == 2  # type: ignore[index]
