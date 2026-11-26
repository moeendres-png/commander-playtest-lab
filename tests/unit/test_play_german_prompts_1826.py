"""Tests for #1826: German game-sentence prompts, HTML-free rendering, and mana-pool pips."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_JS = REPO_ROOT / "src" / "commander_lab" / "studio" / "static" / "prompts.js"
PARTIE_HTML = REPO_ROOT / "src" / "commander_lab" / "studio" / "static" / "partie.html"
PARTIE_JS = REPO_ROOT / "src" / "commander_lab" / "studio" / "static" / "partie.js"


def _run_node(script: str) -> dict[str, object]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node binary unavailable")
    src = PROMPTS_JS.read_text(encoding="utf-8")
    full = "\n".join(
        [
            src,
            """
const h = (tag, props, ...children) => {
  const kids = [];
  for (const ch of children.flat(Infinity)) {
    if (ch === null || ch === undefined || ch === false) continue;
    kids.push(typeof ch === "object" && ch.tag ? ch : { text: String(ch) });
  }
  return { tag, props: props || {}, children: kids };
};
const flattenText = (node) => {
  if (typeof node === "string") return node;
  if (node && typeof node.text === "string") return node.text;
  if (!node || !Array.isArray(node.children)) return "";
  return node.children.map(flattenText).join("");
};
const collectPips = (node, out = []) => {
  if (!node || typeof node !== "object") return out;
  const cls = node.props && typeof node.props.class === "string" ? node.props.class : "";
  if (cls.includes("mana-pip")) out.push({ cls, text: flattenText(node), title: node.props.title });
  for (const ch of node.children || []) collectPips(ch, out);
  return out;
};
""",
            script,
        ]
    )
    proc = subprocess.run([node, "-e", full], check=False, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip())


def test_partie_html_loads_prompts_before_partie() -> None:
    html = PARTIE_HTML.read_text(encoding="utf-8")
    prompts_pos = html.index('<script src="prompts.js"></script>')
    partie_pos = html.index('<script src="partie.js"></script>')
    assert prompts_pos < partie_pos


def test_raw_html_mana_prompt_regression_from_audit_play_24() -> None:
    data = _run_node(
        """
const assert = require("assert");
const rawAudit24Prompt = "{G}<div style='font-size:11pt'><font color='#224488'>Choose mana to pay for <b>Crop Rotation</b> {G}</font></div>&nbsp;";
const localized = StudioPrompts.localizePrompt(
  {
    decision_class: "mana_payment",
    prompt: rawAudit24Prompt,
    context: { unpaid_mana: "{G}" },
  },
  "mana_payment"
);
assert.ok(!localized.includes("<") && !localized.includes(">"), "raw HTML leaked: " + localized);
assert.ok(!localized.includes("style="), "raw style leaked: " + localized);
assert.ok(!/choose mana/i.test(localized), "English leak: " + localized);
const container = h("div", { class: "human-prompt" }, ...StudioPrompts.renderRichGameText(h, localized));
const pips = collectPips(container);
assert.strictEqual(pips.length, 1);
assert.ok(pips[0].cls.includes("mana-g"));
assert.strictEqual(pips[0].text, "G");
const localizedNoCtx = StudioPrompts.localizePrompt(
  rawAudit24Prompt,
  "mana_payment"
);
assert.strictEqual(
  localizedNoCtx,
  "Mana bezahlen — offen: {G}. Wähle eine Mana-Quelle oder Pool-Mana.",
  "Must not duplicate {G} when context.unpaid_mana is absent: " + localizedNoCtx
);
assert.strictEqual(
  StudioPrompts.localizePrompt("Select target", "target"),
  "Wähle ein legales Ziel für diesen Zauber oder diese Fähigkeit."
);
assert.ok(!/[<>]/.test(StudioPrompts.stripHtmlAndNormalize("<<script>>alert(1)<</script>> &lt;b&gt;Hi&lt;/b&gt; <div title=1")));
const arbitraryBrace = h("div", {}, ...StudioPrompts.renderRichGameText(h, "Return {this} to hand {2/W}{G/P}{T}"));
const mixedPips = collectPips(arbitraryBrace);
assert.deepStrictEqual(mixedPips.map((p) => p.text), ["2/W", "G/P", "⟳"]);
assert.ok(flattenText(arbitraryBrace).includes("{this}"), "{this} must stay literal text");
console.log(JSON.stringify({ localized, pips, localizedNoCtx, mixedPips }));
"""
    )
    assert "Mana bezahlen" in str(data["localized"])
    assert len(list(data["pips"])) == 1  # type: ignore[arg-type]


def test_all_prompt_classes_localize_to_german_without_html_leaks() -> None:
    data = _run_node(
        r"""
const assert = require("assert");
const cases = [
  {
    name: "mulligan",
    pending: { decision_class: "mulligan", prompt: "Mulligan (7 cards)?", seat: 0 },
    mustContain: "Starthand behalten",
    forbidEn: /mulligan\s*\(|keep hand\?/i,
  },
  {
    name: "priority_own",
    pending: {
      decision_class: "priority",
      prompt: "Choose priority action",
      seat: 0,
      actor_id: "p0",
      pilot_state: { active_player_id: "p0", stack: [] },
    },
    mustContain: "Du bist am Zug",
    forbidEn: /choose priority action/i,
  },
  {
    name: "priority_opponent",
    pending: {
      decision_class: "priority",
      prompt: "Choose priority action",
      seat: 0,
      actor_id: "p0",
      pilot_state: { active_player_id: "p1", stack: [{ name: "Lightning Bolt" }] },
    },
    mustContain: "Priorität auf dem Stapel",
    forbidEn: /choose priority action/i,
  },
  {
    name: "mana_payment",
    pending: {
      decision_class: "mana_payment",
      prompt: "Pay {2}{U}<div style='color:red'>remaining</div>",
      context: { unpaid_mana: "{2}{U}" },
    },
    mustContain: "Mana bezahlen",
    forbidEn: /<div|<font|style=|choose mana/i,
  },
  {
    name: "target",
    pending: { decision_class: "target", prompt: "Select target creature you control" },
    mustContain: "Wähle ein Ziel",
    forbidEn: /^select target/i,
  },
  {
    name: "choose_use",
    pending: { decision_class: "choose_use", prompt: "Do you want to pay {1}?" },
    mustContain: "Möchtest du",
    forbidEn: /^do you want/i,
  },
  {
    name: "declare_attacker",
    pending: { decision_class: "declare_attacker", prompt: "Select attackers for Full Game Seat 1" },
    mustContain: "Angreifer ansagen",
    forbidEn: /^select attackers/i,
  },
  {
    name: "declare_blocker",
    pending: { decision_class: "declare_blocker", prompt: "Select blockers for Grizzly Bears" },
    mustContain: "Blocker ansagen",
    forbidEn: /^select blockers/i,
  },
  {
    name: "mode",
    pending: { decision_class: "mode", prompt: "Choose a mode" },
    mustContain: "Wähle den Modus",
    forbidEn: /^choose a mode/i,
  },
];

const results = [];
for (const c of cases) {
  const out = StudioPrompts.localizePrompt(c.pending, c.pending.decision_class);
  assert.ok(out.includes(c.mustContain), `${c.name}: expected '${c.mustContain}' in '${out}'`);
  assert.ok(!c.forbidEn.test(out), `${c.name}: forbidden pattern in '${out}'`);
  assert.ok(!/[<>]/.test(out), `${c.name}: angle brackets in '${out}'`);
  results.push({ name: c.name, out });
}

assert.strictEqual(StudioPrompts.localizeOptionLabel("Keep hand"), "Starthand behalten");
assert.strictEqual(StudioPrompts.localizeOptionLabel("Keep opening hand"), "Starthand behalten");
assert.strictEqual(StudioPrompts.localizeOptionLabel("Take mulligan"), "Mulligan nehmen");
assert.strictEqual(StudioPrompts.localizeOptionLabel("Yes"), "Ja");
assert.strictEqual(StudioPrompts.localizeOptionLabel("No"), "Nein");

console.log(JSON.stringify({ results }));
"""
    )
    results = list(data["results"])  # type: ignore[arg-type]
    assert len(results) == 9


def test_mana_pool_renders_color_pips_matching_engine_state() -> None:
    data = _run_node(
        """
const assert = require("assert");
const poolEl = StudioPrompts.renderManaPoolPips(h, {
  white: 2,
  blue: 0,
  black: 1,
  red: 0,
  green: 3,
  colorless: 4,
});
assert.ok(poolEl && poolEl.props.class.includes("has-mana"));
const text = flattenText(poolEl);
assert.ok(!/(white|blue|black|red|green|colorless)/i.test(text), "English pool label leaked: " + text);
const byColor = {};
for (const chip of poolEl.children) {
  byColor[chip.props["data-mana-symbol"]] = {
    count: chip.props["data-mana-count"],
    active: chip.props.class.includes("active"),
  };
}
assert.deepStrictEqual(byColor, {
  W: { count: "2", active: true },
  U: { count: "0", active: false },
  B: { count: "1", active: true },
  R: { count: "0", active: false },
  G: { count: "3", active: true },
  C: { count: "4", active: true },
});
console.log(JSON.stringify({ byColor, aria: poolEl.props["aria-label"] }));
"""
    )
    assert data["byColor"] == {
        "W": {"count": "2", "active": True},
        "U": {"count": "0", "active": False},
        "B": {"count": "1", "active": True},
        "R": {"count": "0", "active": False},
        "G": {"count": "3", "active": True},
        "C": {"count": "4", "active": True},
    }
