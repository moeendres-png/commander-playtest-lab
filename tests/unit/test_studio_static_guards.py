"""Static guards for the Studio pages: no literal 'null' children, no price wording, labelled inputs."""

from __future__ import annotations

import re
from pathlib import Path

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
    """No raw .toFixed( in any Studio script except the two excluded pages: the de-DE helpers
    StudioUI.num / StudioUI.pct are the only place that formats decimals (comma, not point)."""
    excluded = {"tierliste.js"}
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
    assert 'toLocaleString("de-DE"' in ui and "num, pct" in ui
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


def test_boardclick_script_only_maps_engine_options_and_holds_no_rules() -> None:
    script = (STATIC / "boardclick.js").read_text(encoding="utf-8")
    html = (STATIC / "partie.html").read_text(encoding="utf-8")
    assert html.index('src="boardclick.js"') < html.index('src="partie.js"')
    # a pure mapping: no DOM, no network, no markup sinks, no style attribute
    for sink in ("document.", "window.", "fetch(", "innerHTML", "outerHTML", "eval(", "style="):
        assert sink not in script, sink
    # no rule words: legality is the engine's, the page never works a rule out
    rule_words = re.compile(
        r"\b(hexproof|shroud|ward|protection|summoning|vigilance|haste|flying|reach|lethal|deathtouch)\b",
        re.IGNORECASE,
    )
    assert rule_words.findall(script) == []
    # a click can only name an option the decision offers, and an object must equal its option id
    assert "const offered = entry.optionIds.map((id) => optionOf(pending, id)).filter(Boolean);" in script
    assert "offered.length !== entry.optionIds.length" in script
    assert "objectId !== optionId" in script
    # opponents are recognised only by the engine's own player name
    assert 'SEAT_NAME = /^Full Game Seat (\\d+)$/' in script


def test_partie_board_clicks_send_only_offered_options_and_only_on_a_click() -> None:
    js = (STATIC / "partie.js").read_text(encoding="utf-8")
    css = (STATIC / "partie.css").read_text(encoding="utf-8")
    html = (STATIC / "partie.html").read_text(encoding="utf-8")
    for element in ('id="board-bar"', 'id="board-menu"', 'id="board-links"', 'role="menu"'):
        assert element in html, element
    # boardClick runs only from onclick handlers (never from a timer, a poll or a render)
    calls = [m.start() for m in re.finditer(r"boardClick\(", js)]
    assert len(calls) == 3  # the definition, the card tile (also in the zone lists) and the seat button
    for start in calls:
        line = js[js.rfind("\n", 0, start) + 1 : js.find("\n", start)]
        assert "function boardClick(" in line or "onclick" in line, line
    # the one place a board answer leaves: it checks the id against the pending decision first
    send = js.split("function sendBoardOption(", 1)[1].split("\nfunction ", 1)[0]
    assert send.index("offeredOption(optionId)") < send.index("submitHumanChoice(")
    toggle = js.split("function toggleOption(", 1)[1].split("\nfunction ", 1)[0]
    assert "offeredOption(optionId)" in toggle and "submitHumanChoice(" not in toggle
    # fast-forward, auto-pass and the switch-on code never touch a board click
    for name in ("startFastForward", "endFastForward", "maybeAutoPassHuman", "setAiDelay"):
        body = js.split(f"function {name}(", 1)[1].split("\nfunction ", 1)[0]
        assert "boardClick(" not in body and "sendBoardOption(" not in body, name
    # cards on the board carry their object id, are real buttons with a label, and the preview
    # follows the keyboard focus as well as the mouse
    assert 'props["data-object-id"] = options.objectId' in js
    assert 'h("button", props, cardFace(name))' in js and '"aria-label": clickAria(name, entry)' in js
    assert 'el.addEventListener("focus"' in js and ":focus-visible" in js
    # only the decision of the live table is clickable, never a recorded frame
    assert "atLiveTail && state.click" in js and "!state.submitting && !state.ff.on" in js
    # Esc closes an open menu before it closes anything else; the option list stays
    keydown = js.split('addEventListener("keydown"', 1)[1].split('$("new-game")', 1)[0]
    assert keydown.index("closeBoardMenu(true)") < keydown.index('$("modal").hidden = true')
    assert 'class: "human-options"' in js and "toggleOption(optId)" in js
    # a refused or outdated answer says so instead of staying silent
    assert "stale" in js and "Vermutlich hat sich die Entscheidung inzwischen geändert" in js
    # classes, no inline styles
    for rule in (".card.legal ", ".card.dimmed", ".card.clickable:hover", ".card.picked", ".board-menu", ".seat-pick"):
        assert rule in css, rule
    assert "style=" not in js and "style=" not in html and "setAttribute(\"style\"" not in js
