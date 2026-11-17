"""Static guards for the Studio pages: no literal 'null' children, no price wording, labelled inputs."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "src" / "commander_lab" / "studio" / "static"
PRICE_WORDS = re.compile(r"\b(preis\w*|kaufen|zukauf|price\w*|buy)\b|€", re.IGNORECASE)


def _files(pattern: str) -> list[Path]:
    found = sorted(STATIC.glob(pattern))
    assert found, pattern
    return found


def _replace_children_calls(source: str) -> list[tuple[int, str, str]]:
    """(line, arguments, top-level text) of every .replaceChildren( call; the top-level text
    holds only what sits directly in the argument list, not inside nested calls or strings."""
    found: list[tuple[int, str, str]] = []
    for match in re.finditer(r"\.replaceChildren\(", source):
        start = match.end()
        depth, pos, quote, top = 1, start, "", []
        while pos < len(source):
            char = source[pos]
            if quote:
                if char == "\\":
                    pos += 2
                    continue
                if char == quote:
                    quote = ""
            elif char in "\"'`":
                quote = char
            elif char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
                if depth == 0:
                    break
            elif depth == 1:
                top.append(char)
            pos += 1
        found.append((source.count("\n", 0, match.start()) + 1, source[start:pos], "".join(top)))
    return found


def test_replace_children_never_receives_a_bare_null() -> None:
    # replaceChildren turns a null argument into the text "null"; a call whose own argument
    # list can contain null must spread through the kids() filter.
    offenders: list[str] = []
    checked = 0
    for path in _files("*.js"):
        for line, arguments, top in _replace_children_calls(path.read_text(encoding="utf-8")):
            checked += 1
            if not arguments.lstrip().startswith("...") and re.search(r"\bnull\b", top):
                offenders.append(f"{path.name}:{line}")
    assert checked > 50
    assert offenders == []


def test_no_price_wording_in_pages_and_scripts() -> None:
    for path in [*_files("*.html"), *_files("*.js")]:
        text = path.read_text(encoding="utf-8")
        hits = PRICE_WORDS.findall(text)
        assert not hits, f"{path.name}: {hits}"


def test_every_text_input_and_select_has_a_name() -> None:
    tag = re.compile(r"<(input|select|textarea)\b([^>]*)>", re.IGNORECASE)
    unlabeled: list[str] = []
    for path in _files("*.html"):
        text = path.read_text(encoding="utf-8")
        for match in tag.finditer(text):
            attrs = match.group(2)
            if re.search(r'type="(checkbox|radio|hidden|button)"', attrs):
                continue
            ident = re.search(r'id="([^"]+)"', attrs)
            labelled = "aria-label" in attrs or "title=" in attrs
            if not labelled:
                before = text[: match.start()]
                labelled = before.rfind("<label") > before.rfind(
                    "</label>"
                )  # wrapped in an open <label>
            if not labelled:
                unlabeled.append(f"{path.name}:{ident.group(1) if ident else match.group(1)}")
    assert unlabeled == []


def test_decimals_go_through_the_german_number_helpers() -> None:
    """No raw .toFixed( or .toPrecision( in any Studio deckbuilder/tierliste script: the de-DE
    helpers StudioUI.num / StudioUI.pct / StudioUI.numFlex / StudioUI.numSig are the only place
    that formats decimals (comma, not point, and typographic minus)."""
    excluded: set[str] = set()
    scripts = [
        path
        for path in _files("*.js")
        if path.name not in excluded and not path.name.startswith("partie")
    ]
    assert len(scripts) >= 10
    for path in scripts:
        text = path.read_text(encoding="utf-8")
        assert ".toFixed(" not in text and ".toPrecision(" not in text, path.name
    ui = (STATIC / "ui.js").read_text(encoding="utf-8")
    assert 'toLocaleString("de-DE"' in ui and "num, pct" in ui and "numSig" in ui
    assert 'class: "num"' in (STATIC / "app.js").read_text(encoding="utf-8")


def test_bridge_chip_shows_plain_german_with_raw_code_in_tooltip() -> None:
    sources = {
        n: (STATIC / n).read_text(encoding="utf-8") for n in ("ui.js", "app.js", "paired.js")
    }
    assert len(sources) == 3
    for name, text in sources.items():
        assert "Engine-Stand noch nicht qualifiziert" in text, name
        assert 'label = "BRIDGE_AHEAD_OF_QUALIFICATION"' not in text


def test_deck_browser_reset_returns_to_the_source_only_default() -> None:
    """The reset button must restore the default origin ("Nur Quelldecks"): resetting to the mixed
    origin would count saved Studio decks into the source-deck denominator."""
    text = (STATIC / "decks.js").read_text(encoding="utf-8")
    assert 'state.origin = $("db-origin").value' in text
    reset = text.split('$("db-reset").addEventListener', 1)[1].split("});", 1)[0]
    assert '$("db-origin").value = "source"' in reset
    html = (STATIC / "decks.html").read_text(encoding="utf-8")
    select = html.split('<select id="db-origin">', 1)[1].split("</select>", 1)[0]
    assert select.strip().startswith('<option value="source">')  # first option = the default


def test_small_window_filter_fold_and_compact_evidence_panel() -> None:
    """The second filter row folds behind a toggle with an active-filter chip, the evidence panel
    starts with the compact columns, and a stored column choice still wins."""
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    evidence = (STATIC / "deckevidence.js").read_text(encoding="utf-8")
    ui = (STATIC / "ui.js").read_text(encoding="utf-8")
    assert 'id="filter-toggle"' in index and 'id="filters-more"' in index
    assert 'id="filter-count"' in index
    assert "studio.builder.filters-open" in app and "updateFilterChip" in app
    assert "EVIDENCE_COMPACT" in evidence and "evidenceStoredColumns(allKeys, wide)" in evidence
    assert "studio-evidence-hidden-columns" in evidence
    assert "pill-short" in ui and "Engine-Stand noch nicht qualifiziert" in ui


def test_mobile_deck_browser_columns_and_tier_banner_stay_in_the_viewport() -> None:
    """Abnahme 2026-11-17 (B2, #1464): at 390 px the Deck-Browser and Deckbuilder grid columns
    must not be widened by child min-content, and all sentence-length badges in the tier list
    must wrap instead of running off-screen on one line."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    assert "@media (max-width:900px){main.browser>*{min-width:0}}" in css
    assert "main{grid-template-columns:minmax(0,1fr)}main>*{min-width:0}" in css
    assert (
        "#deck{border-left:1px solid var(--line);background:var(--panel);display:flex;flex-direction:column;min-height:0;min-width:0}"
        in css
    )
    tier_css = (STATIC / "tierliste.css").read_text(encoding="utf-8")
    assert ".badge-text{white-space:normal" in tier_css
    tier_js = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    # Every sentence-length badge carries the wrapping class, pinned per site:
    # oracle banner, universe-empty note, subset note, below-minimum note,
    # calculation notices and snapshot-status badges.
    for site in (
        'class: "badge warn badge-text", id: "oracle-banner"',
        'id: "universe-empty", class: "badge warn badge-text"',
        'class: "badge warn badge-text" }, summary.subset_note)',
        'class: "badge warn badge-text" }, `unter dem Mindest-Universum',
        'class: "badge warn badge-text" }, text)',
        'id: "snapshot-status", class: "badge good badge-text"',
        'id: "snapshot-status", class: "badge warn badge-text"',
        'id: "snapshot-status", class: "badge dim badge-text"',
    ):
        assert site in tier_js, site


def test_no_raw_error_message_or_alert_or_missing_favicon_in_studio_pages() -> None:
    import shutil
    import subprocess

    node = shutil.which("node")
    for page_name in ("index.html", "tierliste.html", "decks.html"):
        html = (STATIC / page_name).read_text(encoding="utf-8")
        assert '<link rel="icon" href="data:,">' in html, page_name
    scripts = _files("*.js")
    assert len(scripts) >= 10
    for path in scripts:
        if node:
            res = subprocess.run(
                [node, "--check", str(path)], check=False, capture_output=True, text=True
            )
            assert res.returncode == 0, f"{path.name}: {res.stderr}"
        if path.name.startswith("partie"):
            continue
        text = path.read_text(encoding="utf-8")
        assert "alert(" not in text, path.name
        if path.name != "ui.js":
            assert "error.message" not in text and "err.message" not in text, path.name


def test_print_rules_are_scoped_to_the_build_list() -> None:
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    blocks = re.findall(r"@media print\{(.*)\}\s*$", css, re.MULTILINE)
    assert blocks
    for block in blocks:
        # Every selector in a print block must hang on the build-list class: no global hiding.
        selectors = re.findall(r"(?:^|\})([^{}]+)\{", block)
        assert selectors
        assert all("printing-buildlist" in selector for selector in selectors), selectors


def test_export_dialog_offers_exactly_the_server_text_formats() -> None:
    from commander_lab.studio.decks import EXPORT_TEXT_FORMATS

    script = (STATIC / "exportformats.js").read_text(encoding="utf-8")
    offered = re.findall(r'\{ id: "([a-z]+)", label:', script)
    assert offered
    assert set(offered) == set(EXPORT_TEXT_FORMATS)
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    assert page.index("exportformats.js") < page.index("app.js")
    assert "exportFormatsSection(" in (STATIC / "app.js").read_text(encoding="utf-8")


def test_partie_space_key_is_not_taken_from_a_focused_control() -> None:
    js = (STATIC / "partie.js").read_text(encoding="utf-8")
    keydown = js.split('addEventListener("keydown"', 1)[1].split('$("new-game")', 1)[0]
    # Space toggles the replay only when no interactive element has the focus
    assert 'if (event.key === " ") { if (isInteractive(target)) return;' in keydown
    guard = js.split("function isInteractive(", 1)[1].split("\n}", 1)[0]
    for selector in ("button", "a[href]", "input", "select", "textarea", "summary"):
        assert selector in guard
    assert keydown.index("isInteractive(target)") < keydown.index("setPlaying(")


def test_partie_announces_decisions_and_labels_option_groups() -> None:
    html = (STATIC / "partie.html").read_text(encoding="utf-8")
    js = (STATIC / "partie.js").read_text(encoding="utf-8")
    assert 'id="sr-announce"' in html and 'aria-live="polite"' in html
    assert 'id="human-decision"' in html and 'role="region"' in html
    assert 'id="toast" role="status"' in html
    assert "announceDecision(pending)" in js and "Neue Entscheidung für" in js
    # every option list is a labelled group
    assert js.count('role: "group", "aria-label"') >= 4
    assert '"aria-pressed": active' in js


def test_partie_poll_failures_show_a_connection_banner_not_a_silent_retry() -> None:
    html = (STATIC / "partie.html").read_text(encoding="utf-8")
    js = (STATIC / "partie.js").read_text(encoding="utf-8")
    assert 'id="conn-status"' in html and 'role="alert"' in html
    follow = js.split("function follow() {", 1)[1].split("async function refreshTitles", 1)[0]
    assert "/* try again */" not in follow
    assert "showConnectionLost(state.pollFailures, error.message)" in follow
    assert "Verbindung zum Studio unterbrochen" in js


def test_partie_offers_no_time_limit_choice() -> None:
    # Owner decision 2026-11-17: no timeout ends a human game; the page offers none.
    js = (STATIC / "partie.js").read_text(encoding="utf-8")
    assert "timeoutPick" not in js and "timeoutWrap" not in js
    for seconds in ("120", "300", "600"):
        assert f'value: "{seconds}"' not in js
    assert "body.decision_timeout_seconds = 0;" in js
    assert "Kein Zeitlimit" in js


def test_the_word_urteil_only_appears_in_negations() -> None:
    allowed = re.compile(r"\bkein(?:e|en|es)?\s+(?:\w+\s+)?Urteil", re.IGNORECASE)
    studio = STATIC.parent
    sources = [*_files("*.js"), *_files("*.html"), *sorted(studio.glob("*.py"))]
    assert len(sources) > 20
    offenders: list[str] = []
    for path in sources:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for match in re.finditer(r"Urteil", line):
                if not allowed.search(line[max(0, match.start() - 24) : match.end()]):
                    offenders.append(f"{path.name}:{number}")
    assert offenders == []
    assert "Vorfilter-Beobachtung" in (STATIC / "app.js").read_text(encoding="utf-8")


def test_partie_loads_one_page_at_a_time_and_reloads_when_hands_are_revealed() -> None:
    js = (STATIC / "partie.js").read_text(encoding="utf-8")
    # loads run one after the other, never two with the same start
    assert "loadTail = run.catch(" in js and "loadTail.then(loadMoreOnce)" in js
    once = js.split("async function loadMoreOnce() {", 1)[1].split("async function openGame", 1)[0]
    assert "page.start !== requestedStart" in once  # a page for another position is dropped
    assert "state.gameId !== gameId" in once  # an answer for a game that is no longer open
    # the game ended while watched: reload from the start so the revealed hands arrive
    assert "page.hands_revealed && !state.handsRevealed && state.frames.length" in once
    assert once.index("resetFrames();") < once.index("state.frames.push(")


def test_partie_leave_restore_deleted_game_and_attempt_reset() -> None:
    js = (STATIC / "partie.js").read_text(encoding="utf-8")
    assert "error.status === 404" in js and "failure.status = response.status" in js
    follow = js.split("function follow() {", 1)[1].split("async function refreshTitles", 1)[0]
    assert follow.index("error.status === 404") < follow.index(
        "showConnectionLost(state.pollFailures"
    )
    assert 'addEventListener("pagehide"' in js and "keepalive: true" in js
    assert "restoreAiDelayOnLeave(state.gameId);" in js  # when another game is opened
    ended = js.split("function endFastForward(", 1)[1].split("\nfunction ", 1)[0]
    assert "state.autoPassAttempt = null" in ended


def test_no_raw_model_code_and_average_mana_value_uses_the_german_formatter() -> None:
    """Visible texts say "Modellrechnung", not the internal code, and a mana-value average goes
    through StudioUI.num (comma), not a raw number (QA finding B3/B4, #1464)."""
    scripts = [p for p in _files("*.js") if not p.name.startswith("partie")]
    assert len(scripts) >= 10
    for path in scripts:
        assert "HEURISTIC_MODEL" not in path.read_text(encoding="utf-8"), path.name
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "${shape.mana_value === null" not in app
    packages = (STATIC / "packages.js").read_text(encoding="utf-8")
    assert "StudioUI.num(m.deck" in packages and "StudioUI.num(m.target" in packages


def _node_json(script: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    done = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, check=True, cwd=STATIC
    )
    return json.loads(done.stdout)


def test_draft_export_matches_the_server_text_for_astral_names_and_partners() -> None:
    from commander_lab.studio.decks import export_text

    # U+FF5E sorts before U+1F600 by code point (Python) but after it by UTF-16 unit (JS).
    names = ["\U0001f600 Grin", "\uff5e Tilde", "Zed", "Apple", "Zed"]
    script = (
        "const E = require('./exportformats.js');"
        f"const names = {json.dumps(names)};"
        "const cmd = [{name: 'Zoe', quantity: 1}, {name: 'Abe', quantity: 1}];"
        "const main = names.map((name) => ({name, quantity: 1}));"
        "console.log(JSON.stringify(['moxfield', 'plain'].map((f) => E.exportFormatText(f, cmd, main))));"
    )
    drafts = _node_json(script)
    rows = [{"zone": "commander", "oracle_name": n, "quantity": 1} for n in ("Zoe", "Abe")]
    rows += [{"zone": "main", "oracle_name": n, "quantity": 1} for n in names]
    server = [export_text(rows, f) for f in ("moxfield", "plain")]  # type: ignore[arg-type]
    assert drafts == server
    assert "2 Zed" in server[0]
    assert server[0].index("\uff5e Tilde") < server[0].index("\U0001f600 Grin")


def test_build_list_keys_are_stable_order_free_and_per_location() -> None:
    script = """
const B = require('./buildlist.js');
const state = {baseRevision: null, dirty: true, deckId: 'd'};
const key = (entries) => B.buildListKey({state, entries: () => entries});
const a = {card_id: 'c1', zone: 'main', quantity: 1};
const b = {card_id: 'c2', zone: 'main', quantity: 2};
const box = (id) => ({location_id: id});
console.log(JSON.stringify({
  same: key([a, b]) === key([a, b]),
  order: key([a, b]) === key([b, a]),
  changed: key([a, b]) !== key([a, {...b, quantity: 3}]),
  zone: key([a, b]) !== key([a, {...b, zone: 'commander'}]),
  tick: [B.buildListTickId(box('box-1'), a), B.buildListTickId(box('box-2'), a),
         B.buildListTickId(box(null), a)],
  draft: key([a, b]).startsWith('buildlist:d:entwurf-'),
}));
"""
    result = _node_json(script)
    assert result == {
        "same": True,
        "order": True,
        "changed": True,
        "zone": True,
        "tick": ["box-1:c1", "box-2:c1", "unknown:c1"],
        "draft": True,
    }


def test_engine_check_and_json_export_labels_say_what_they_do() -> None:
    """The engine check compares with the stored engine card list (no live engine query) and the
    JSON export is a lab file for command-line tools, not for the Studio series form (container
    check 2026-11-17)."""
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "Gegen die Engine-Kartenliste prüfen" in app
    assert '"Mit der Engine prüfen"' not in app
    assert "keine Live-Abfrage der Engine" in app
    assert "für Simulation (" not in app and "als Lab-Datei" in app
