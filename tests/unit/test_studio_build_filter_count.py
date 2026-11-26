"""Tests for the BUILD #filter-count active filter pill (#1833)."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from commander_lab.studio.web import STATIC


def _run_node_filter_probe() -> dict[str, object]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")

    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    start_marker = "function activeFilters() {"
    end_marker = "function setFiltersOpen("
    start_idx = app_js.index(start_marker)
    end_idx = app_js.index(end_marker)
    snippet = app_js[start_idx:end_idx]

    script = f"""
const elements = new Map();
const makeEl = (id, init = {{}}) => {{
  const el = {{ id, value: '', checked: false, hidden: true, textContent: '', title: '', ...init }};
  elements.set(id, el);
  return el;
}};
function resetAll() {{
  makeEl('filter-count');
  makeEl('q');
  makeEl('type-filter');
  makeEl('role-filter');
  makeEl('label-filter');
  makeEl('mv-min');
  makeEl('mv-max');
  makeEl('f-free', {{ checked: true }});
  makeEl('f-notin', {{ checked: false }});
  makeEl('f-fav', {{ checked: false }});
  makeEl('f-excl', {{ checked: false }});
  makeEl('f-sim', {{ checked: false }});
  makeEl('f-unowned', {{ checked: false }});
  state.colors = new Set();
  state.superfriendsFilter = '';
  state.cohort = 'all';
  state.gcBand = '';
  state.universe = '';
  state.subset = null;
}}
const state = {{}};
const $ = (id) => elements.get(id) || null;
const StudioUI = {{ num: (v) => String(v) }};
const cohortName = (k) => (k === 'bracket:4' ? 'Bracket 4' : k);

{snippet}

const readChip = () => ({{
  hidden: $('filter-count').hidden,
  text: $('filter-count').textContent,
  title: $('filter-count').title,
  ...activeFilters(),
}});

resetAll();
updateFilterChip();
const initial = readChip();

const cases = [
  ['color_G', () => state.colors.add('G'), 'Farbe (G)'],
  ['search_q', () => {{ $('q').value = 'sol'; }}, 'Suche'],
  ['type', () => {{ $('type-filter').value = 'Creature'; }}, 'Typ'],
  ['role', () => {{ $('role-filter').value = 'ramp'; }}, 'Rolle'],
  ['label', () => {{ $('label-filter').value = 'blink'; }}, 'Marke'],
  ['mv_min', () => {{ $('mv-min').value = '2'; }}, 'Manawert'],
  ['mv_max', () => {{ $('mv-max').value = '4'; }}, 'Manawert'],
  ['not_free', () => {{ $('f-free').checked = false; }}, 'auch belegte'],
  ['notin', () => {{ $('f-notin').checked = true; }}, 'nicht im Deck'],
  ['fav', () => {{ $('f-fav').checked = true; }}, 'Favoriten'],
  ['excl', () => {{ $('f-excl').checked = true; }}, 'Ausgeschlossene'],
  ['sim', () => {{ $('f-sim').checked = true; }}, 'Simulator-bereit'],
  ['unowned', () => {{ $('f-unowned').checked = true; }}, 'Zukauf-Pool'],
  ['superfriends', () => {{ state.superfriendsFilter = 'planeswalker'; }}, 'Schnellfilter (planeswalker)'],
  ['cohort_bracket4', () => {{ state.cohort = 'bracket:4'; }}, 'Kohorte (Bracket 4)'],
  ['gc_band', () => {{ state.gcBand = 'gc_band:1-3'; }}, 'Game-Changer-Band'],
  ['universe', () => {{ state.universe = 'mein-univ'; }}, 'Universum (mein-univ)'],
  ['subset', () => {{ state.subset = {{ info: {{ label: 'subset' }} }}; }}, 'Teilmenge'],
];

const singleResults = {{}};
for (const [name, setup, expectedLabel] of cases) {{
  resetAll();
  setup();
  updateFilterChip();
  singleResults[name] = {{ chip: readChip(), expectedLabel }};
}}

resetAll();
state.colors.add('G');
state.cohort = 'bracket:4';
updateFilterChip();
const combined = readChip();

resetAll();
updateFilterChip();
const afterReset = readChip();

console.log(JSON.stringify({{ initial, singleResults, combined, afterReset }}));
"""
    done = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


def test_build_filter_count_counts_every_filter_group_and_resets_cleanly() -> None:
    """#1833: every active filter group (including color, search, cohort/bracket, gcBand,
    universe, subset, and secondary filters) increments #filter-count and resets to 0."""
    res = _run_node_filter_probe()

    initial = res["initial"]
    assert isinstance(initial, dict)
    assert initial["count"] == 0
    assert initial["text"] == "0 aktiv"
    assert initial["hidden"] is True

    single_results = res["singleResults"]
    assert isinstance(single_results, dict)
    assert len(single_results) == 18
    for name, entry in single_results.items():
        chip = entry["chip"]
        expected = entry["expectedLabel"]
        assert chip["count"] == 1, f"{name}: {chip}"
        assert chip["text"] == "1 aktiv", f"{name}: {chip}"
        assert chip["hidden"] is False, f"{name}: {chip}"
        assert expected in chip["title"], f"{name}: {chip}"

    combined = res["combined"]
    assert isinstance(combined, dict)
    assert combined["count"] == 2
    assert combined["text"] == "2 aktiv"
    assert combined["hidden"] is False
    assert "Farbe (G)" in combined["title"]
    assert "Kohorte (Bracket 4)" in combined["title"]

    after_reset = res["afterReset"]
    assert isinstance(after_reset, dict)
    assert after_reset["count"] == 0
    assert after_reset["text"] == "0 aktiv"
    assert after_reset["hidden"] is True
