// node --test tests/js/  (#1662 PLAY v1, the one pass element)
// The pure logic of Space / Enter / Shift+Enter lives in static/vorspulen.js. Whatever the state, the
// only option it may ever hand back is the pass_priority option the engine offered.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";

const require = createRequire(import.meta.url);
const SOURCE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../src/commander_lab/studio/static/vorspulen.js");
const FF = require(SOURCE);

const PASS = { option_id: "pass-1", option_type: "pass_priority", label: "Pass priority" };
const OTHERS = [
  { option_id: "land-1", option_type: "play_land", label: "Play Forest" },
  { option_id: "cast-1", option_type: "cast_spell", label: "Cast Counterspell" },
];
const PLAYERS = [{ seat: 0, player_id: "p0" }, { seat: 1, player_id: "op-1" }];
const OPP_OBJECT = { object_id: "s1", name: "Counterspell", controller_id: "op-1" };
const OWN_OBJECT = { object_id: "s2", name: "Sol Ring", controller_id: "p0" };

function pending(over = {}, stateOver = {}) {
  return {
    decision_id: "d", actor_id: "p0", seat: 0, decision_class: "priority",
    legal_options: [OTHERS[0], PASS, OTHERS[1]],
    pilot_state: { players: PLAYERS, active_player_id: "op-1", turn_number: 3, stack: [], ...stateOver },
    ...over,
  };
}
const ENTER = FF.shortcutAction("Enter", false);
const SHIFT_ENTER = FF.shortcutAction("Enter", true);
const ctx = (action, startTurn = 3) => ({ startTurn, stopOnOpponentStack: action.stopOnOpponentStack });

// The invariant: a verdict either stops or names exactly an offered pass_priority option.
function assertOnlyOfferedPass(verdict, p) {
  if (verdict.action === "stop") { assert.ok(!("optionId" in verdict)); return; }
  assert.equal(verdict.action, "pass");
  const match = (p.legal_options || []).find((o) => o.option_id === verdict.optionId);
  assert.ok(match, "optionId must be one of the offered options");
  assert.equal(match.option_type, "pass_priority", "only pass_priority may be sent");
}

test("shortcutAction maps Space, Enter, Shift+Enter and nothing else", () => {
  assert.deepEqual(FF.shortcutAction(" ", false), { kind: "pass_once" });
  assert.deepEqual(ENTER, { kind: "fast_forward", stopOnOpponentStack: true, label: "Continue" });
  assert.deepEqual(SHIFT_ENTER, { kind: "fast_forward", stopOnOpponentStack: false, label: "To my turn" });
  for (const key of ["Escape", "a", "Tab", "ArrowRight"]) assert.equal(FF.shortcutAction(key, false), null);
  assert.equal(FF.shortcutAction("a", true), null);
});

test("an offered pass is the only thing ever returned, on every priority state", () => {
  for (const action of [ENTER, SHIFT_ENTER]) {
    for (const stack of [[], [OWN_OBJECT], [OPP_OBJECT]]) {
      for (const active of ["p0", "op-1"]) {
        for (const turn of [3, 4]) {
          const p = pending({}, { stack, active_player_id: active, turn_number: turn });
          assertOnlyOfferedPass(FF.verdict(p, ctx(action)), p);
        }
      }
    }
  }
  const ok = FF.verdict(pending(), ctx(ENTER));
  assert.deepEqual(ok, { action: "pass", optionId: "pass-1" });
});

test("no pass option offered: stop, never invent one", () => {
  const p = pending({ legal_options: OTHERS });
  for (const action of [ENTER, SHIFT_ENTER]) assert.equal(FF.verdict(p, ctx(action)).action, "stop");
});

test("Enter stops on an opponent object on the stack; Shift+Enter does not", () => {
  const p = pending({}, { stack: [OPP_OBJECT] });
  const enter = FF.verdict(p, ctx(ENTER));
  assert.equal(enter.action, "stop");
  assert.match(enter.reason, /Counterspell/);
  assert.deepEqual(FF.verdict(p, ctx(SHIFT_ENTER)), { action: "pass", optionId: "pass-1" });
  // my own object does not stop Enter
  assert.equal(FF.verdict(pending({}, { stack: [OWN_OBJECT] }), ctx(ENTER)).action, "pass");
});

test("both runs stop at every non-priority question", () => {
  const classes = ["mulligan", "declare_attacker", "declare_blocker", "target", "mana_payment", "choose_use",
    "mode", "announce_x", "order", "trigger_order", "choice", "amount"];
  for (const action of [ENTER, SHIFT_ENTER]) {
    for (const cls of classes) {
      const v = FF.verdict(pending({ decision_class: cls, legal_options: [OTHERS[0], PASS] }), ctx(action));
      assert.equal(v.action, "stop", `${cls} must stop`);
      assert.ok(!("optionId" in v));
    }
  }
  assert.equal(FF.verdict(null, ctx(ENTER)).action, "stop");
});

test("both runs stop when my own turn begins, and when the turn is unknown", () => {
  const own = pending({}, { active_player_id: "p0", turn_number: 4 });
  for (const action of [ENTER, SHIFT_ENTER]) {
    assert.deepEqual(FF.verdict(own, ctx(action, 3)), { action: "stop", reason: "dein Zug beginnt" });
    // still the turn the run started in: keep passing
    assert.equal(FF.verdict(pending({}, { active_player_id: "p0", turn_number: 3 }), ctx(action, 3)).action, "pass");
    assert.equal(FF.verdict(own, { startTurn: null, stopOnOpponentStack: action.stopOnOpponentStack }).action, "stop");
  }
  // unknown active player: stop
  assert.equal(FF.verdict(pending({}, { active_player_id: null }), ctx(ENTER)).action, "stop");
});

test("mutation probe: a verdict that returns a non-pass option turns the invariant red", () => {
  const raw = fs.readFileSync(SOURCE, "utf8");
  const mutated = raw.replace('option.option_type === "pass_priority"', 'option.option_type === "cast_spell"');
  assert.notEqual(mutated, raw, "the mutation must change the source");
  const Mutated = new Function("module", `${mutated}\nreturn StudioFastForward;`)({ exports: {} });
  const p = pending();
  const v = Mutated.verdict(p, ctx(SHIFT_ENTER));
  assert.equal(v.optionId, "cast-1");
  assert.throws(() => assertOnlyOfferedPass(v, p), /pass_priority/);
  // the real implementation passes the same check
  assertOnlyOfferedPass(FF.verdict(p, ctx(SHIFT_ENTER)), p);
});
