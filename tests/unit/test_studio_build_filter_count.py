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
    cohort_consts_start = app_js.index("const COHORT_NAMES = {")
    cohort_consts_end = app_js.index("const ROLE_NAMES = {")
    cohort_consts = app_js[cohort_consts_start:cohort_consts_end]

    cohort_fn_start = app_js.index("const COHORT_PREFIX = {")
    cohort_fn_end = app_js.index("function mana(cost)")
    cohort_fn = app_js[cohort_fn_start:cohort_fn_end]

    start_marker = "function activeFilters() {"
    end_marker = "function setFiltersOpen("
    start_idx = app_js.index(start_marker)
    end_idx = app_js.index(end_marker)
    snippet = app_js[start_idx:end_idx]

    preset_start = app_js.index("const applyBuilderFilterPreset = async (cfg) => {")
    preset_end = app_js.index("  };\n  renderQuickFilterPresets();", preset_start) + 4
    preset_snippet = app_js[preset_start:preset_end]

    script = f"""
const elements = new Map();
const makeEl = (id, init = {{}}) => {{
  const el = {{
    id,
    value: '',
    checked: false,
    hidden: true,
    textContent: '',
    title: '',
    listeners: {{}},
    attrs: {{}},
    children: [],
    classList: {{
      _set: new Set(),
      add(c) {{ this._set.add(c); }},
      toggle(c, on) {{ if (on === undefined) {{ if (this._set.has(c)) this._set.delete(c); else this._set.add(c); }} else if (on) this._set.add(c); else this._set.delete(c); }},
      contains(c) {{ return this._set.has(c); }},
    }},
    setAttribute(k, v) {{ this.attrs[k] = String(v); }},
    querySelectorAll() {{ return []; }},
    replaceChildren(...kids) {{ this.children = kids; }},
    ...init,
  }};
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
  makeEl('cohort', {{ value: 'all' }});
  makeEl('universe', {{ value: '' }});
  makeEl('color-filter');
  makeEl('quick-filter-presets');
  state.colors = new Set();
  state.superfriendsFilter = '';
  state.cohort = 'all';
  state.gcBand = '';
  state.universe = '';
  state.subset = null;
  state.subsetNames = [];
  state.subsetWanted = null;
  state.includeUnowned = false;
  state.shown = 120;
}}
const state = {{}};
const $ = (id) => elements.get(id) || null;
let subsetTicket = 0;
const memory = new Map();
const toasts = [];
const StudioUI = {{
  num: (v) => String(v),
  remember: (k, v) => memory.set(k, v),
  recall: (k, d) => (memory.has(k) ? memory.get(k) : d),
}};
const toast = (m) => toasts.push(m);
const h = (tag, props, ...children) => ({{ tag, ...(props || {{}}), label: children.join('') }});
const fail = (e) => {{ throw e; }};
const loadPool = async () => {{}};
const renderAll = () => {{ renderBracketBar(); renderGcBandBar(); renderUniverseInfo(); renderPool(); renderDeck(); }};
const renderBracketBar = () => {{}};
const renderGcBandBar = () => {{}};
const renderUniverseInfo = () => {{}};
const renderPool = () => {{ updateFilterChip(); }};
const renderDeck = () => {{}};

{cohort_consts}
{cohort_fn}
{snippet}

const readChip = () => ({{
  hidden: $('filter-count').hidden,
  text: $('filter-count').textContent,
  title: $('filter-count').title,
  ...activeFilters(),
}});

async function run() {{
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

  // Choosing #universe disables cohort filtering via activeScope(); #filter-count must not double-count cohort.
  resetAll();
  state.cohort = 'bracket:4';
  state.universe = 'mein-univ';
  updateFilterChip();
  const universeOverridesCohort = readChip();

  // Test applyBuilderFilterPreset + save/restore view including label-filter and f-sim
  resetAll();
  {preset_snippet}
  $('q').value = 'sol';
  $('label-filter').value = 'blink';
  $('f-sim').checked = true;
  state.cohort = 'bracket:4';
  renderQuickFilterPresets();
  const btns = $('quick-filter-presets').children;
  const saveBtn = btns.find((b) => b.label === 'Ansicht merken');
  const loadBtn = btns.find((b) => b.label === 'Gemerkte Ansicht');
  const resetBtn = btns.find((b) => b.label === 'Standardfilter');
  saveBtn.onclick();
  await resetBtn.onclick();
  const afterPresetReset = {{
    chip: readChip(),
    label: $('label-filter').value,
    sim: $('f-sim').checked,
    cohort: state.cohort,
  }};
  await loadBtn.onclick();
  const afterRestored = {{
    chip: readChip(),
    q: $('q').value,
    label: $('label-filter').value,
    sim: $('f-sim').checked,
  }};

  console.log(JSON.stringify({{
    initial,
    singleResults,
    combined,
    universeOverridesCohort,
    afterPresetReset,
    afterRestored,
  }}));
}}

run().catch((err) => {{ console.error(err); process.exit(1); }});
"""
    done = subprocess.run([node, "-e", script], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr or done.stdout
    return json.loads(done.stdout)


def test_build_filter_count_counts_every_filter_group_and_resets_cleanly() -> None:
    """#1833: every active filter group (including color, search, cohort/bracket, gcBand,
    universe, subset, and secondary filters) increments #filter-count and resets cleanly."""
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

    universe_override = res["universeOverridesCohort"]
    assert isinstance(universe_override, dict)
    assert universe_override["count"] == 1
    assert universe_override["labels"] == ["Universum (mein-univ)"]

    after_preset_reset = res["afterPresetReset"]
    assert isinstance(after_preset_reset, dict)
    assert after_preset_reset["chip"]["count"] == 0
    assert after_preset_reset["label"] == ""
    assert after_preset_reset["sim"] is False
    assert after_preset_reset["cohort"] == "all"

    after_restored = res["afterRestored"]
    assert isinstance(after_restored, dict)
    assert after_restored["q"] == "sol"
    assert after_restored["label"] == "blink"
    assert after_restored["sim"] is True
    assert after_restored["chip"]["count"] == 3
