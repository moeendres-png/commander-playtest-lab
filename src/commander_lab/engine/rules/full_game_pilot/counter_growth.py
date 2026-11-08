"""Conservative strategic estimate for repeated optional self-counter growth."""

from __future__ import annotations

import html
import re

from commander_lab.agents.card_knowledge import card_facts

from ..full_game_pilot_views import creature_toughness_left, permanent_owner, players

_SHAPE = re.compile(
    r"whenever one or more \+1/\+1 counters are put on another creature you control, "
    r"you may put a \+1/\+1 counter on this creature\."
)
_STAT_COUNTER_REPLACEMENT = (
    "if one or more +1/+1 counters would be put on a creature you control, "
    "that many plus one +1/+1 counters are put on it instead."
)


def _known_counter_abilities(name: str, abilities: object, *, growth: bool) -> bool:
    if not isinstance(abilities, list) or any(not isinstance(a, str) for a in abilities):
        return False
    for ability in abilities:
        text = ability.casefold()
        if "counter" not in text or text == _STAT_COUNTER_REPLACEMENT:
            continue
        rule = text.replace(name.casefold(), "this creature").replace("{this}", "this creature")
        if not growth or not _SHAPE.fullmatch(rule):
            return False
    return True


def self_counter_stack_depth(state: dict[str, object]) -> int | None:
    """Count an observed stack containing only the recognized growth trigger text."""
    stack = state.get("stack")
    if not isinstance(stack, list):
        return None
    for item in stack:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            return None
        text = item["name"].casefold()
        if not text.startswith("stack ability (") or not text.endswith(")"):
            return None
        rule = text[len("stack ability (") : -1].replace("{this}", "this creature")
        if not _SHAPE.fullmatch(rule):
            return None
    return len(stack)


def self_counter_progress(state: dict[str, object]) -> tuple[int, int] | None:
    """Observed queue size and a capped public-body development score."""
    depth = self_counter_stack_depth(state)
    public_players = players(state)
    if depth is None or not public_players:
        return None
    comparison = 40
    for player in public_players:
        life = player.get("life")
        if type(life) is not int:
            return None
        comparison = max(comparison, life)
    development = 0
    for player in public_players:
        board = player.get("battlefield")
        if not isinstance(board, list):
            return None
        for entry in board:
            if not isinstance(entry, dict) or entry.get("face_down") is not False:
                return None
            name = entry.get("name")
            facts = card_facts(name) if isinstance(name, str) else None
            if facts is None:
                return None
            text = facts.oracle_text.casefold()
            if not _known_counter_abilities(
                str(name), entry.get("abilities"), growth=_SHAPE.search(text) is not None
            ):
                return None
            if _SHAPE.search(text):
                p, t, d = (entry.get(key) for key in ("power", "toughness", "damage"))
                if type(p) is not int or type(t) is not int or type(d) is not int:
                    return None
                development += max(0, min(p, creature_toughness_left(entry), 2 * comparison))
            elif "counter" in text and text != _STAT_COUNTER_REPLACEMENT:
                return None
    return depth, development


def saturated_self_counter(state: dict[str, object], source: object, prompt: str) -> bool:
    """Estimate low marginal value; unknown public information keeps the old ranking."""
    if not isinstance(source, dict) or source.get("ability_type") != "triggered_nonmana":
        return False
    object_id = source.get("source_object_id")
    original = source.get("ability_original_id")
    name = source.get("source_name")
    if not isinstance(object_id, str) or not object_id.strip():
        return False
    if not isinstance(original, str) or not original.strip():
        return False
    if not isinstance(name, str) or not name.strip():
        return False
    normalized = html.unescape(re.sub(r"<[^>]*>", "", prompt)).strip().casefold()
    expected = (
        "whenever one or more +1/+1 counters are put on another creature you control, "
        f"you may put a +1/+1 counter on {name.casefold()}"
    )
    if not re.fullmatch(re.escape(expected) + r"(?: \[[0-9a-f]+\])?\.", normalized):
        return False
    actor_id = state.get("actor_id")
    owner = permanent_owner(object_id, state)
    if not actor_id or owner is None or owner[0] != actor_id:
        return False
    body = owner[1]
    if str(body.get("name") or "").casefold() != name.casefold():
        return False
    facts = card_facts(name)
    if facts is None or not _SHAPE.search(facts.oracle_text.casefold()):
        return False
    # Other abilities on the source itself may give counters an alternate value.
    text = _SHAPE.sub("", facts.oracle_text.casefold())
    if "counter" in text:
        return False
    power, toughness, damage = (body.get(key) for key in ("power", "toughness", "damage"))
    if type(power) is not int or type(toughness) is not int or type(damage) is not int:
        return False
    if power <= 0 or toughness <= 0 or damage < 0:
        return False
    all_players = players(state)
    raw_players = state.get("players")
    if (
        not isinstance(raw_players, list)
        or len(all_players) < 2
        or len(all_players) != len(raw_players)
    ):
        return False
    peers = 0
    peer_strengths: list[int] = []
    bound = 40
    for player in all_players:
        player_id = player.get("player_id")
        board = player.get("battlefield")
        if not player_id or not isinstance(board, list):
            return False
        if player_id != actor_id:
            life = player.get("life")
            if type(life) is not int:
                return False
            bound = max(bound, life)
        for entry in board:
            if not isinstance(entry, dict):
                return False
            if entry.get("face_down") is not False:
                return False
            entry_name = entry.get("name")
            if not isinstance(entry_name, str) or not entry_name:
                return False
            entry_id = entry.get("object_id")
            if not isinstance(entry_id, str) or not entry_id:
                return False
            entry_facts = card_facts(entry_name)
            if entry_facts is None:
                return False
            if not _known_counter_abilities(
                entry_name, entry.get("abilities"), growth=entry_name.casefold() == name.casefold()
            ):
                return False
            if (
                player_id == actor_id
                and entry_name.casefold() == name.casefold()
                and entry_id != object_id
            ):
                peers += 1
            if (
                entry_name.casefold() != name.casefold()
                and "counter" in entry_facts.oracle_text.casefold()
                and entry_facts.oracle_text.casefold() != _STAT_COUNTER_REPLACEMENT
            ):
                return False
            if entry_facts.is_creature or "power" in entry or "toughness" in entry:
                p, t, d = (entry.get(key) for key in ("power", "toughness", "damage"))
                if type(p) is not int or type(t) is not int or type(d) is not int:
                    return False
                if not entry_facts.is_creature and p == t == d == 0:
                    continue
                if t <= 0 or d < 0:
                    return False
                if player_id != actor_id and not _SHAPE.search(entry_facts.oracle_text.casefold()):
                    bound = max(bound, p, creature_toughness_left(entry))
                elif (
                    player_id == actor_id
                    and entry_name.casefold() == name.casefold()
                    and entry_id != object_id
                ):
                    peer_strengths.append(min(p, creature_toughness_left(entry)))
    ceiling = bound if any(strength > bound for strength in peer_strengths) else 2 * bound
    return peers > 0 and power > ceiling and creature_toughness_left(body) > ceiling
