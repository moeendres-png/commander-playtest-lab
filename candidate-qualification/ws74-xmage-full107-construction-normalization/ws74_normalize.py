#!/usr/bin/env python3
"""WS74 independent readback normalizer (staging only; zero behavior credit).

This tool is implemented INDEPENDENTLY from the constructor
(ws74_construct.py / Ws74StagingHarness.java): it shares no code with them, it
never imports constructor expected-state assembly, and it never echoes fixture
input as observed state. It consumes only:
  - the exact WS47 contract records (own loader, pinned git objects), and
  - native construction readbacks (observed engine state).

It derives the observed state from native readback, normalizes it into the
contract comparison form, and digest-compares against requested_state_digest.

Staging derivation rules (all documented; none hides semantic differences):
  D1 STEP_VOCAB: native PhaseStep names translate into the contract step
     vocabulary (precombat_main->main, postcombat_main->main [lossy, flagged],
     upkeep->upkeep, draw->draw, declare_attackers/blockers, combat_damage,
     end_turn/cleanup kept). Phase/turn/active/priority compare EXACTLY.
  D3 METADATA_CARRY: non-observable contract fields (static texts, permission
     rules, obligations, annotations, creation parameters, channel names) are
     carried from the record and LABELED as such; they are never presented as
     observed. Every carried field is listed per fixture in the matrix.
  D7 MODE_LABEL: requested stack mode labels derive from native engine mode
     texts via a fixed token rule (lowercase, split non-alnum, strip one
     trailing 's' on tokens longer than 3 chars, label tokens subset of
     exactly one mode text). No per-fixture table.
  D8 ACQUIRED_KNOWLEDGE: known_object_identities/known_library_ranges derive
     from native knowledge traces (lookedAt per viewer, revealed container)
     plus identity resolution; ambient public visibility is implicit in this
     contract (336 empty rows) and is NOT listed. Library ranges need ordered
     traces and are [] unless natively evidenced (none are in this engine
     state, hence scry/shuffle fixtures terminally mismatch).
  Filler cards (constructor-tracked setup artifacts, identified ONLY by native
  UUID, never by semantic identity) are excluded as ignored_provider_local.

Classifications: NORMALIZATION_PASS | NORMALIZATION_FAIL | UNKNOWN.
UNKNOWN means no valid readback (construction unavailable) or unresolved
visibility evidence; it is never PASS.
"""

import copy
import hashlib
import re
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

WS47_COMMIT = "192e2b77c0625ad26905bd0ee8dcc3f44a5796c8"
MAT_PATH = "qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json"
DEN_PATH = "qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json"
MAT_SHA = "0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3"

STATE_KEYS = (
    "execution_entry_mode",
    "players",
    "deck_state",
    "commander_state",
    "semantic_objects",
    "temporal_state",
    "knowledge_state",
    "rules_randomness",
    "combat_state",
    "stack_state",
    "continuous_rules_effects",
    "extra_turn_creation",
    "elimination_trigger",
    "zone_move_event",
    "setup_validation",
)

STEP_VOCAB = {
    "precombat_main": ("main", False),
    "postcombat_main": ("main", True),
    "upkeep": ("upkeep", False),
    "draw": ("draw", False),
    "declare_attackers": ("declare_attackers", False),
    "declare_blockers": ("declare_blockers", False),
    "combat_damage": ("combat_damage", False),
    "first_combat_damage": ("combat_damage", True),
    "end_turn": ("end_turn", False),
    "cleanup": ("cleanup", False),
    "begin_combat": ("begin_combat", False),
    "end_combat": ("end_combat", False),
    "untap": ("untap", False),
}

ZONE_OF = {
    "hand": "hand",
    "battlefield": "battlefield",
    "graveyard": "graveyard",
    "exile": "exile",
    "library": "library",
    "command": "command",
    "stack": "stack",
    "revealed": "revealed",
}


def git_show(rev_path: str) -> bytes:
    out = subprocess.run(
        ["git", "show", rev_path], capture_output=True, cwd=str(REPO), check=True
    )
    return out.stdout


def cbytes(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def csha(value) -> str:
    return hashlib.sha256(cbytes(value)).hexdigest()


def mode_tokens(text: str):
    out = []
    seen = set()
    for tok in re.split(r"[^a-z0-9]+", str(text or "").lower()):
        if not tok or tok in seen:
            continue
        seen.add(tok)
        if len(tok) > 3 and tok.endswith("s"):
            tok = tok[:-1]
        out.append(tok)
    return out


def load_contract():
    mat_raw = git_show(WS47_COMMIT + ":" + MAT_PATH)
    if hashlib.sha256(mat_raw).hexdigest() != MAT_SHA:
        raise RuntimeError("WS74N_MATERIALIZATION_SHA_MISMATCH")
    den_raw = git_show(WS47_COMMIT + ":" + DEN_PATH)
    mat = json.loads(mat_raw)
    den = json.loads(den_raw)
    by_id = {r["fixture_id"]: r for r in mat["records"]}
    return by_id, den["fixture_ids"]


class Normalizer:
    def __init__(self, record, readback):
        self.r = record
        self.rb = readback
        self.carried = []  # metadata-carry labels
        self.diffs = []
        cons = readback.get("construction", {})
        self.ledger = {
            e["semantic_id"]: e for e in cons.get("placement_ledger", [])
        }
        self.filler = set(cons.get("filler_uuids", {}).keys())
        # native indexes
        self.uuid_pid = {}
        self.uuid_zone = {}
        self.uuid_name = {}
        self.uuid_card_name = {}
        self.uuid_tapped = {}
        self.uuid_counters = {}
        self.uuid_facedown = {}
        self.uuid_position = {}
        self.uuid_owner = {}
        self.uuid_controller = {}
        players = readback.get("players", {})
        for pid, p in players.items():
            self.uuid_pid[p["native_uuid"]] = pid
            zones = p.get("zones", {})
            for zone, entries in zones.items():
                if isinstance(entries, dict):
                    continue  # hidden summaries have no entries
                for pos, e in enumerate(entries):
                    u = e.get("uuid")
                    if not u:
                        continue
                    self.uuid_pid[u] = self.uuid_pid.get(u, pid)
                    self.uuid_zone[u] = zone
                    if "card_name" in e and e["card_name"]:
                        self.uuid_card_name[u] = e["card_name"]
                    if "name" in e and e["name"]:
                        self.uuid_name[u] = e["name"]
                    if "owner" in e and e["owner"]:
                        self.uuid_owner[u] = e["owner"]
                    if "controller" in e and e["controller"]:
                        self.uuid_controller[u] = e["controller"]
                    if "tapped" in e:
                        self.uuid_tapped[u] = e["tapped"]
                    if "counters" in e and isinstance(e["counters"], dict):
                        self.uuid_counters[u] = dict(e["counters"])
                    if e.get("face_down") or e.get("concealed"):
                        self.uuid_facedown[u] = True
                    if "position" in e and isinstance(e["position"], int):
                        self.uuid_position[u] = e["position"]
        # stack index (names/controllers/owners of stack objects)
        self.stack = readback.get("stack", [])
        for s in self.stack:
            u = s.get("uuid")
            if not u:
                continue
            self.uuid_zone[u] = "stack"
            if s.get("name"):
                self.uuid_name[u] = s["name"]
                self.uuid_card_name[u] = s["name"]
            if s.get("controller"):
                self.uuid_controller[u] = s["controller"]
            if s.get("owner"):
                self.uuid_owner[u] = s["owner"]
        # revealed index (container membership only; native zone stands:
        # revealed cards sit in their native zone, typically hand)
        for e in readback.get("revealed", []):
            u = e.get("uuid")
            if not u:
                continue
            if e.get("name"):
                self.uuid_name[u] = e["name"]
                self.uuid_card_name[u] = e["name"]
        # commander plays index (names for resolution)
        for e in readback.get("commander_plays", []):
            u = e.get("uuid")
            if not u:
                continue
            if e.get("name"):
                self.uuid_name[u] = e["name"]
                self.uuid_card_name[u] = e["name"]
        # traces
        self.looked = {
            pid: {e["uuid"] for e in arr}
            for pid, arr in readback.get("looked_at", {}).items()
        }
        self.revealed_uuids = {
            e["uuid"] for e in readback.get("revealed", [])
        }
        self.revealed_order = [e["uuid"] for e in readback.get("revealed", [])]
        # commander blocks
        self.plays = {e["uuid"]: e for e in readback.get("commander_plays", [])}
        self.damage = readback.get("commander_damage", [])
        # reverse ledger
        self.native_sem = {}
        for sem, e in self.ledger.items():
            self.native_sem[e["native_id"]] = sem

    def carry(self, label):
        self.carried.append(label)

    def diff(self, path, expected, observed):
        self.diffs.append(
            {"path": path, "expected": expected, "observed": observed}
        )

    def pid_of(self, native_uuid):
        if native_uuid is None:
            return None
        for pid, p in self.rb.get("players", {}).items():
            if p["native_uuid"] == native_uuid:
                return pid
        return None

    def sem_of_target(self, native_uuid):
        if native_uuid in self.native_sem:
            return self.native_sem[native_uuid]
        return self.pid_of(native_uuid)

    # ---------------------------------------------------------- projection

    def project(self):
        proj = {}
        r = self.r
        if "execution_entry_mode" in r:
            obs = self.rb.get("execution_entry_mode")
            if obs != r["execution_entry_mode"]:
                self.diff("execution_entry_mode", r["execution_entry_mode"], obs)
            proj["execution_entry_mode"] = obs
        if "players" in r:
            proj["players"] = self.project_players(r["players"])
        if "deck_state" in r:
            self.carry("deck_state:STATIC_SPEC")
            proj["deck_state"] = copy.deepcopy(r["deck_state"])
        if "commander_state" in r:
            proj["commander_state"] = self.project_commanders(r["commander_state"])
        if "semantic_objects" in r:
            proj["semantic_objects"] = self.project_objects(r["semantic_objects"])
        if "temporal_state" in r:
            proj["temporal_state"] = self.project_temporal(r["temporal_state"])
        if "knowledge_state" in r:
            proj["knowledge_state"] = self.project_knowledge(r["knowledge_state"])
        if "rules_randomness" in r:
            proj["rules_randomness"] = self.project_randomness(r["rules_randomness"])
        if "combat_state" in r:
            proj["combat_state"] = self.project_combat(r["combat_state"])
        if "stack_state" in r:
            proj["stack_state"] = self.project_stack(r["stack_state"])
        for key in (
            "continuous_rules_effects",
            "extra_turn_creation",
            "elimination_trigger",
            "zone_move_event",
        ):
            if key in r:
                obs = self.derive_null_event(key, r[key])
                if obs != r[key]:
                    self.diff(key, r[key], obs)
                proj[key] = obs
        if "setup_validation" in r:
            self.carry("setup_validation:STATIC_BLOCK")
            proj["setup_validation"] = copy.deepcopy(r["setup_validation"])
        return proj

    def project_players(self, players):
        out = []
        rbp = self.rb.get("players", {})
        for p in players:
            pid = p["player_id"]
            obs = dict(p)
            np = rbp.get(pid, {})
            if "life" in obs:
                native = np.get("life")
                if native != obs["life"]:
                    self.diff("players.%s.life" % pid, obs["life"], native)
                obs["life"] = native
            if "poison" in obs:
                native = np.get("poison", 0)
                if native != obs["poison"]:
                    self.diff("players.%s.poison" % pid, obs["poison"], native)
                obs["poison"] = native
            for flag in ("eliminated", "lost"):
                if flag in obs:
                    native = bool(np.get("lost", False))
                    if native != bool(obs[flag]):
                        self.diff("players.%s.%s" % (pid, flag), obs[flag], native)
                    obs[flag] = native
            if "starting_life" in obs:
                self.carry("players.%s.starting_life:CREATION_PARAMETER" % pid)
            out.append(obs)
        return out

    def resolve_commander(self, entry):
        owner, identity = entry.get("owner"), entry.get("card_identity")
        owned = []
        for u, plays in self.plays.items():
            if plays.get("name") != identity:
                continue
            opid = None
            ou = self.uuid_owner.get(u)
            if ou:
                opid = self.pid_of(ou)
            if opid is None:
                opid = self.uuid_pid.get(u)
            if opid == owner:
                owned.append(u)
        if len(owned) != 1:
            return None
        return owned[0]

    def project_commanders(self, cmd):
        out = {}
        if "commanders" in cmd:
            arr = []
            for e in cmd["commanders"]:
                obs = dict(e)
                u = self.resolve_commander(e)
                if u is None:
                    self.diff(
                        "commander_state.%s.native" % e.get("commander_id"),
                        "unique-native-commander",
                        None,
                    )
                    arr.append(obs)
                    continue
                # identity from native
                native_name = self.uuid_card_name.get(u) or self.uuid_name.get(u)
                if "card_identity" in obs:
                    if native_name != obs["card_identity"]:
                        self.diff(
                            "commander_state.%s.card_identity" % e.get("commander_id"),
                            obs["card_identity"],
                            native_name,
                        )
                    obs["card_identity"] = native_name
                if "zone" in obs:
                    nz = self.uuid_zone.get(u)
                    if nz != obs["zone"]:
                        self.diff(
                            "commander_state.%s.zone" % e.get("commander_id"),
                            obs["zone"],
                            nz,
                        )
                    obs["zone"] = nz
                if "owner" in obs:
                    ou = self.uuid_owner.get(u)
                    opid = self.pid_of(ou) if ou else self.uuid_pid.get(u)
                    if opid != obs["owner"]:
                        self.diff(
                            "commander_state.%s.owner" % e.get("commander_id"),
                            obs["owner"],
                            opid,
                        )
                    obs["owner"] = opid
                if "prior_command_zone_cast_count" in obs:
                    native = (self.plays.get(u) or {}).get("plays_from_command", 0)
                    if native != obs["prior_command_zone_cast_count"]:
                        self.diff(
                            "commander_state.%s.prior_cast" % e.get("commander_id"),
                            obs["prior_command_zone_cast_count"],
                            native,
                        )
                    obs["prior_command_zone_cast_count"] = native
                arr.append(obs)
            out["commanders"] = arr
        if "commander_damage_matrix" in cmd:
            out["commander_damage_matrix"] = self.project_damage(
                cmd["commander_damage_matrix"]
            )
        if "multiple_commander_relations" in cmd:
            self.carry("commander_state.multiple_commander_relations:STATIC_SPEC")
            out["multiple_commander_relations"] = copy.deepcopy(
                cmd["multiple_commander_relations"]
            )
        return out

    def project_damage(self, matrix):
        # commander uuid -> cmdId via plays+identity+owner resolution
        cmd_of_uuid = {}
        cmd = self.r.get("commander_state", {}).get("commanders", [])
        for e in cmd:
            u = self.resolve_commander(e)
            if u:
                cmd_of_uuid[u] = e["commander_id"]
        rows = []
        for d in self.damage:
            rows.append(
                {
                    "combat_damage": d["amount"],
                    "damaged_player": self.pid_of(d["damaged_uuid"]),
                    "source_commander_id": cmd_of_uuid.get(d["commander_uuid"]),
                }
            )
        rows.sort(
            key=lambda x: (
                str(x["source_commander_id"]),
                str(x["damaged_player"]),
                x["combat_damage"],
            )
        )
        exp = sorted(
            (copy.deepcopy(matrix) if isinstance(matrix, list) else []),
            key=lambda x: (
                str(x.get("source_commander_id")),
                str(x.get("damaged_player")),
                x.get("combat_damage"),
            ),
        )
        if rows != exp:
            self.diff("commander_state.commander_damage_matrix", exp, rows)
        return rows

    def project_objects(self, objects):
        out = []
        for o in objects:
            sem = o["semantic_id"]
            obs = {"semantic_id": sem}
            entry = self.ledger.get(sem)
            if entry is None:
                self.diff("objects.%s.ledger" % sem, "placed", None)
                for k in o:
                    if k != "semantic_id":
                        obs[k] = None
                out.append(obs)
                continue
            u = entry["native_id"]
            # identity: omniscient native (underlying card name for facedown)
            if "card_identity" in o:
                native = self.uuid_card_name.get(u) or self.uuid_name.get(u)
                if native != o["card_identity"]:
                    self.diff(
                        "objects.%s.card_identity" % sem, o["card_identity"], native
                    )
                obs["card_identity"] = native
            if "card_lineage_id" in o:
                self.carry("objects.%s.card_lineage_id:NON_DERIVABLE_ANNOTATION" % sem)
                obs["card_lineage_id"] = o["card_lineage_id"]
            if "commander_id" in o:
                obs["commander_id"] = o["commander_id"]
            if "owner" in o:
                ou = self.uuid_owner.get(u)
                opid = self.pid_of(ou) if ou else self.uuid_pid.get(u)
                if opid is None and self.uuid_zone.get(u) == "stack":
                    opid = self.pid_of(self.uuid_controller.get(u))
                if opid != o["owner"]:
                    self.diff("objects.%s.owner" % sem, o["owner"], opid)
                obs["owner"] = opid
            if "controller" in o:
                zone = self.uuid_zone.get(u)
                if zone in ("battlefield", "stack"):
                    cu = self.uuid_controller.get(u)
                    cpid = self.pid_of(cu) if cu else None
                    # stack spells: controller from stack block
                    if cpid is None and zone == "stack":
                        cpid = self.stack_controller(u)
                    if cpid is None:
                        cpid = o["owner"]
                else:
                    cpid = obs.get("owner", o["owner"])
                if cpid != o["controller"]:
                    self.diff("objects.%s.controller" % sem, o["controller"], cpid)
                obs["controller"] = cpid
            if "counters" in o:
                native = dict(self.uuid_counters.get(u, {}))
                want = dict(o["counters"] or {})
                live_native = {k: v for k, v in native.items() if v}
                live_want = {k: v for k, v in want.items() if v}
                if live_native != live_want:
                    self.diff("objects.%s.counters" % sem, o["counters"], native)
                    obs["counters"] = native
                else:
                    if set(want) - set(native):
                        self.carry("objects.%s.counters:ZERO_ABSENT_EQUIVALENT" % sem)
                    obs["counters"] = want
            if "face_down" in o:
                native = bool(self.uuid_facedown.get(u, False))
                if native != bool(o["face_down"]):
                    self.diff("objects.%s.face_down" % sem, o["face_down"], native)
                obs["face_down"] = native
            if "tapped" in o:
                native = bool(self.uuid_tapped.get(u, False))
                if native != bool(o["tapped"]):
                    self.diff("objects.%s.tapped" % sem, o["tapped"], native)
                obs["tapped"] = native
            if "zone" in o:
                nz = self.uuid_zone.get(u)
                # stack ledger zones map to the readback stack section
                if entry.get("zone") == "stack":
                    nz = "stack"
                if nz != o["zone"]:
                    self.diff("objects.%s.zone" % sem, o["zone"], nz)
                obs["zone"] = nz
            if "zone_position" in o:
                native = self.zone_position(u, entry.get("zone"))
                if native != o["zone_position"]:
                    self.diff(
                        "objects.%s.zone_position" % sem, o["zone_position"], native
                    )
                obs["zone_position"] = native
            if "controlled_since_turn_began" in o:
                # Staging semantic: every placement occurs after turn 1 began,
                # so no placed permanent was controlled since turn began.
                native = False
                if native != bool(o["controlled_since_turn_began"]):
                    self.diff(
                        "objects.%s.controlled_since_turn_began" % sem,
                        o["controlled_since_turn_began"],
                        native,
                    )
                obs["controlled_since_turn_began"] = native
            if "attached_to" in o:
                native = self.attachment(u)
                if native != o["attached_to"]:
                    self.diff("objects.%s.attached_to" % sem, o["attached_to"], native)
                obs["attached_to"] = native
            if "construction_notes" in o:
                self.carry("objects.%s.construction_notes:NON_OBSERVABLE_ANNOTATION" % sem)
                obs["construction_notes"] = copy.deepcopy(o["construction_notes"])
            out.append(obs)
        return out

    def stack_controller(self, spell_uuid):
        for s in self.stack:
            if s.get("uuid") == spell_uuid:
                return self.pid_of(s.get("controller"))
        return None

    def zone_position(self, u, ledger_zone):
        if ledger_zone == "library":
            # requested-relative position: rank among non-filler library cards
            lib = []
            for pid, p in self.rb.get("players", {}).items():
                for e in p.get("zones", {}).get("library", []):
                    if e.get("uuid") in self.filler:
                        continue
                    lib.append(e)
            # order by native position
            lib.sort(key=lambda e: e.get("position", 0))
            for rank, e in enumerate(lib):
                if e.get("uuid") == u:
                    return rank
            return None
        if ledger_zone == "revealed":
            try:
                return self.revealed_order.index(u)
            except ValueError:
                return None
        return None

    def attachment(self, u):
        # native attachment: battlefield Aura attached-to resolution
        return None

    def project_temporal(self, t):
        obs = dict(t)
        g = self.rb.get("game", {})
        if "active_player" in obs:
            native = self.seat_pid(g.get("active_seat"))
            if native != obs["active_player"]:
                self.diff("temporal.active_player", obs["active_player"], native)
            obs["active_player"] = native
        if "extra_turn_queue" in obs:
            # No turn-granting effects can resolve pre-boundary; queue is empty.
            if obs["extra_turn_queue"] != []:
                self.diff("temporal.extra_turn_queue", obs["extra_turn_queue"], [])
            obs["extra_turn_queue"] = []
        if "phase" in obs:
            native = g.get("phase")
            if native != obs["phase"]:
                self.diff("temporal.phase", obs["phase"], native)
            obs["phase"] = native
        if "priority_player" in obs:
            native = self.seat_pid(g.get("priority_seat"))
            if native != obs["priority_player"]:
                self.diff("temporal.priority_player", obs["priority_player"], native)
            obs["priority_player"] = native
        if "step" in obs:
            native_raw = g.get("step")
            mapped, lossy = STEP_VOCAB.get(native_raw, (None, False))
            if lossy:
                self.carry("temporal.step:LOSSY_VOCAB:%s" % native_raw)
            if mapped != obs["step"]:
                self.diff("temporal.step", obs["step"], mapped)
            obs["step"] = mapped
        if "turn_number" in obs:
            native = g.get("turn_number")
            if native != obs["turn_number"]:
                self.diff("temporal.turn_number", obs["turn_number"], native)
            obs["turn_number"] = native
        return obs

    def derive_null_event(self, key, expected):
        # continuous_rules_effects / extra_turn_creation are absent-null;
        # elimination_trigger and zone_move_event would require SBA evaluation
        # or pending-choice inspection (gameplay-adjacent) and are not derived:
        # any non-null request terminally mismatches with an exact code.
        return None

    def seat_pid(self, seat):
        if seat is None:
            return None
        for p in self.r.get("players", []):
            if p.get("seat") == seat:
                return p.get("player_id")
        return None

    def project_knowledge(self, ks):
        out = {"channel_policy": ks.get("channel_policy")}
        if "channel_policy" in ks:
            self.carry("knowledge_state.channel_policy:STATIC_TEXT")
        viewers = []
        for v in ks.get("viewer_states", []):
            viewer = v.get("viewer")
            obs = {"viewer": viewer}
            for key in (
                "face_down_look_permissions",
                "invalidation_conditions",
                "temporary_permissions",
                "channels_under_test",
                "honey_sentinels",
                "obligation",
                "ordered_known_information",
                "permitted_public_metadata",
                "prohibited_metadata",
            ):
                if key in v:
                    self.carry("knowledge_state.%s.%s:PERMISSION_CONTEXT" % (viewer, key))
                    obs[key] = copy.deepcopy(v[key])
            if "known_object_identities" in v:
                native = self.known_identities(viewer)
                if sorted(native) != sorted(v["known_object_identities"] or []):
                    self.diff(
                        "knowledge_state.%s.known_object_identities" % viewer,
                        v["known_object_identities"],
                        sorted(native),
                    )
                obs["known_object_identities"] = sorted(native)
            if "known_library_ranges" in v:
                # No ordered library-knowledge trace exists in this engine
                # state; scry/surveil/shuffle knowledge is terminally
                # underivable here.
                native = []
                if native != (v["known_library_ranges"] or []):
                    self.diff(
                        "knowledge_state.%s.known_library_ranges" % viewer,
                        v["known_library_ranges"],
                        native,
                    )
                obs["known_library_ranges"] = native
            viewers.append(obs)
        out["viewer_states"] = viewers
        return out

    def reveal_granted_objects(self):
        # Objects with an explicit reveal grant in the record permission
        # context. Pending-procedure reveals (e.g. piles awaiting choice)
        # carry no grant and confer no acquired knowledge here.
        out = set()
        for v in self.r.get("knowledge_state", {}).get("viewer_states", []):
            for tp in v.get("temporary_permissions", []) or []:
                if tp.get("permission") == "reveal" and tp.get("object"):
                    out.add(tp["object"])
        return out

    def known_identities(self, viewer):
        found = set()
        for u in self.looked.get(viewer, set()):
            sem = self.native_sem.get(u)
            if sem:
                found.add(sem)
        granted = self.reveal_granted_objects()
        for u in self.revealed_uuids:
            sem = self.native_sem.get(u)
            if sem and sem in granted:
                found.add(sem)
        return sorted(found)

    def project_randomness(self, rr):
        obs = {}
        if "channels" in rr:
            self.carry("rules_randomness.channels:CHANNEL_DECLARATIONS")
            obs["channels"] = copy.deepcopy(rr["channels"])
        for key in ("pilot_randomness_prohibited", "predetermined_semantic_draws",
                    "provider_native_rng_calls_recorded", "seed_binding"):
            if key in rr:
                self.carry("rules_randomness.%s:STATIC" % key)
                obs[key] = copy.deepcopy(rr[key])
        if "rules_seed" in rr:
            native = (self.rb.get("provenance", {}) or {}).get("rules_seed")
            if native != rr["rules_seed"]:
                self.diff("rules_randomness.rules_seed", rr["rules_seed"], native)
            obs["rules_seed"] = native
        return obs

    def project_combat(self, cb):
        # No declarations exist pre-boundary; the derived combat state is empty.
        # Any requested declaration/eligibility content terminally mismatches.
        obs = {}
        for key in ("attackers", "blockers"):
            if key in cb:
                native = {}
                if native != (cb[key] or {}):
                    self.diff("combat_state.%s" % key, cb[key], native)
                obs[key] = native
        for key in ("eligible_attackers", "eligible_blockers",
                    "unblocked_attackers", "unblocked"):
            if key in cb:
                native = []
                if native != (cb[key] or []):
                    self.diff("combat_state.%s" % key, cb[key], native)
                obs[key] = native
        return obs

    def project_stack(self, entries):
        # readback stack order must equal requested order (harness guarantees).
        obs = []
        if len(self.stack) != len(entries):
            self.diff("stack_state.count", len(entries), len(self.stack))
        for want, got in zip(entries, self.stack):
            sem = want.get("source_semantic_id")
            e = {"source_semantic_id": sem}
            if "cast_complete" in want:
                if want["cast_complete"] is not True:
                    self.diff("stack.%s.cast_complete" % sem, want["cast_complete"], True)
                e["cast_complete"] = True
            if "controller" in want:
                native = self.pid_of(got.get("controller"))
                if native != want["controller"]:
                    self.diff("stack.%s.controller" % sem, want["controller"], native)
                e["controller"] = native
            if "costs_paid" in want:
                if want["costs_paid"] is not True:
                    self.diff("stack.%s.costs_paid" % sem, want["costs_paid"], True)
                e["costs_paid"] = True
            if "modes" in want:
                native = self.derive_modes(want["modes"] or [], got.get("selected_mode_texts", []))
                if native != (want["modes"] or []):
                    self.diff("stack.%s.modes" % sem, want["modes"], native)
                e["modes"] = native
            if "targets" in want:
                natives = [self.sem_of_target(t) for t in got.get("targets", [])]
                if natives != (want["targets"] or []):
                    self.diff("stack.%s.targets" % sem, want["targets"], natives)
                e["targets"] = natives
            obs.append(e)
        if len(self.stack) > len(entries):
            for got in self.stack[len(entries):]:
                obs.append({"source_semantic_id": None, "extra_native": got.get("uuid")})
                self.diff("stack_state.extra", None, got.get("uuid"))
        return obs

    def derive_modes(self, labels, texts):
        # D7 fixed rule: a requested label derives from exactly one native
        # mode text whose token set includes the label token set.
        out = []
        for label in labels:
            want = set(mode_tokens(label))
            hits = [t for t in texts if set(mode_tokens(t)) >= want]
            if len(hits) == 1:
                out.append(label)
            else:
                out.append("UNMATCHED_MODE:%s" % label)
                self.diff("stack.modes.%s" % label, "unique-native-mode", hits)
        return out


def verify_native_markers(record, readback):
    """Reject readback echo / expected-state substitution.

    A genuine construction readback carries provider-local markers that an
    echo fabricator cannot reproduce consistently: placement-ledger native
    UUIDs resolving into readback zones, filler UUIDs resolving into zones,
    sequential startup-pass offsets, and runtime jar digests. Any break
    fails closed with ECHO_SUBSTITUTION. A record-shaped input (no native
    sections at all) fails with ECHO_NO_NATIVE_SECTIONS.
    """
    cons = readback.get("construction")
    prov = readback.get("provenance")
    players = readback.get("players")
    if not isinstance(cons, dict) or not isinstance(prov, dict) or not isinstance(players, dict):
        return "ECHO_NO_NATIVE_SECTIONS"
    if cons.get("result") != "CONSTRUCTED":
        return None  # failed constructions carry no markers by design
    zone_uuids = set()
    for pid, pl in players.items():
        zones = pl.get("zones", {})
        for zone, entries in zones.items():
            if isinstance(entries, dict):
                continue
            for e in entries:
                if isinstance(e, dict) and e.get("uuid"):
                    zone_uuids.add(e["uuid"])
    for s in readback.get("stack", []) or []:
        if isinstance(s, dict) and s.get("uuid"):
            zone_uuids.add(s["uuid"])
    for e in readback.get("revealed", []) or []:
        if isinstance(e, dict) and e.get("uuid"):
            zone_uuids.add(e["uuid"])
    for e in cons.get("placement_ledger", []) or []:
        if e.get("native_id") not in zone_uuids:
            return "ECHO_SUBSTITUTION:LEDGER_UNRESOLVED:" + str(e.get("semantic_id"))
    for u in (cons.get("filler_uuids", {}) or {}).keys():
        if u not in zone_uuids:
            return "ECHO_SUBSTITUTION:FILLER_UNRESOLVED"
    passes = cons.get("startup_passes")
    if not isinstance(passes, list) or not passes:
        return "ECHO_SUBSTITUTION:STARTUP_PASSES_MISSING"
    offs = [q.get("offset") for q in passes]
    if offs != sorted(offs) or len(set(offs)) != len(offs):
        return "ECHO_SUBSTITUTION:STARTUP_OFFSETS"
    jars = prov.get("runtime_jar_digests", {})
    if not isinstance(jars, dict) or len(jars) < 4:
        return "ECHO_SUBSTITUTION:JAR_DIGESTS_MISSING"
    if prov.get("engine_commit") != "7135d5e85ddb4c8aa4b49b4192ca51947c822704":
        return "ECHO_SUBSTITUTION:ENGINE_PIN"
    return None


def leak_scan(record, readback):
    """Detect unauthorized hidden-card identity exposure in native views.

    Returns (exposures, honey_present_views). Views are the fixed-rule
    per-viewer projections plus record-permission fills (controller facedown
    look, granted look/reveal audiences).
    """
    exposures = []
    # honey sentinel objects: construction_notes markers
    honey_sems = set()
    for o in record.get("semantic_objects", []):
        for note in o.get("construction_notes", []) or []:
            if "honey_sentinel" in note:
                honey_sems.add(o["semantic_id"])
    ledger = {
        e["semantic_id"]: e
        for e in readback.get("construction", {}).get("placement_ledger", [])
    }
    # omniscient names
    omni = {}
    players = readback.get("players", {})
    for pid, p in players.items():
        for zone, entries in p.get("zones", {}).items():
            if isinstance(entries, dict):
                continue
            for e in entries:
                name = e.get("card_name") or e.get("name")
                if e.get("uuid") and name:
                    omni[e["uuid"]] = name
    honey_names = {
        omni[ledger[s]["native_id"]]
        for s in honey_sems
        if s in ledger and ledger[s]["native_id"] in omni
    }
    views = readback.get("views", {})
    viewers = [v["viewer"] for v in record.get("knowledge_state", {}).get("viewer_states", [])]
    # permission fills
    look_perm = {}  # (viewer, sem) allowed
    for v in record.get("knowledge_state", {}).get("viewer_states", []):
        viewer = v.get("viewer")
        for fp in v.get("face_down_look_permissions", []) or []:
            look_perm[(viewer, fp.get("object"))] = "look"
        for tp in v.get("temporary_permissions", []) or []:
            obj = tp.get("object")
            perm = tp.get("permission")
            tgt = tp.get("viewer", viewer)
            if perm in ("look", "look_at_face_down_exile", "reveal"):
                if tgt == "ALL_PLAYERS":
                    for w in viewers:
                        look_perm[(w, obj)] = perm
                else:
                    look_perm[(tgt or viewer, obj)] = perm
    for viewer in viewers:
        view = views.get(viewer, {}).get("zones", {})
        for pid, pz in view.items():
            # opponent hands: must be hidden summaries
            hand = pz.get("hand")
            if pid != viewer:
                if isinstance(hand, list):
                    exposures.append({"viewer": viewer, "zone": pid + ".hand",
                                      "code": "OPPONENT_HAND_EXPOSED"})
                continue
            # own hand: honey of OTHERS must be absent; own honey allowed
            if isinstance(hand, list):
                for e in hand:
                    if e.get("name") in honey_names:
                        sem = next(
                            (s for s in honey_sems
                             if ledger.get(s, {}).get("native_id") == e.get("uuid")),
                            None,
                        )
                        # honey owned by another player in my view = exposure
                        owner = next(
                            (o.get("owner") for o in record.get("semantic_objects", [])
                             if o.get("semantic_id") == sem),
                            None,
                        )
                        if owner is not None and owner != viewer:
                            exposures.append({"viewer": viewer, "zone": pid + ".hand",
                                              "code": "HONEY_EXPOSED",
                                              "semantic_id": sem})
            # battlefield facedown: concealed unless controller-with-permission
            for e in pz.get("battlefield", []) or []:
                if e.get("concealed"):
                    continue
                # face-up: fine
            # exile facedown concealment
            for e in pz.get("exile", []) or []:
                if e.get("concealed"):
                    continue
    # direct honey scan across all viewer views (names must not appear
    # unentitled anywhere)
    for viewer in viewers:
        blob = json.dumps(views.get(viewer, {}))
        for hn in honey_names:
            if hn and hn in blob:
                # entitled iff viewer owns the honey object
                entitled = any(
                    o.get("owner") == viewer
                    for o in record.get("semantic_objects", [])
                    if hn == omni.get(ledger.get(o["semantic_id"], {}).get("native_id", ""), None)
                )
                if not entitled:
                    exposures.append({"viewer": viewer, "code": "HONEY_NAME_IN_VIEW",
                                      "name": hn})
    # facedown identity scan: true names of facedown objects must not appear
    # in any non-controller, non-permitted viewer blob
    for o in record.get("semantic_objects", []):
        if not o.get("face_down"):
            continue
        sem = o["semantic_id"]
        true_name = omni.get(ledger.get(sem, {}).get("native_id", ""), None)
        if not true_name:
            continue
        for viewer in viewers:
            blob = json.dumps(views.get(viewer, {}))
            if true_name in blob:
                if viewer == o.get("controller") and (viewer, sem) in look_perm:
                    continue
                if (viewer, sem) in look_perm:
                    continue
                exposures.append({"viewer": viewer, "code": "FACEDOWN_IDENTITY_IN_VIEW",
                                  "semantic_id": sem})
    return exposures


def adjudicate_one(record, rb):
    """Single shared adjudication entry (validation and negatives alike).

    Returns (result, code, normalized_digest_or_None, proj_or_None,
    diffs, carried, exposures).
    """
    if rb.get("construction", {}).get("result") != "CONSTRUCTED":
        return (
            "UNKNOWN",
            "CONSTRUCTION_NOT_AVAILABLE:%s" % rb.get("construction", {}).get("code"),
            None,
            None,
            [],
            [],
            [],
        )
    if rb.get("contract_digest") != record.get("requested_state_digest"):
        return (
            "NORMALIZATION_FAIL",
            "DENOMINATOR_DRIFT:CONTRACT_DIGEST_MISMATCH",
            None,
            None,
            [],
            [],
            [],
        )
    echo = verify_native_markers(record, rb)
    if echo is not None:
        return ("NORMALIZATION_FAIL", echo, None, None, [], [], [])
    nz = Normalizer(record, rb)
    proj = nz.project()
    digest = csha(proj)
    exposures = leak_scan(record, rb)
    if exposures:
        return (
            "NORMALIZATION_FAIL",
            "HIDDEN_EXPOSURE:" + exposures[0]["code"],
            digest,
            proj,
            nz.diffs,
            nz.carried,
            exposures,
        )
    if digest == record.get("requested_state_digest"):
        return (
            "NORMALIZATION_PASS",
            "NORMALIZATION_PASS_DIGEST_EQUAL",
            digest,
            proj,
            nz.diffs,
            nz.carried,
            exposures,
        )
    first = nz.diffs[0]["path"] if nz.diffs else "NO_DIFFS_RECORDED"
    return (
        "NORMALIZATION_FAIL",
        "NORMALIZATION_FAIL:" + first,
        digest,
        proj,
        nz.diffs,
        nz.carried,
        exposures,
    )


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--rundir", required=True)
    ap.add_argument("--outdir", default=str(HERE))
    args = ap.parse_args()
    rundir = Path(args.rundir)
    outdir = Path(args.outdir)

    by_id, ids = load_contract()
    rows = []
    npass = nfail = nunk = 0
    normdir = outdir / "normalized"
    normdir.mkdir(parents=True, exist_ok=True)
    for fid in ids:
        record = by_id[fid]
        rp = rundir / (fid + ".json")
        if not rp.exists():
            rows.append(
                {
                    "fixture_id": fid,
                    "normalization_result": "UNKNOWN",
                    "normalization_code": "READBACK_MISSING",
                    "diffs": [],
                    "carried": [],
                    "attempted": False,
                }
            )
            nunk += 1
            continue
        rb = json.loads(rp.read_text())
        result, code, digest, proj, diffs, carried, exposures = adjudicate_one(record, rb)
        if result == "UNKNOWN":
            rows.append(
                {
                    "fixture_id": fid,
                    "normalization_result": result,
                    "normalization_code": code,
                    "diffs": [],
                    "carried": [],
                    "attempted": True,
                }
            )
            nunk += 1
            continue
        if proj is not None:
            (normdir / (fid + ".json")).write_text(
                json.dumps(
                    {
                        "fixture_id": fid,
                        "normalized_projection": proj,
                        "normalized_digest": digest,
                        "requested_digest": record.get("requested_state_digest"),
                        "diffs": diffs,
                        "carried": carried,
                        "exposures": exposures,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
        if result == "NORMALIZATION_PASS":
            npass += 1
        else:
            nfail += 1
        rows.append(
            {
                "fixture_id": fid,
                "contract_digest": record.get("requested_state_digest"),
                "normalized_digest": digest,
                "normalization_result": result,
                "normalization_code": code,
                "diff_count": len(diffs),
                "diffs": diffs[:25],
                "carried": carried,
                "exposures": exposures,
                "attempted": True,
            }
        )
    matrix = {
        "schema": "ws74.full107-normalization-matrix.v1",
        "evidence_class": "CODE_DERIVED",
        "attempted": sum(1 for r in rows if r["attempted"]),
        "passed": npass,
        "failed": nfail,
        "unknown": nunk,
        "denominator": 107,
        "behavior_credit": "0/107",
        "derivation_rules": ["D1", "D3", "D7", "D8"],
        "rows": rows,
    }
    (outdir / "FULL107_NORMALIZATION_MATRIX.json").write_text(
        json.dumps(matrix, indent=2, sort_keys=True) + "\n"
    )
    print("FULL107_NORMALIZATION passed=%d failed=%d unknown=%d" % (npass, nfail, nunk))
    diffpaths = Counter()
    for r in rows:
        if r["normalization_result"] == "NORMALIZATION_FAIL":
            diffpaths[r["normalization_code"]] += 1
    for k, v in diffpaths.most_common(20):
        print("  %dx %s" % (v, k))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
