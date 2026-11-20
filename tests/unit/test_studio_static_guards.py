"""Static guards for the Studio pages: no literal 'null' children, no price wording, labelled inputs."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "src" / "commander_lab" / "studio" / "static"
# Price and buy wording is forbidden in every page and script (B1, AGENTS.md §12).
PRICE_WORDS = re.compile(r"\b(preis\w*|kaufen|price\w*|buy)\b|€", re.IGNORECASE)
# Owner decision 2026-11-19 (E14, #1187, #1636): the word "Zukauf" (missing-card wishlist
# without prices) is allowed in BUILD only: its wishlist helpers and the BUILD page (#1648).
ZUKAUF_WORDS = re.compile(r"\bzuk[aä]u[fe]\w*", re.IGNORECASE)
ZUKAUF_FILES = frozenset({"wishlist.js", "app.js", "index.html"})


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


def test_zukauf_wording_only_on_the_build_page() -> None:
    # E14 frees "Zukauf" for BUILD, not for the other pages; price words stay forbidden in the
    # BUILD files too (previous test).
    offenders: dict[str, list[str]] = {}
    allowed_seen = 0
    for path in [*_files("*.html"), *_files("*.js")]:
        found = ZUKAUF_WORDS.findall(path.read_text(encoding="utf-8"))
        if path.name in ZUKAUF_FILES:
            allowed_seen += len(found)
        elif found:
            offenders[path.name] = found
    assert offenders == {}
    assert allowed_seen > 0  # the pattern still finds the BUILD texts
    assert ZUKAUF_WORDS.search("Zukäufe") and ZUKAUF_WORDS.search("Zukauf-Liste")


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


def test_no_page_calls_the_removed_prefilter_or_tournament_conversion() -> None:
    """Q1-b1 (#1676, E15 Q1): the heuristic prefilter button and the TopDeck Mit/Ohne panel
    left the Studio; no page, script or style may still call or style them."""
    sources = [*_files("*.js"), *_files("*.html"), *_files("*.css")]
    assert len(sources) > 20
    for token in (
        "/api/prefilter",
        "/api/tournament-conversion",
        "topdeck-conversion-panel",
        "conv-filter-row",
        "loadTournamentConversion",
    ):
        hits = [path.name for path in sources if token in path.read_text(encoding="utf-8")]
        assert hits == [], (token, hits)


def test_the_tier_page_knows_no_rubric_v1_simulation_or_conversion_component() -> None:
    """Q1-b4 (#1679, E15 Q1): the index lost the components ``rubric`` (rubric v1),
    ``simulation`` and ``tournament_conversion``; the tier page names none of them as a
    component any more. Rubric v2 stays as the column "Kartenverständnis (Modellurteil)"."""
    sources = [*_files("*.js"), *_files("*.html"), *_files("*.css")]
    assert len(sources) > 20
    for token in (
        "block-subjective",
        "block-simulation",
        'c.component === "rubric"',
        'c.component === "simulation"',
        'c.key !== "simulation"',
        'c.key === "rubric"',
        "tournament_conversion",
        "Raster-Bewertung",
    ):
        hits = [path.name for path in sources if token in path.read_text(encoding="utf-8")]
        assert hits == [], (token, hits)
    # positive case: the rubric v2 column stays
    js = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    assert "// ---------- rubric v2 judgement" in js
    assert "Kartenverständnis (Modellurteil)" in js


def test_partie_loads_one_page_at_a_time_and_reloads_when_hands_are_revealed() -> None:
    js = (STATIC / "partie.js").read_text(encoding="utf-8")
    # loads run one after the other, never two with the same start
    # a state sent with an own answer (#1578) rides in the same queue, it never skips it
    assert "loadTail = run.catch(" in js
    assert "loadTail.then(() => loadMoreOnce(hold, prefetched))" in js
    once = js.split("async function loadMoreOnce(hold, prefetched) {", 1)[1].split(
        "async function openGame", 1
    )[0]
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
    assert (
        "const offered = entry.optionIds.map((id) => optionOf(pending, id)).filter(Boolean);"
        in script
    )
    assert "offered.length !== entry.optionIds.length" in script
    assert "objectId !== optionId" in script
    # opponents are recognised only by the engine's own player name
    assert "SEAT_NAME = /^Full Game Seat (\\d+)$/" in script


def test_new_game_dialog_offers_only_the_released_table_sizes() -> None:
    from commander_lab.studio import launch

    js = (STATIC / "partie.js").read_text(encoding="utf-8")
    declared = re.search(r"const OPPONENT_COUNTS = \[([0-9, ]+)\];", js)
    assert declared is not None
    counts = [int(n) for n in declared.group(1).split(",")]
    # two to four players: one to three opponents, never five or six seats
    assert counts == list(range(launch.MIN_SEATS - 1, launch.MAX_RELEASED_SEATS))
    assert "OPPONENT_COUNTS.map(" in js and "[1, 2, 3, 4, 5].map" not in js


def test_commander_line_shows_engine_values_and_computes_nothing() -> None:
    js = (STATIC / "partie.js").read_text(encoding="utf-8")
    rows = js.split("function commanderRows(", 1)[1].split("\nfunction commanderLine(", 1)[0]
    line = js.split("function commanderLine(", 1)[1].split("\nfunction pilotStateToFrame(", 1)[0]
    assert "Steuer unbekannt" in line and "Casts unbekannt" in line
    for word in ("tax", "21", "* 2", "+ 2"):
        assert word not in rows and word not in line, word
    # damage totals are shown as the engine's own numbers: only assigned, never summed
    assert "+=" not in rows and "reduce(" not in rows and "reduce(" not in line
    assert "commanders," in js.split("function pilotStateToFrame(", 1)[1].split("return {", 1)[1]


def test_partie_dims_non_answers_with_a_veil_and_labels_every_engine_decision_class() -> None:
    css = (STATIC / "partie.css").read_text(encoding="utf-8")
    js = (STATIC / "partie.js").read_text(encoding="utf-8")
    # a card that is not a legal answer gets a veil, never a filter or opacity on the card image
    assert ".card.dimmed::after" in css
    dimmed = [line for line in css.splitlines() if ".card.dimmed" in line]
    assert dimmed and all("filter" not in line and "opacity" not in line for line in dimmed)
    assert "filter" not in css.split(".card{transition", 1)[1].split("}", 1)[0]
    # a decision whose options are all off the board (a library card) dims nothing and says so
    assert "boardHasClickables(state.click) && !state.click.objects[objectId]" in js
    assert "liegen nicht auf dem Brett" in js
    # the engine's two label-only actions are shown in German, and five area links fit 390 px
    assert 'Cancel mana payment") s = "Zahlung abbrechen"' in js
    assert 'startsWith("Do not attack with ")' in js
    assert "@media (max-width:480px){#areas a{" in css
    # every decision class the bridge declares has a German label in the page
    java = (
        Path(__file__).resolve().parents[2]
        / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameDecisionController.java"
    ).read_text(encoding="utf-8")
    declared = re.findall(
        r'"([a-z_]+)"', java.split("DECISION_CLASSES = Set.of(", 1)[1].split(");", 1)[0]
    )
    labels = set(re.findall(r"(\w+): ", js.split("const CLASSES = {", 1)[1].split("};", 1)[0]))
    assert len(declared) >= 17 and "amount" in declared
    assert sorted(set(declared) - labels) == []


def test_partie_board_clicks_send_only_offered_options_and_only_on_a_click() -> None:
    js = (STATIC / "partie.js").read_text(encoding="utf-8")
    css = (STATIC / "partie.css").read_text(encoding="utf-8")
    html = (STATIC / "partie.html").read_text(encoding="utf-8")
    for element in ('id="board-bar"', 'id="board-menu"', 'id="board-links"', 'role="menu"'):
        assert element in html, element
    # boardClick runs only from onclick handlers (never from a timer, a poll or a render)
    calls = [m.start() for m in re.finditer(r"boardClick\(", js)]
    assert (
        len(calls) == 3
    )  # the definition, the card tile (also in the zone lists) and the seat button
    for start in calls:
        line = js[js.rfind("\n", 0, start) + 1 : js.find("\n", start)]
        assert "function boardClick(" in line or "onclick" in line, line
    # the one place a board answer leaves: it checks the id against the pending decision first
    send = js.split("function sendBoardOption(", 1)[1].split("\nfunction ", 1)[0]
    assert send.index("offeredOption(optionId)") < send.index("submitHumanChoice(")
    toggle = js.split("function toggleOption(", 1)[1].split("\nfunction ", 1)[0]
    assert "offeredOption(optionId)" in toggle and "submitHumanChoice(" not in toggle
    # a board answer is bound to the decision its model was built for, never to a newer pending one
    for name in ("toggleBoardOption", "sendBoardOption", "confirmSelection", "boardClick"):
        body = js.split(f"function {name}(", 1)[1].split("\nfunction ", 1)[0]
        assert "boardDecision()" in body, name
    assert (
        "decision_id: state.click.decisionId" in send
        and "decision_id: pending.decision_id" not in send
    )
    confirm = js.split("function confirmSelection(", 1)[1].split("\nfunction ", 1)[0]
    assert "decision_id: state.click.decisionId" in confirm and "offeredOption(id)" in confirm
    # the poll hands every new decision over through adoptPendingDecision (behaviour: test_page_drops_...)
    assert "adoptPendingDecision(page.pending_decision || null);" in js
    # fast-forward, auto-pass and the switch-on code never touch a board click
    for name in ("startFastForward", "endFastForward", "maybeAutoPassHuman", "setAiDelay"):
        body = js.split(f"function {name}(", 1)[1].split("\nfunction ", 1)[0]
        assert "boardClick(" not in body and "sendBoardOption(" not in body, name
    # cards on the board carry their object id, are real buttons with a label, and the preview
    # follows the keyboard focus as well as the mouse
    assert 'props["data-object-id"] = options.objectId' in js
    assert (
        'h("button", props, cardFace(name))' in js and '"aria-label": clickAria(name, entry)' in js
    )
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
    for rule in (
        ".card.legal ",
        ".card.dimmed",
        ".card.clickable:hover",
        ".card.picked",
        ".board-menu",
        ".seat-pick",
    ):
        assert rule in css, rule
    assert "style=" not in js and "style=" not in html and 'setAttribute("style"' not in js


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


def test_the_column_menu_host_id_is_the_same_in_html_and_js() -> None:
    """Q1-b2 (#1677): the host of the Kompakt/Detail menu was renamed from ``layer-controls``;
    the id the script looks up must be the id the page has, and the old one is gone."""
    import re

    html = (STATIC / "tierliste.html").read_text(encoding="utf-8")
    js = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    body = js[js.index("function renderColumnControls() {") :]
    looked_up = re.search(r'const host = \$\("([^"]+)"\);', body)
    assert looked_up is not None
    assert f'id="{looked_up.group(1)}"' in html
    assert looked_up.group(1) == "col-controls"
    for name in ("tierliste.html", "tierliste.js", "tierliste.css", "app.css"):
        assert "layer-controls" not in (STATIC / name).read_text(encoding="utf-8"), name


def test_tierliste_ux_batch_1_contract() -> None:
    """UX batch 1 (#1369): one labelled scroll region with a skip link, the method panels behind one
    closed details, a dialog window, table semantics, plain German instead of raw codes, and the
    comparison "Gleiche Funktion" as a view mode (the quick toggle sends no recalculation)."""
    html = (STATIC / "tierliste.html").read_text(encoding="utf-8")
    js = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    css = (STATIC / "tierliste.css").read_text(encoding="utf-8")
    assert html and js and css
    assert 'class="skip-link" href="#pool-body"' in html
    assert (
        'id="pool-body" role="region"' in html and 'aria-label="Tierliste: Kartentabelle"' in html
    )
    assert 'role="dialog" aria-modal="true" aria-labelledby="modal-title"' in html
    method = html.split('<details id="method-panel"', 1)[1].split("</details>", 1)[0]
    panel_ids = [
        "data-state",
        "notice",
        "universe-panel",
        "strength-panel",
        "role-audit-panel",
    ]
    assert "Methodik und Datenlage" in method
    for panel_id in panel_ids:
        assert f'id="{panel_id}"' in method, panel_id  # behind the one details, not above the table
        assert f'id="{panel_id}"' in html.split('<div id="filters">', 1)[0]
    assert 'id="tier-bar"' in html and 'id="col-controls"' in html
    # table semantics, sticky columns, one scroll area
    for token in (
        'scope: "col"',
        '"aria-sort"',
        'class: "visually-hidden"',
        '"aria-pressed": String(state.tab',
        "th-sort",
    ):
        assert token in js, token
    assert "position:sticky;left:0" in css and "#pool-body .table-wrap{overflow:visible}" in css
    assert "body.modal-open" in css and "closeModal" in js and "trapModalFocus" in js
    # raw codes are plain German (the code stays in the title), no English leftovers
    for code in ("COMPLETE", "NORMALIZED_SOURCE", "DERIVED_DESCRIPTIVE", "NEGATIVE_NEUTRAL"):
        assert f'{code}: "' in js, code
    for raw_label in ("(ZERO_COUNT)", "(NOT_LISTED)", "(NOT_COLLECTED)", "EDHREC Inclusion"):
        assert raw_label not in js, raw_label
    assert "keine echte oracle_id" not in js and "keine echte Oracle-Kennung" in js
    assert "typeLabel(group)" in js and 'Artifact: "Artefakt"' in js
    # the quick toggle is a view mode: it must not send rank_group to the server any more
    assert "rank_group: group" not in js and 'data-rank-group="function"' in html
    assert "role_ranks" in js and "Rang in Funktion" in js
    for forbidden in ("innerHTML", "style=", 'setAttribute("style"', ".toFixed("):
        assert forbidden not in js and forbidden not in html, forbidden


def test_why_box_split_is_only_shown_when_it_adds_up() -> None:
    """P2 of the UX batch 1 review: the split of the index into points and percentages ("Warum hier?")
    runs the real function from tierliste.js. A low index (0,2) gets no percentage split, a high one
    (80,6) does and its rounded percentages add up to 100 +- 1."""
    source = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    start = source.index("function indexShares(item) {")
    end = source.index('// "Warum hier?"', start)
    script = (
        f"eval({json.dumps(source[start:end])} + ';globalThis.indexShares = indexShares;');"
        "const comp = (component, weight, percentile) => ({component, label: component, weight, percentile});"
        "const item = (parts) => { const total = parts.reduce((s, p) => s + p[1], 0);"
        "  const index = Math.round(10 * parts.reduce((s, p) => s + 100 * p[1] * p[2] / total, 0)) / 10;"
        "  return {index, components: parts.map((p) => comp(...p))}; };"
        "const low = item([['edhrec', 1, 0.0082], ['deck', 4, 0.0007], ['tour', 0.5, 0.0054], ['combos', 0.5, 0], ['lift', 1, 0.0006]]);"
        "const high = item([['deck', 4, 1], ['tuned', 1.5, 1], ['lift', 1, 0], ['slope', 1, 0.06], ['glob', 1, 1], ['tour', 0.5, 0.99], ['theme', 0.5, 0.99], ['combos', 0.5, 1]]);"
        "const a = indexShares(low), b = indexShares(high);"
        "console.log(JSON.stringify({lowIndex: low.index, lowDetail: a === null ? null : a.detail,"
        "  highIndex: high.index, highDetail: b.detail,"
        "  highSum: b.shown.reduce((s, r) => s + Math.round(r.percent), 0) + Math.round(b.restPercent)}));"
    )
    result = _node_json(script)
    assert isinstance(result, dict)
    assert result["lowIndex"] < 5 and result["lowDetail"] is False
    assert result["highIndex"] > 70 and result["highDetail"] is True
    assert 99 <= result["highSum"] <= 101


def _ui_helpers_prelude() -> str:
    """The real de-DE number helpers of ui.js as a small ``StudioUI`` object for node tests."""
    ui = (STATIC / "ui.js").read_text(encoding="utf-8")
    ui_part = ui[
        ui.index("function _formatDe(n, opts) {") : ui.index("// Simulator readiness codes")
    ]
    return "const StudioUI = (() => {" + ui_part + "return {num, pct, numFlex, numSig}; })();\n"


def test_why_box_names_the_further_signals_and_never_shows_zero_percent() -> None:
    """P3 of #1494: a positive share that rounds to 0 % is shown as "unter 1 %", the number of
    further signals is named, and a top row under 1 % switches the percentages off. Rewritten in
    Q1-b3 (#1678): it ran on the prelude of the removed overall rating; it now cuts out only the
    real ``percentOrUnder`` and ``indexShares`` of tierliste.js."""
    js = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    nf_line = next(line for line in js.splitlines() if line.startswith("const nf = "))
    start = js.index("function percentOrUnder(percent) {")
    shares = js[start : js.index('// "Warum hier?"', start)]
    assert "function indexShares(item) {" in shares
    script = (
        _ui_helpers_prelude()
        + nf_line
        + "\n"
        + shares
        + """
const comp = (component, weight, percentile) => ({component, label: component, weight, percentile});
const item = (parts) => { const total = parts.reduce((s, p) => s + p[1], 0);
  const index = Math.round(10 * parts.reduce((s, p) => s + 100 * p[1] * p[2] / total, 0)) / 10;
  return {index, components: parts.map((p) => comp(...p))}; };
const tail = indexShares(item([['deck', 4, 1], ['tuned', 1.5, 1], ['glob', 1, 1], ['lift', 1, 0.001], ['tour', 0.5, 0.001]]));
const spread = indexShares(item([['a', 1, 0.9], ['b', 1, 0.8], ['c', 1, 0.7], ['d', 1, 0.6]]));
console.log(JSON.stringify({tailDetail: tail.detail, tailCount: tail.restCount, tailRest: percentOrUnder(tail.restPercent),
  spreadCount: spread.restCount, spreadRest: percentOrUnder(spread.restPercent)}));
"""
    )
    result = _node_json(script)
    assert isinstance(result, dict)
    assert result["tailDetail"] is True and result["tailCount"] == 2
    assert result["tailRest"] == "unter 1 %" and "0 %" not in result["tailRest"].replace("1 %", "")
    assert result["spreadCount"] == 1 and result["spreadRest"] != "unter 1 %"
    assert "percentOrUnder(shares.restPercent)" in js and "weitere ${nf(shares.restCount)}" in js


def test_the_tierliste_has_no_overall_rating_left() -> None:
    """Q1-b3 (#1678, E15 Q1): the overall rating v1 left the tier list. No toggle button, panel,
    sort key, style or server field of it remains; the bar keeps the usage button for Q1-b5
    (#1680), and a remembered sort of the removed rating is no sort option any more (the page
    falls back to the index sort)."""
    html = (STATIC / "tierliste.html").read_text(encoding="utf-8")
    js = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    css = (STATIC / "tierliste.css").read_text(encoding="utf-8")
    for token in ("rk-overall", "overall-panel", 'data-ranking="overall"', "Gesamtrating"):
        assert token not in html, token
    for token in (
        "overall_meta",
        "overallOf",
        "overallColumns",
        "renderOverallPanel",
        "overall-hint",
        "setRanking",
        "studio.tier.ranking",
        '"overall_rank"',
        "CRIT_SORT",
        "Gesamtrating",
    ):
        assert token not in js, token
    for token in ("#overall-panel", ".ocell", ".oscore", ".overall-reason", "crit-head"):
        assert token not in css, token
    toggle = html.split('id="ranking-toggle"', 1)[1].split("</span>\n  <span", 1)[0]
    assert 'id="rk-usage"' in toggle and ">Nutzung</button>" in toggle
    assert toggle.count("<button") == 1
    # a stored sort key is only restored when it is still a sort option
    assert "SORTS.some((item) => item[0] === savedSort)" in js
    sorts = js[js.index("const SORTS = [") : js.index("];", js.index("const SORTS = ["))]
    for gone in ('"overall"', '"overall_rank"', "crit:"):
        assert gone not in sorts, gone
    # No sort key for the model judgement "Kartenverständnis" either: sorting by it would be a
    # rating through the back door (review of #1691/#1696). The keys are read from the array.
    sort_keys = re.findall(r'^\s*\["([^"]+)",', sorts, flags=re.MULTILINE)
    assert "strength" in sort_keys and "rolerank" in sort_keys and len(sort_keys) >= 10
    for key in sort_keys:
        for token in ("understanding", "kartenverst", "urteil", "rubric", "judgement"):
            assert token not in key.casefold(), key
    # positive case: the judgement column and its constants stay, they are only no sort key
    assert "const UNDERSTANDING_NAME" in js and "understandingColumns()" in js
    # the judgement column uses the number contract component of B3
    assert html.index('<script src="zahl.js">') < html.index('<script src="tierliste.js">')


def _understanding_node_prelude() -> str:
    """The real number contract component (zahl.js), the real constants and judgement block of
    tierliste.js (cut out by their markers) and a small stub of h() and the page state."""
    js = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    zahl = (STATIC / "zahl.js").read_text(encoding="utf-8")
    lines = js.splitlines()
    nf_line = next(line for line in lines if line.startswith("const nf = "))
    head_line = next(line for line in lines if line.startswith("const plainHead = "))
    constants = js[js.index("const UNDERSTANDING_NAME") : js.index("const SORTS = [")]
    block = js[js.index("// ---------- rubric v2 judgement") : js.index("// ---------- pool view")]
    stub = """
const h = (tag, props, ...kids) => { const node = {tag, props: props || {}, kids: [],
  append(...more) { this.kids.push(...more.flat(Infinity).filter((k) => k !== null && k !== undefined && k !== false)); }};
  node.append(...kids); return node; };
const text = (n) => (n === null || n === undefined ? '' : typeof n === 'object' ? n.kids.map(text).join(' ') : String(n));
const figure = (id, wert, klasse = 'URTEIL') => ({id: 'kartenverstaendnis:' + id, bezeichnung: 'H Gesamtwert (0 bis 100)', wert,
  einheit: 'Punkte', n: null, N: null, bezug: null, intervall: null, klasse, kohorte: 'Chulane, Teller of Tales · Bracket 3 (Annahme der Rater)',
  quelle: 'Rubrik v2.1 (chulane-rubric-v2.1), Modell-Rater Stufe large, 1 Bewerter', stand_datum: null,
  hinweise: ['Rater-Vertrauen high (Selbstauskunft)', 'nicht gegen Spielergebnisse validiert']});
const field = (zahlen, extra) => ({verfuegbar: true, grund: null, name: 'Kartenverständnis (Modellurteil)', kriterium: 'H',
  n_bewertet: zahlen.length, n_gesamt: 3, herkunft: {version: 'v2.1', rubric: 'chulane-rubric-v2.1'}, zahlen, ...extra});
const setup = (result, view = 'commander', status = 'ready') => { globalThis.state = {view, strength: {status, result}}; };
const cards = [{card_id: 'A'}, {card_id: 'B'}, {card_id: 'C'}];
const view = () => { const columns = understandingColumns();
  return {heads: columns.map((c) => text(c.head())), cells: columns.length ? cards.map((card) => text(columns[0].cell(card))) : [],
    hint: understandingHint().map(text).join(' ')}; };
"""
    return (
        _ui_helpers_prelude()
        + zahl
        + "\n"
        + nf_line
        + "\n"
        + head_line
        + "\n"
        + constants
        + "\n"
        + block
        + "\n"
        + stub
    )


def test_the_judgement_column_is_only_shown_for_chulane_with_class_urteil() -> None:
    """Q1-b3 (#1678, E5): the column "Kartenverständnis (Modellurteil)" runs through the real
    StudioZahl.zelle with the class URTEIL. It appears only while the server sends the field
    (Chulane) and says it is available; a card without a figure is "unbekannt", never 0; for
    another commander (no field), the global view and an unavailable field there is no column;
    a figure of another class shows no number (classes are never mixed in one column)."""
    script = (
        _understanding_node_prelude()
        + """
const out = {};
setup({kartenverstaendnis: field([figure('A', 90), figure('C', 0)])});
out.chulane = view();
setup({cards: []});
out.other = view();
setup({kartenverstaendnis: field([figure('A', 90)])}, 'global');
out.global = view();
setup({kartenverstaendnis: field([figure('A', 90)])}, 'commander', 'loading');
out.loading = view();
setup({kartenverstaendnis: field([], {verfuegbar: false, grund: 'Kartenverständnis gilt für Bracket 3', herkunft: null})});
out.unavailable = view();
setup({kartenverstaendnis: field([{...figure('A', 90, 'GEZÄHLT'), n: 9, N: 10, bezug: 'Decks (mit Karte / gesamt)'}])});
out.mixed = view();
console.log(JSON.stringify(out));
"""
    )
    result = _node_json(script)
    assert isinstance(result, dict)
    chulane = result["chulane"]
    assert chulane["heads"] == ["Kartenverständnis (Modellurteil)"]
    a, b, c = chulane["cells"]
    assert a.startswith("90") and "Modellurteil" in a and "Quelle: Rubrik v2.1" in a
    assert "Kohorte: Chulane" in a and "nicht gegen Spielergebnisse validiert" in a
    assert b == "unbekannt"  # no figure: unknown, never 0
    assert c.startswith("0") and "Modellurteil" in c  # a real 0 stays a real 0
    assert "2 von 3 Karten bewertet" in chulane["hint"] and "v2.1" in chulane["hint"]
    assert "nicht gegen Spielergebnisse validiert" in chulane["hint"]
    for case in ("other", "global", "loading"):
        assert result[case] == {"heads": [], "cells": [], "hint": ""}, case
    unavailable = result["unavailable"]
    assert unavailable["heads"] == [] and "nicht verfügbar" in unavailable["hint"]
    assert "Bracket 3" in unavailable["hint"]
    mixed = result["mixed"]["cells"]
    assert mixed[0] == "Klasse passt nicht zur Spalte" and not mixed[0].startswith("90")
    js = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    assert 'StudioZahl.zelle(h, understandingFigure(card), "URTEIL"' in js


def test_the_tierliste_shows_exactly_one_tier_scale() -> None:
    """Q1-b5 (#1680, E2): the tier page has one lettered scale, the strength index S to D. The
    toggle of the relative tiers S to F and the spread level letters (S to D, U, F, with their
    names) are gone from page and script; the spread is n of N. "Gleiche Funktion" stays."""
    html = (STATIC / "tierliste.html").read_text(encoding="utf-8")
    js = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    for token in ("tier-mode-toggle", 'id="tm-rel"', 'id="tm-abs"', "data-tier-mode", "(S\u2013F)"):
        assert token not in html, token
    for token in (
        "tier-mode-toggle",
        "data-tier-mode",
        "tierMode",
        "TIER_MODE_KEY",
        "studio.tier.mode",
        "relative_tier",
        "relative_rank",
        "level_name",
        "LEVEL_RANK",
        "spread_level",
        "item.level",
        "S\u2013F",
        "sehr häufig",
        "Verbreitung unbekannt (U)",
        "data.params.cuts",
    ):
        assert token not in js, token
    spread_filter = html.split('<select id="spread-filter"', 1)[1].split("</select>", 1)[0]
    assert re.findall(r'<option value="([^"]*)"', spread_filter) == [
        "",
        "counted",
        "unknown",
        "filter",
    ]
    # the one scale and the kept comparison
    assert "Stärke-Index mit Stufen S bis D" in html and 'id="rk-usage"' in html
    assert 'id="rank-group-toggle"' in html and 'id="rg-function"' in html
    assert "tierBadge(item.tier, StudioUI.num(item.index, 1), title)" in js


def _pool_view_node_prelude() -> str:
    """The real zahl.js and ui.js helpers, the real reason names and the pool view block of
    tierliste.js (cut out by its markers), with a small h() stub."""
    js = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    zahl = (STATIC / "zahl.js").read_text(encoding="utf-8")
    reasons = next(line for line in js.splitlines() if line.startswith("const REASON_NAMES = "))
    block = js[js.index("// ---------- pool view") : js.index("function spreadCell(card) {")]
    stub = """
const h = (tag, props, ...kids) => ({tag, props: props || {}, kids: kids.flat(Infinity).filter((k) => k !== null && k !== undefined && k !== false)});
const text = (n) => (n === null || n === undefined ? '' : typeof n === 'object' ? n.kids.map(text).join(' ') : String(n));
const universe = {profile: 'alle', snapshot_id: 'universe:abc', denominator: 43, below_min_universe: false, subset_note: null};
const item = (extra) => ({card_id: 'c1', matched: true, filter_card: false, hits: 20, denominator: 43, share: 20 / 43, reason: 'SHARE_CUT', ...extra});
const show = (it, uni = universe) => { const figure = spreadFigure(it, uni);
  return {kind: spreadKindOf(it, uni), figure, errors: figure ? StudioZahl.pruefe(figure) : null, text: figure ? text(StudioZahl.knoten(h, figure)) : null}; };
"""
    return _ui_helpers_prelude() + zahl + "\n" + reasons + "\n" + block + "\n" + stub


def test_the_pool_view_shows_n_of_n_as_a_counted_number_contract() -> None:
    """Q1-b5 (#1680): the pool view "Nutzung n/N" is one GEZÄHLT figure of the real zahl.js:
    n of N decks with the universe as cohort and origin. Unmatched and below ``min_universe``
    the share is "unbekannt", never 0 (n/N stays visible); a filter card gets no figure; a
    remembered filter with a level letter falls back to "all"."""
    script = (
        _pool_view_node_prelude()
        + """
const out = {
  counted: show(item()),
  unmatched: show(item({matched: false, hits: null, share: null, reason: 'NAME_NOT_FOUND_IN_UNIVERSE'})),
  small: show(item({hits: 20, denominator: 20, share: 1, reason: 'UNIVERSE_TOO_SMALL'}), {...universe, denominator: 20, below_min_universe: true}),
  filter: show(item({filter_card: true, share: null, reason: 'FILTER_CARD'})),
  empty: show(item({matched: false, hits: null, share: null, denominator: 0, reason: 'UNIVERSE_EMPTY'}), {...universe, denominator: 0}),
  restore: ['S', 'U', 'F', 'unknown', 'counted', 'filter', '', undefined, 'toString'].map((v) => spreadFilterValue(v)),
};
console.log(JSON.stringify(out));
"""
    )
    result = _node_json(script)
    assert isinstance(result, dict)
    counted = result["counted"]
    assert counted["kind"] == "counted" and counted["errors"] == []
    assert counted["figure"]["klasse"] == "GEZÄHLT" and counted["figure"]["einheit"] == "Anteil"
    assert (counted["figure"]["n"], counted["figure"]["N"]) == (20, 43)
    assert counted["text"].startswith("46,5 %") and "gezählt" in counted["text"]
    assert "n/N 20 / 43 Decks" in counted["text"] and "Kohorte: Universum alle" in counted["text"]
    assert "Stand universe:abc" in counted["text"]
    for case in ("unmatched", "small", "empty"):
        shown = result[case]
        assert shown["kind"] == "unknown" and shown["errors"] == [], case
        assert shown["figure"]["wert"] is None and shown["text"].startswith("unbekannt"), case
        assert not shown["text"].startswith("0"), case
    assert "n/N unbekannt / 43 Decks" in result["unmatched"]["text"]
    assert "n/N 20 / 20 Decks" in result["small"]["text"]  # the count stays, the share is unknown
    assert result["filter"] == {"kind": "filter", "figure": None, "errors": None, "text": None}
    assert result["restore"] == ["", "", "", "unknown", "counted", "filter", "", "", ""]
    js = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    assert "StudioZahl.knoten(h, spreadFigure(item, universe))" in js
    assert '$("spread-filter").value = spreadFilterValue(cfg.spread);' in js


def test_the_usage_ranking_button_is_only_enabled_for_a_ready_commander_index() -> None:
    """The usage button ``rk-usage`` is fixed in the page; ``syncRankingToggle`` disables it while
    the index loads, without an index map and in the global view (the check the removed toggle
    test of Q1-b3 covered; review of #1691/#1696)."""
    js = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    block = js[js.index("function syncRankingToggle() {") : js.index("function syncRanking() {")]
    script = (
        block
        + """
const buttons = [{disabled: null}];
let present = true;
const $ = (id) => (id === 'ranking-toggle' && present ? {querySelectorAll: (sel) => (sel === 'button[data-ranking]' ? buttons : [])} : null);
const run = (status, map, view) => { globalThis.state = {view, strength: {status, map}}; buttons[0].disabled = null; syncRankingToggle(); return buttons[0].disabled; };
const out = {
  loading: run('loading', null, 'commander'),
  ready: run('ready', new Map(), 'commander'),
  readyDeck: run('ready', new Map(), 'deck'),
  global: run('ready', new Map(), 'global'),
  noMap: run('ready', null, 'commander'),
  failed: run('error', new Map(), 'commander'),
};
present = false; globalThis.state = {view: 'commander', strength: {status: 'ready', map: new Map()}};
syncRankingToggle(); out.noBox = 'no error';
console.log(JSON.stringify(out));
"""
    )
    assert _node_json(script) == {
        "loading": True,
        "ready": False,
        "readyDeck": False,
        "global": True,
        "noMap": True,
        "failed": True,
        "noBox": "no error",
    }
    html = (STATIC / "tierliste.html").read_text(encoding="utf-8")
    assert 'id="rk-usage"' in html and "disabled" in html.split('id="rk-usage"', 1)[1].split(">")[0]


def test_kartenauswertung_renders_outcomes_cohort_and_few_data_honestly() -> None:
    """kartenauswertung.js renders real card_outcomes.aggregate() payloads honestly (fail-closed on
    status != MEASURED, warnings/provenance shown, hash only when queryId === baseRevision)."""
    from commander_lab.studio.card_outcomes import aggregate, empty_table

    exposures = []
    for i in range(40):
        has_sol = i < 12
        has_rare = i < 2
        hand = ["Island", "Forest", "Plains", "Command Tower", "Cultivate"]
        if has_sol:
            hand.append("Sol Ring")
        if has_rare:
            hand.append("Rare Card")
        while len(hand) < 7:
            hand.append(f"Filler {len(hand)}")
        won = (i % 3 == 0) if has_sol else (i % 4 == 0)
        exposures.append(
            {
                "game_id": f"g-{i}",
                "seed": 1000 + i,
                "engine_commit": "5bd29ab6f318",
                "bridge_jar_sha256": "abc123def4567890",
                "bridge_qualification_state": "BRIDGE_AHEAD_OF_QUALIFICATION",
                "covered_by_sealed_epoch": False,
                "pilot": "GenericCommanderPilot 1.0.0",
                "decision_policy": "heuristic_v1",
                "winner_seats": [0 if won else 1],
                "seats": [
                    {
                        "seat": 0,
                        "deck_id": "chulane@deadbeef1234",
                        "commanders": ["Chulane, Teller of Tales"],
                        "first_dealt_hand": hand,
                        "mulligans_taken": 0,
                        "seen_by_own_turn_3": hand,
                        "result": "win" if won else "loss",
                        "win_credit": 1.0 if won else 0.0,
                    },
                    {
                        "seat": 1,
                        "deck_id": "kaervek",
                        "commanders": ["Kaervek"],
                        "first_dealt_hand": [],
                        "mulligans_taken": 0,
                        "seen_by_own_turn_3": [],
                        "result": "loss" if won else "win",
                        "win_credit": 0.0 if won else 1.0,
                    },
                ],
            }
        )

    payload = aggregate(exposures, deck_id="chulane@deadbeef1234", min_exposed=10, games_skipped=2)  # type: ignore[arg-type]
    # Add an unknown status card to verify fail-closed UI handling.
    payload["cards"].append(
        {**payload["cards"][1], "card": "Unknown Status Card", "status": "BOGUS"}
    )  # type: ignore[typeddict-item]
    empty_payload = empty_table("other-deck", min_exposed=10)

    script = f"""
global.StudioUI = {{
  num: (n, d = 0) => Number(n).toFixed(d).replace('.', ','),
  pct: (r) => `${{(Number(r) * 100).toFixed(1).replace('.', ',')}} %`,
  kids: (...a) => a.flat(Infinity).filter((x) => x !== null && x !== undefined && x !== false),
}};
const mod = require('./kartenauswertung.js');
const textOf = (node) => {{
  if (node === null || node === undefined) return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(textOf).join('');
  return (node.kids || []).map(textOf).join(' ');
}};
const findRows = (node, out = []) => {{
  if (!node || typeof node !== 'object') return out;
  if (Array.isArray(node)) {{ node.forEach((n) => findRows(n, out)); return out; }}
  if (node.tag === 'tr') out.push(node);
  if (node.kids) findRows(node.kids, out);
  return out;
}};
const h = (tag, attrs, ...kids) => ({{ tag, attrs: attrs || {{}}, kids: kids.flat(Infinity) }});
const slot = {{ children: [], replaceChildren(...kids) {{ this.children = kids; }} }};
const payload = {json.dumps(payload)};
const emptyPayload = {json.dumps(empty_payload)};
(async () => {{
  let askedRevUrl = null;
  await mod.renderCardOutcomes(slot, {{
    h,
    deckId: 'chulane',
    baseRevision: 'chulane@deadbeef1234',
    dirty: false,
    api: async (url) => {{
      if (url === '/api/outcomes/decks') return {{ decks: [{{ deck_id: 'chulane@deadbeef1234', games: 40 }}] }};
      askedRevUrl = url;
      return payload;
    }},
  }});
  const revText = textOf(slot.children);
  const rows = findRows(slot.children).slice(1).map((tr) => ({{
    card: textOf(tr.kids[0]),
    rowText: textOf(tr),
  }}));

  let askedDeckUrl = null;
  await mod.renderCardOutcomes(slot, {{
    h,
    deckId: 'chulane',
    baseRevision: 'chulane@deadbeef1234',
    dirty: false,
    api: async (url) => {{
      if (url === '/api/outcomes/decks') return {{ decks: [{{ deck_id: 'chulane', games: 40 }}] }};
      askedDeckUrl = url;
      return {{ ...payload, deck_id: 'chulane' }};
    }},
  }});
  const fallbackText = textOf(slot.children);

  await mod.renderCardOutcomes(slot, {{
    h,
    deckId: 'other-deck',
    baseRevision: 'other-deck@cafe9999',
    dirty: false,
    api: async (url) => {{
      if (url === '/api/outcomes/decks') return {{ decks: [{{ deck_id: 'chulane', games: 40 }}] }};
      return emptyPayload;
    }},
  }});
  const emptyText = textOf(slot.children);

  await mod.renderCardOutcomes(slot, {{
    h,
    deckId: 'chulane',
    baseRevision: 'chulane@deadbeef1234',
    dirty: false,
    api: async (url) => {{
      if (url === '/api/outcomes/decks') return {{ decks: [{{ deck_id: 'chulane@deadbeef1234', games: 40 }}] }};
      const err = new Error('mixed engine commits');
      err.detail = 'mixed engine commits';
      throw err;
    }},
  }});
  const errText = textOf(slot.children);
  console.log(JSON.stringify({{
    askedRevUrl,
    revText,
    rows,
    askedDeckUrl,
    fallbackText,
    emptyText,
    errText,
    zeroRatio: mod.outcomesRatio(0, 0),
  }}));
}})();
"""
    r = _node_json(script)
    assert isinstance(r, dict)
    assert r["askedRevUrl"] == "/api/outcomes?deck_id=chulane%40deadbeef1234"
    rev_text = r["revText"]
    assert "SIMULATED_RESULT" in rev_text
    assert "Exposition zufällig (Mischung), Ergebnis pilotabhängig" in rev_text
    assert "vom Piloten wenig abhängig" not in rev_text
    assert "Gewicht 0" in rev_text
    assert "Deck-Stand (Hash): deadbeef1234" in rev_text
    assert "Siegel-Epoche: nein" in rev_text
    assert "BRIDGE_AHEAD_OF_QUALIFICATION" in rev_text
    assert "abc123def456" in rev_text
    assert "heuristic_v1" in rev_text
    assert "erwartete Zufallsfunde bei 5 %" in rev_text
    assert "EDHREC" not in rev_text and "Top16" not in rev_text

    rows_by_card = {row["card"]: row["rowText"] for row in r["rows"]}
    assert "pp" in rows_by_card["Sol Ring"]
    assert "kein Unterschied nachweisbar bei n=40" in rows_by_card["Sol Ring"]
    assert "pp" not in rows_by_card["Rare Card"]
    assert "pp" not in rows_by_card["Unknown Status Card"]
    assert "unbekannter Status" in rows_by_card["Unknown Status Card"]

    # When baseRevision is not in /api/outcomes/decks, fall back to deck_id without claiming revHash.
    assert r["askedDeckUrl"] == "/api/outcomes?deck_id=chulane"
    assert "über Deck-ID chulane, Deck-Stand der Partien unbekannt" in r["fallbackText"]
    assert "Deck-Stand (Hash): deadbeef1234" not in r["fallbackText"]

    assert "cafe9999" not in r["emptyText"]
    assert "über Deck-ID other-deck, Deck-Stand der Partien unbekannt" in r["emptyText"]
    assert "Sol Ring" not in r["emptyText"]
    assert "mixed engine commits" in r["errText"]
    assert r["zeroRatio"] == "unbekannt"


def test_kartenauswertung_names_deck_states_strata_and_the_unknown_stand() -> None:
    """#1657: the page shows each deck state (hash), the strata count of the stratified table
    and "Stand unbekannt" with its own n; a not-pooled answer shows no combined row.
    #1683: every stratum names its table size; strata of 2, 3 and 4 seats stand apart and a
    stratum without a table size is shown as "Tischgröße unbekannt" with its own n.
    #1687: every stratum also names its pilot fingerprint (short hash)."""
    from commander_lab.studio.card_outcomes import stand_tables
    from tests.unit.test_studio_card_outcomes import PILOT_FP, STATE_A, _simpson, _stated, _with

    pilot = f"Pilot-Fingerabdruck {PILOT_FP[:12]}…"

    a, b = _simpson()
    old = _stated([(["A"], i < 4) for i in range(7)] + [(["F"], False)] * 5, None, prefix="o")
    for game in old:
        game["bridge_qualification_state"] = "BRIDGE_AHEAD_OF_QUALIFICATION"
    pooled = stand_tables([*a, *b, *old], deck_id="deck/a", min_exposed=5)
    only_old = stand_tables(old, deck_id="deck/a", min_exposed=5)
    b_pod = _stated([(["A"], i < 5) for i in range(20)], STATE_A[::-1], prefix="p", opponent="x")
    not_pooled = stand_tables([*a, *b_pod], deck_id="deck/a", min_exposed=5)
    sizes = [
        *_with(_stated([(["A"], i < 2) for i in range(4)], STATE_A, prefix="s3"), table_size=3),
        *_with(_stated([(["A"], i < 2) for i in range(5)], STATE_A, prefix="s4"), table_size=4),
        *_stated([(["A"], i < 2) for i in range(6)], STATE_A, prefix="s2"),
        *_with(_stated([(["A"], i < 2) for i in range(7)], STATE_A, prefix="su"), table_size=None),
    ]
    by_size = stand_tables(sizes, deck_id="deck/a", min_exposed=1)
    script = f"""
global.StudioUI = {{
  num: (n, d = 0) => Number(n).toFixed(d).replace('.', ','),
  pct: (r) => `${{(Number(r) * 100).toFixed(1).replace('.', ',')}} %`,
  kids: (...a) => a.flat(Infinity).filter((x) => x !== null && x !== undefined && x !== false),
}};
const mod = require('./kartenauswertung.js');
const textOf = (node) => {{
  if (node === null || node === undefined) return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(textOf).join('');
  return (node.kids || []).map(textOf).join(' ');
}};
const count = (node, tag) => {{
  if (!node || typeof node !== 'object') return 0;
  if (Array.isArray(node)) return node.reduce((n, k) => n + count(k, tag), 0);
  return (node.tag === tag ? 1 : 0) + count(node.kids || [], tag);
}};
const h = (tag, attrs, ...kids) => ({{ tag, attrs: attrs || {{}}, kids: kids.flat(Infinity) }});
const slot = {{ children: [], replaceChildren(...kids) {{ this.children = kids; }} }};
const render = async (payload) => {{
  await mod.renderCardOutcomes(slot, {{
    h, deckId: 'deck/a', baseRevision: 'deck/a@aaaa', dirty: false,
    api: async (url) => (url === '/api/outcomes/decks' ? {{ decks: [] }} : payload),
  }});
  return {{ text: textOf(slot.children), details: count(slot.children, 'details'),
            tables: count(slot.children, 'table') }};
}};
(async () => {{
  const pooled = await render({json.dumps(pooled)});
  const notPooled = await render({json.dumps(not_pooled)});
  const onlyOld = await render({json.dumps(only_old)});
  const bySize = await render({json.dumps(by_size)});
  const sizeTexts = [1, 4, null].map((v) => mod.outcomesTableSize(v));
  console.log(JSON.stringify({{ pooled, notPooled, onlyOld, bySize, sizeTexts }}));
}})();
"""
    r = _node_json(script)
    assert isinstance(r, dict)
    text = r["pooled"]["text"]
    assert "2 Deck-Stände geschichtet" in text
    assert "Schichten (Deck-Stand, Tischgröße und Pilot-Fingerabdruck): 2" in text
    assert (
        f"Stand unbekannt · Tischgröße: 2 Sitze · {pilot}: 12 Partien (getrennt gezählt, nie addiert)"
        in text
    )
    assert (
        "geschichtet (je Stand eigene Differenz, gewichtet zusammengeführt) · Tischgröße: 2 Sitze"
        f" · {pilot}" in text
    )
    assert "geschichtet über 2 Deck-Stände" in text
    assert "Anteil nur je Deck-Stand" in text
    assert f"Deck-Stand {STATE_A[:12]}…" in text
    assert "deck/a@aaaa" in text
    assert r["pooled"]["details"] == 3  # two known states and "Stand unbekannt"
    assert r["pooled"]["tables"] == 4  # the stratified table and one per state
    # every stand, "Stand unbekannt" included, names its provenance and qualification
    assert text.count("Qualifizierung:") == 4 and text.count("Piloten:") == 4
    assert "BRIDGE_AHEAD_OF_QUALIFICATION (Bridge neuer als Qualifizierung)" in text
    # warning at the top, named by its stratum
    assert (
        f"Stand unbekannt · 2 seats · pilot {PILOT_FP[:12]}: BRIDGE_AHEAD_OF_QUALIFICATION" in text
    )
    old_text = r["onlyOld"]["text"]
    assert (
        "liegen keine Partien vor, in denen Deck-Stand, Tischgröße und Pilot-Fingerabdruck "
        "bekannt sind" in old_text
    )
    assert "noch keine abgeschlossenen Partien" not in old_text
    assert old_text.count("Qualifizierung:") == 2 and r["onlyOld"]["details"] == 1
    nt = r["notPooled"]["text"]
    assert "nicht zusammengeführt" in nt and "pod sets" in nt
    assert "geschichtet über" not in nt
    assert r["notPooled"]["details"] == 2 and r["notPooled"]["tables"] == 2
    st = r["bySize"]["text"]
    assert (
        "3 Schichten (Deck-Stand, Tischgröße und Pilot-Fingerabdruck) nicht zusammengeführt" in st
    )
    assert "Schichten (Deck-Stand, Tischgröße und Pilot-Fingerabdruck): 3" in st
    for size, games in ((2, 6), (3, 4), (4, 5)):
        line = f"Deck-Stand {STATE_A[:12]}… · Tischgröße: {size} Sitze · {pilot} · {games} Partien"
        assert line in st
    assert (
        f"Deck-Stand {STATE_A[:12]}… · Tischgröße unbekannt · {pilot}: 7 Partien "
        "(getrennt gezählt, nie addiert)"
    ) in st
    assert (
        f"Tischgröße unbekannt (Protokollkopf ohne vollständige Sitzliste) · {pilot} · 7 Partien"
        in st
    )
    assert "nie zu einer bekannten Schicht addiert" in st and "table size" in st
    # the reason in German: different table sizes, different base win rates, never combined
    assert (
        "Nicht zusammengeführt: Die Partien stammen von verschiedenen Tischgrößen (2, 3, 4 Sitze)"
        in st
    )
    assert "(bei 2 Sitzen 1/2, bei 3 Sitzen 1/3, bei 4 Sitzen 1/4)" in st
    assert "Jede Schicht steht unten einzeln mit n/N und Herkunft" in st
    # #1694: one section per table size replaces the former "Folgepaket" note
    assert "diese Ansicht kommt als Folgepaket" not in st
    assert (
        "Deck-Stände derselben Kombination aus Tischgröße und Pilot-Fingerabdruck werden unten "
        "in einem eigenen Abschnitt geschichtet"
    ) in st
    assert "Nicht zusammengeführt: the strata" not in st
    assert r["sizeTexts"] == ["Tischgröße: 1 Sitz", "Tischgröße: 4 Sitze", "Tischgröße unbekannt"]
    # the reason in German (#1687 review P3-3); the raw reason stays among the warnings
    assert (
        "Nicht zusammengeführt: Die Deck-Stände wurden gegen verschiedene Gegner-Tische (Pods) "
        "gespielt" in r["notPooled"]["text"]
    )
    assert "Nicht zusammengeführt: the deck states were played" not in r["notPooled"]["text"]
    assert "geschichtet über" not in st
    # three known strata and "Tischgröße unbekannt", each with its own table and provenance
    assert r["bySize"]["details"] == 4 and r["bySize"]["tables"] == 4
    assert st.count("Qualifizierung:") == 5


def test_static_files_send_cache_control_no_cache_and_keep_security_headers(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from commander_lab.studio import StudioStore
    from commander_lab.studio.web import create_app

    folder = tmp_path / "studio"
    store = StudioStore.open(folder)
    store.connection.execute(
        "INSERT OR IGNORE INTO source(source_id, data_class, title, sha256, imported_at) "
        "VALUES ('s1', 'DERIVED_DESCRIPTIVE', 's1', 'h', '2026-11-18')"
    )
    store.connection.execute(
        "INSERT INTO card(card_id, oracle_id, oracle_name, color_identity, source_id) "
        "VALUES ('card:1', 'o1', 'Sol Ring', 'C', 's1')"
    )
    store.connection.execute(
        "INSERT INTO scryfall_card(oracle_id, scryfall_id, name, front_name, layout,"
        " color_identity, commander_legality, keywords, produced_mana, image_front, source_id) "
        "VALUES ('o1', 'scry1', 'Sol Ring', 'Sol Ring', 'normal', '', 'legal', '[]', '[]',"
        " 'https://cards.scryfall.io/normal/front/a/b/ab.jpg', 's1')"
    )
    store.connection.commit()
    store.close()

    with TestClient(create_app(folder), base_url="http://127.0.0.1") as client:
        static_resp = client.get("/app.js")
        assert static_resp.status_code == 200
        assert static_resp.headers.get("cache-control") == "no-cache"
        etag = static_resp.headers.get("etag")
        assert etag
        assert static_resp.headers.get("content-security-policy")
        assert static_resp.headers.get("x-content-type-options") == "nosniff"
        assert static_resp.headers.get("referrer-policy") == "no-referrer"

        not_modified = client.get("/app.js", headers={"If-None-Match": etag})
        assert not_modified.status_code == 304
        assert not_modified.headers.get("cache-control") == "no-cache"
        assert not_modified.headers.get("content-security-policy")
        assert not_modified.headers.get("x-content-type-options") == "nosniff"
        assert not_modified.headers.get("referrer-policy") == "no-referrer"

        api_resp = client.get("/api/status")
        assert api_resp.status_code == 200
        assert api_resp.headers.get("cache-control") == "no-store"

        img_resp = client.get("/img/card:1", follow_redirects=False)
        assert img_resp.status_code == 302
        assert img_resp.headers.get("cache-control") == "max-age=604800"


def test_studio_ui_deduplicates_status_and_layers_and_retries_after_failure() -> None:
    """#1564: StudioUI.request shares /api/status and /api/layers GET promises, runs them
    concurrently in dataState, evicts rejections on failure, and resets via clearSharedCache."""
    ui_source = (STATIC / "ui.js").read_text(encoding="utf-8")
    assert "StudioUI.clearSharedCache()" in (STATIC / "daten.js").read_text(encoding="utf-8")
    script = f"""
const vm = require("vm");
const calls = [];
let failNext = false, inFlight = 0, maxPar = 0, track = false;
const statusBody = {{ freshness: null, source_layers: [], bridge_qualification: {{ status: "ALIGNED_WITH_SEALED_EPOCH" }} }};
const layersBody = {{ layers: [{{ key: "inventory", layer: "Sammlung", rows: 10, covered: 10, pool: 10, status: "COMPLETE" }}], pool_size: 10 }};
const ctx = {{
  console, Promise, Map, Set, Error, Number, Math, Array, Object, String, Boolean, JSON, encodeURIComponent,
  localStorage: {{ getItem: () => null, setItem() {{}} }}, location: {{ pathname: "/index.html" }},
  window: {{ matchMedia: () => ({{ matches: false }}) }},
  document: {{ documentElement: {{ dataset: {{}} }}, addEventListener() {{}}, querySelectorAll: () => [], getElementById: () => null,
    createElement: (t) => ({{ tagName: t.toUpperCase(), className: "", children: [], setAttribute() {{}}, hasAttribute: () => false, addEventListener() {{}}, append(...n) {{ this.children.push(...n); }}, replaceChildren(...n) {{ this.children = n; }} }}) }},
  fetch: (path, opts) => {{
    calls.push({{ path, method: (opts && opts.method) || "GET" }});
    if (track) {{ inFlight += 1; maxPar = Math.max(maxPar, inFlight); }}
    return new Promise((res, rej) => setTimeout(() => {{
      if (track) inFlight -= 1;
      if (path === "/api/status" && failNext) {{ failNext = false; rej(new Error("boom")); return; }}
      const body = path.startsWith("/api/layers") ? layersBody : path === "/api/status" ? statusBody : {{ n: calls.length }};
      res({{ ok: true, status: 200, statusText: "OK", json: async () => body }});
    }}, 5));
  }},
}};
vm.createContext(ctx);
vm.runInContext({json.dumps(ui_source)} + "\\nglobalThis.StudioUI = StudioUI;", ctx);
(async () => {{
  const UI = ctx.StudioUI, host = {{ replaceChildren() {{}} }}, count = (p) => calls.filter((c) => c.path === p).length;
  const [s1, s2] = await Promise.all([UI.request("/api/status"), UI.request("/api/status")]);
  const s3 = await UI.request("/api/status");
  const [l1, l2] = await Promise.all([UI.request("/api/layers?commander=Chulane"), UI.request("/api/layers?commander=Chulane")]);
  await UI.dataState(host, "Chulane");
  const shared = [count("/api/status"), count("/api/layers?commander=Chulane")];
  UI.clearSharedCache(); track = true; await UI.dataState(host, "Chulane"); track = false;
  const refreshed = [count("/api/status"), count("/api/layers?commander=Chulane")];
  UI.clearSharedCache(); failNext = true;
  let failedOnce = false;
  try {{ await UI.request("/api/status"); }} catch (_) {{ failedOnce = true; }}
  const recovered = await UI.request("/api/status");
  const [d1, d2] = [await UI.request("/api/decks"), await UI.request("/api/decks")];
  console.log(JSON.stringify([
    JSON.stringify(s1) === JSON.stringify(s2) && JSON.stringify(s2) === JSON.stringify(s3),
    JSON.stringify(l1) === JSON.stringify(l2), shared, refreshed, maxPar, failedOnce,
    Boolean(recovered && recovered.bridge_qualification), count("/api/decks"), d1.n !== d2.n,
  ]));
}})();
"""
    assert _node_json(script) == [True, True, [1, 1], [2, 2], 2, True, True, 2, True]


def test_tierliste_init_parallelizes_independent_requests_and_keeps_equivalence() -> None:
    """#1564: tierliste.js starts independent fetches in parallel, fires strength once after
    universe without waiting for evidence/decks, keeps loading state, and preserves equivalence."""
    js = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    rhead = js[
        js.index("function render(keepScroll = true) {") : js.index("const cards = visibleCards();")
    ]
    assert rhead.index("if (!state.data) return;") < rhead.index("body.replaceChildren();")
    slices = [
        ("async function selectUniverse(name) {", "// ---------- strength index ----------"),
        ("async function initStrength() {", "// ---------- data state banner ----------"),
        ("async function dataBanner() {", "// ---------- loading ----------"),
        ("async function loadEvidence() {", "// ---------- marks and deck from the table"),
        ("async function loadRoleAudit() {", "async function setView(view) {"),
        ("async function setView(view) {", "function renderTabs() {"),
    ]
    parts = "\n".join(js[js.index(a) : js.index(b)] for a, b in slices)
    init_tail = js[js.index("await StudioCommander.fill(") : js.index("init().catch(")].rsplit(
        "}", 1
    )[0]
    script = f"""
const harness = {json.dumps(parts)}, tailCode = {json.dumps(init_tail)};
async function runOrder(delays) {{
  let strengthCalls = 0, strBeforeEv = false, strBeforeDecks = false, evDone = false, decksDone = false, anyDone = false;
  const wave1 = new Set(), snaps = [], els = new Map(), noop = () => {{}};
  const $ = (id) => {{ if (!els.has(id)) els.set(id, {{ id, value: "", hidden: false, options: [], children: [], classList: {{ add() {{}}, remove() {{}}, toggle() {{}} }}, addEventListener() {{}}, replaceChildren(...k) {{ this.children = k; if (k.length && k[0] && k[0].props && k[0].props.value !== undefined) this.value = k[0].props.value; }}, append(...k) {{ this.children.push(...k); }} }}); return els.get(id); }};
  $("pool-body").replaceChildren("LOADING");
  const COMMANDER = "Chulane, Teller of Tales";
  const state = {{ view: "commander", ticket: 0, data: null, pool: new Map(), marks: new Map(), decks: [], deckCards: new Map(), deckRoles: {{}}, roleAudit: null, cohortShapes: [], universe: {{ ticket: 0, name: "", profiles: [], options: null, summary: null, spread: null }}, strength: {{ status: "idle", meta: null, profiles: [], counted: [], settings: null, result: null, map: null, ticket: 0 }} }};
  const render = () => {{ if (!state.data) return; snaps.push({{ cards: state.data.cards.map((c) => c.card_id), marks: [...state.marks.keys()].sort(), deck: [...state.deckCards.keys()].sort(), universe: state.universe.name, strengthProfile: state.strength.settings ? state.strength.settings.universe_profile : null, strengthReady: state.strength.status === "ready" }}); }};
  const refreshStrength = async () => {{
    strengthCalls += 1; if (!evDone) strBeforeEv = true; if (!decksDone) strBeforeDecks = true;
    await new Promise((r) => setTimeout(r, delays.strength || 5));
    state.strength.result = {{ cards: [{{ card_id: "c1", tier: "S" }}] }}; state.strength.status = "ready"; render();
  }};
  const replies = {{
    "/api/evidence": () => ({{ cards: [{{ card_id: "c1", group: "Creature", roles: ["ramp"] }}] }}),
    "/api/marks": () => ({{ c1: {{ favorite: true, excluded: false, note: "top" }} }}),
    "/api/universe/profiles": () => ([{{ name: "u1" }}]), "/api/universe/options": () => ({{ ok: true }}),
    "/api/universe/spread": () => ({{ universe: "u1", cards: [{{ card_id: "c1" }}] }}),
    "/api/decks": () => ([{{ deck_id: "d1", name: "Chulane", commanders: [COMMANDER], branches: [{{ branch: "main", revision_id: "r1" }}] }}]),
    "/api/revisions/r1": () => ({{ cards: [{{ card_id: "c1", zone: "main", quantity: 1 }}], roles: {{}} }}),
    "/api/strength/presets": () => ({{ layers: [], recommended: {{ universe_source: "auto" }} }}),
    "/api/strength/profiles": () => [], "/api/universe/counted": () => [], "/api/roles/audit": () => ({{ rows: [] }}),
    "/api/data-report": () => ({{ corpus: {{ card_rows_without_oracle_id: {{ count: 0, of: 10 }} }} }}),
  }};
  const api = (path) => {{
    const key = path.split("?")[0]; if (!anyDone) wave1.add(key);
    return new Promise((res) => setTimeout(() => {{
      anyDone = true; if (key === "/api/evidence") evDone = true; if (key === "/api/decks") decksDone = true;
      res(replies[key] ? replies[key]() : key.startsWith("/api/universe/profiles/") ? {{ decks: 50 }} : key.endsWith("/draft") ? {{ draft: null }} : []);
    }}, delays[key] !== undefined ? delays[key] : 5));
  }};
  const names = "COMMANDER,state,$,StudioCommander,StudioUI,h,nf,typeLabel,cardRoles,roleName,rememberedUniverse,rememberUniverse,fillUniverseSelect,renderUniversePanel,fillSortOptions,rememberedStrength,rememberStrength,withDefaults,renderStrengthPanel,renderTierBar,syncRankGroupToggle,syncRanking,renderNotice,renderRoleAuditPanel,updateMethodHint,fillBranches,toast,fail,render,refreshStrength,api".split(",");
  const fn = new Function(...names, harness + "\\nreturn (async () => {{\\n" + tailCode + "\\n}})();");
  await fn(COMMANDER, state, $, {{ fill: async () => {{}} }}, {{ recall: () => "", remember: noop, germanError: String, dataState: async () => {{}} }},
    (tag, props, ...kids) => ({{ tag, props, kids }}), String, (x) => x, (c) => c.roles || [], (x) => x,
    () => "u1", noop, noop, noop, noop, () => null, noop, (x) => ({{ ...x }}),
    noop, noop, noop, noop, noop, noop, noop,
    () => {{ $("branch-select").options = [{{ value: "main" }}]; $("branch-select").value = "main"; }},
    noop, (e) => {{ throw e; }}, render, refreshStrength, api);
  return {{ wave1: [...wave1].sort(), strengthCalls, strBeforeEv, strBeforeDecks, loadingPreserved: $("pool-body").children[0] === "LOADING", finalSnap: snaps[snaps.length - 1] }};
}}
(async () => {{
  const slow = await runOrder({{ "/api/evidence": 60, "/api/decks": 60, "/api/marks": 30, "/api/universe/profiles": 5, "/api/universe/options": 5, "/api/strength/presets": 5, "/api/strength/profiles": 5, "/api/universe/counted": 5, strength: 5 }});
  const fast = await runOrder({{ "/api/evidence": 5, "/api/decks": 5, "/api/marks": 40, "/api/universe/profiles": 30, "/api/universe/options": 30, "/api/strength/presets": 30, "/api/strength/profiles": 30, "/api/universe/counted": 30, strength: 10 }});
  console.log(JSON.stringify({{ slow, fast }}));
}})();
"""
    result = _node_json(script)
    assert isinstance(result, dict)
    slow, fast = result["slow"], result["fast"]
    expected_w1 = [
        "/api/marks",
        "/api/evidence",
        "/api/roles/audit",
        "/api/universe/profiles",
        "/api/universe/options",
        "/api/decks",
        "/api/strength/presets",
        "/api/strength/profiles",
        "/api/universe/counted",
        "/api/data-report",
    ]
    assert set(expected_w1).issubset(set(slow["wave1"])), slow["wave1"]
    assert slow["strengthCalls"] == 1 and fast["strengthCalls"] == 1
    assert slow["strBeforeEv"] and slow["strBeforeDecks"] and slow["loadingPreserved"]
    expected_snap = {
        "cards": ["c1"],
        "marks": ["c1"],
        "deck": ["c1"],
        "universe": "u1",
        "strengthProfile": "u1",
        "strengthReady": True,
    }
    assert slow["finalSnap"] == fast["finalSnap"] == expected_snap


def test_play_p1a_accessibility_focus_and_static_sinks() -> None:
    """Issue #1529 (Play P1a): keyboard focus, stack rail, own-combat label, yield modes,
    and no innerHTML / style= / .toFixed( in the Play P1a files."""
    html = (STATIC / "partie.html").read_text(encoding="utf-8")
    css = (STATIC / "partie.css").read_text(encoding="utf-8")
    partie_js = (STATIC / "partie.js").read_text(encoding="utf-8")
    p1a_js = (STATIC / "play_p1a.js").read_text(encoding="utf-8")
    vorspulen_js = (STATIC / "vorspulen.js").read_text(encoding="utf-8")
    boardclick_js = (STATIC / "boardclick.js").read_text(encoding="utf-8")

    assert html.index('src="play_p1a.js"') < html.index('src="partie.js"')
    for token in (
        'id="ff-mode"',
        'aria-label="Vorspul-Modus"',
        'value="until_my_turn"',
        'value="until_end_of_turn"',
        'value="until_stack_resolves"',
        'id="own-combat"',
        'id="ff-stack-hint"',
        'class="stack-rail"',
    ):
        assert token in html, token

    for rule in (
        "#ff-mode:focus-visible",
        "button.card:focus-visible",
        ".own-combat",
    ):
        assert rule in css, rule

    # the stack items do nothing themselves (their card tile is the only control): no extra tab stop
    assert "tabindex" not in partie_js
    # the book-keeping of an answer runs in play_p1a.js (node-tested), after the engine accepted it;
    # both automatic passes hand over their reason instead of writing the log line themselves
    assert "StudioPlayP1a.submitAnswer(" in partie_js
    for wiring in (
        " getPendingDecision: () => state.pendingDecision",
        ' post: (body) => api(`/api/play/${encodeURIComponent(state.gameId)}/decision`, "POST", body)',
        " getLedger: () => state.ownCombat",
        " setLedger: (ledger) => { state.ownCombat = ledger; }",
        " logAutoPass: appendAutoPassLog",
    ):
        assert wiring in partie_js, wiring
    assert partie_js.count("autoPassReason:") == 2
    assert "appendAutoPassLog(pending" not in partie_js
    assert "StudioPlayP1a.ownCombatView(" in partie_js
    assert "StudioPlayP1a.clearOwnCombatLedger(" not in partie_js
    assert "syncFastForwardControls()" in partie_js and "StudioFastForward.retarget(" in partie_js
    assert "beginning_combat" not in partie_js
    assert "eigene Angaben" in p1a_js

    for name, src in (
        ("play_p1a.js", p1a_js),
        ("vorspulen.js", vorspulen_js),
        ("boardclick.js", boardclick_js),
        ("partie.js", partie_js),
        ("partie.html", html),
    ):
        for forbidden in ("innerHTML", "outerHTML", "style=", 'setAttribute("style"', ".toFixed("):
            assert forbidden not in src, f"{name}: {forbidden}"

    for sink in ("document.", "window.", "fetch(", "eval("):
        assert sink not in p1a_js, sink


def test_home_page_reserves_layout_space_against_cls() -> None:
    """#1567: app.css reserves dimensions for async headers, filters, data-state and deck tabs
    so populating the home page does not cause large layout shifts, with no inline styles."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    for required in (
        "#brand{min-height:",
        "#brand #commander-select{min-width:",
        "#brand #theme-toggle{min-width:",
        "#top{min-height:",
        "#data-state{min-height:",
        "#color-filter{min-width:",
        "#bracket-bar{flex:1 0 100%;min-height:",
        "#quick-filter-presets{flex:1 0 100%;min-height:",
        "#view-toggle{min-width:",
        "#deck-tabs{min-height:",
        "#pool>#filters{min-height:",
    ):
        assert required in css, f"missing CLS layout reservation rule: {required}"
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "style=" not in html


def test_wishlist_js_behavior_and_static_guards() -> None:
    """#1636 / #1187: StudioWishlist pure helpers (ownership summary, wishlist text without
    prices, literal Oracle Superfriends filters) run in node and respect all static guards."""
    wishlist_js = (STATIC / "wishlist.js").read_text(encoding="utf-8")
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert html.index('src="wishlist.js"') < html.index('src="app.js"')
    assert 'id="f-unowned"' in html
    assert "include_unowned=true" in app_js
    assert "Zukauf (0 im Besitz)" in app_js
    assert "Zukauf-Liste kopieren" in app_js
    # n/N (#1648): both counts over the 100 cards of a Commander deck, with their origin.
    assert (
        "`Im Besitz: ${StudioUI.num(ownership.owned, 0)}/100 · "
        "Zukauf: ${StudioUI.num(ownership.missing, 0)}/100`"
    ) in app_js
    assert "ein Commander-Deck hat 100" in app_js
    # Collection and Zukauf cards are counted apart for the simulator readiness.
    assert "pool.sim_readiness_unowned" in app_js

    for name, src in (("wishlist.js", wishlist_js), ("index.html", html)):
        for forbidden in ("innerHTML", "outerHTML", "style=", 'setAttribute("style"', ".toFixed("):
            assert forbidden not in src, f"{name}: {forbidden}"
    for sink in ("document.", "window.", "fetch(", "eval("):
        assert sink not in wishlist_js, sink

    script = """
const W = require('./wishlist.js');
const pool = new Map([
  ['c1', { card_id: 'c1', name: 'Sol Ring', owned: 1, in_collection: true, type_line: 'Artifact', oracle_text: '{T}: Add {C}{C}.' }],
  ['c2', { card_id: 'c2', name: 'Teferi, Hero of Dominaria', owned: 0, in_collection: false, type_line: 'Legendary Planeswalker — Teferi', oracle_text: '+1: Draw a card.' }],
  ['c3', { card_id: 'c3', name: 'Flux Channeler', owned: 0, in_collection: false, type_line: 'Creature — Human Wizard', text: 'Whenever you cast a noncreature spell, proliferate.' }],
  ['c4', { card_id: 'c4', name: 'Forest', owned: 2, in_collection: true, type_line: 'Basic Land — Forest', oracle_text: '' }],
]);
const deck = [
  { card_id: 'c1', quantity: 1 },
  { card_id: 'c2', quantity: 1 },
  { card_id: 'c3', quantity: 1 },
  { card_id: 'c4', quantity: 4 },
];
const extra = new Map(Object.entries({
  k1: { text: 'Put a +1/+1 counter on target creature.' },
  k2: { oracle_text: 'Teferi enters with five loyalty counters.' },
  k3: { text: 'Remove a counter from target permanent.' },
  k4: { text: 'Counter target spell.' },
  k5: { text: 'Counter that spell unless its controller pays {1}. Counter a spell.' },
  k6: { text: 'Whenever you cast a spell, counter it. Then put two charge counters on this.' },
  k7: { text: '' },
  k15: { text: 'Loyalty abilities of planeswalkers you control cost {1} less.' },
  k8: { roles: ['ramp', 'board_wipe'] },
  k9: { roles: ['removal'] },
  k10: { roles: [] },
  k11: { produced_mana: 'WUBRG' },
  k12: { produced_mana: 'WUBR' },
  k13: { produced_mana: 'C' },
  k14: {},
}));
const summary = W.summarizeDeckOwnership(deck, pool);
const text = W.formatWishlistText(summary.missingCards);
console.log(JSON.stringify({
  total: summary.total,
  owned: summary.owned,
  missing: summary.missing,
  missingNames: summary.missingCards.map((c) => c.name),
  text,
  emptyText: W.formatWishlistText([]),
  pwMatch: W.matchesSuperfriendsFilter(pool.get('c2'), 'planeswalker'),
  pwNonMatch: W.matchesSuperfriendsFilter(pool.get('c3'), 'planeswalker'),
  prolifMatch: W.matchesSuperfriendsFilter(pool.get('c3'), 'proliferate'),
  prolifNonMatch: W.matchesSuperfriendsFilter(pool.get('c2'), 'proliferate'),
  missingMatch: W.matchesSuperfriendsFilter(pool.get('c2'), 'missing'),
  missingNonMatch: W.matchesSuperfriendsFilter(pool.get('c1'), 'missing'),
  counters: Object.fromEntries(['k1', 'k2', 'k3', 'k4', 'k5', 'k6', 'k7', 'k15'].map(
    (id) => [id, W.matchesSuperfriendsFilter(extra.get(id), 'counters')])),
  wipes: Object.fromEntries(['k8', 'k9', 'k10'].map(
    (id) => [id, W.matchesSuperfriendsFilter(extra.get(id), 'boardwipe')])),
  fiveColor: Object.fromEntries(['k11', 'k12', 'k13', 'k14'].map(
    (id) => [id, W.matchesSuperfriendsFilter(extra.get(id), 'fixing5c')])),
  unknownKind: W.matchesSuperfriendsFilter(pool.get('c1'), 'nonsense'),
}));
"""
    result = _node_json(script)
    assert result == {
        "total": 7,
        "owned": 3,
        "missing": 4,
        "missingNames": ["Flux Channeler", "Forest", "Teferi, Hero of Dominaria"],
        "text": "1 Flux Channeler\n2 Forest\n1 Teferi, Hero of Dominaria",
        "emptyText": "",
        "pwMatch": True,
        "pwNonMatch": False,
        "prolifMatch": True,
        "prolifNonMatch": False,
        "missingMatch": True,
        "missingNonMatch": False,
        # the noun "counter" and "loyalty" match; the verb "counter target spell" does not
        "counters": {
            "k1": True,
            "k2": True,
            "k3": True,
            "k4": False,
            "k5": False,
            "k6": True,
            "k7": False,
            "k15": True,
        },
        # the tagger role only; a card without role data is unknown and does not match
        "wipes": {"k8": True, "k9": False, "k10": False},
        # all five letters; four colors, colorless and a missing field do not match
        "fiveColor": {"k11": True, "k12": False, "k13": False, "k14": False},
        "unknownKind": True,
    }
    for chip in ("counters", "boardwipe", "fixing5c"):
        assert f'sfChip("{chip}"' in app_js, chip
    assert (
        "if (dropped) toast(`${StudioUI.num(dropped, 0)} von" in app_js
    )  # useCards says what it left out (#1648)
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "async function ensureUnownedLoadedFor(" in app_js
    assert app_js.count("await ensureUnownedLoadedFor(") >= 4
