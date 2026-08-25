from __future__ import annotations

from pathlib import Path


PATH = Path("src/commander_lab/engine/structural/simulator.py")
FIDELITY_PATH = Path("src/commander_lab/engine/structural/simulator_fidelity.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def replace_first_of_two(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 2:
        raise SystemExit(f"{label}: expected exactly two pre-fix matches, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    text = PATH.read_text(encoding="utf-8")

    text = replace_once(
        text,
        'ENGINE_VERSION = "structural-0.6.1"',
        'ENGINE_VERSION = "structural-0.6.2"',
        "engine version",
    )

    text = replace_once(
        text,
        '''    def __init__(self, decks: dict[str, StructuralDeckProfile]) -> None:\n        self.decks = decks\n\n    def simulate(''',
        '''    def __init__(self, decks: dict[str, StructuralDeckProfile]) -> None:\n        self.decks = decks\n\n    @staticmethod\n    def _deterministic_rng(seed: int, stream: str, relative_position: int) -> random.Random:\n        seed_raw = hashlib.sha256(\n            f"{ENGINE_VERSION}|{seed}|{stream}|{relative_position}".encode()\n        ).digest()\n        return random.Random(int.from_bytes(seed_raw[:8], "big"))\n\n    @staticmethod\n    def _relative_target_priority(actor: _Player, target: _Player, pod_size: int) -> int:\n        distance = (target.seat - actor.seat) % pod_size\n        if distance == 0:\n            return 0\n        return pod_size - distance\n\n    def simulate(''',
        "helpers",
    )

    text = replace_once(
        text,
        '''        capture = bool(event_log_path) if capture_events is None else capture_events\n        rng = random.Random(config.seed)\n        recorder = _EventRecorder(config.match_id, capture=capture)\n        players = self._initialize_players(config, rng, recorder)\n        starting_seat = config.starting_player_seat\n        if starting_seat is None:\n            starting_seat = rng.randrange(len(players))\n        order = players[starting_seat:] + players[:starting_seat]\n''',
        '''        capture = bool(event_log_path) if capture_events is None else capture_events\n        recorder = _EventRecorder(config.match_id, capture=capture)\n        starting_seat = config.starting_player_seat\n        if starting_seat is None:\n            starting_rng = self._deterministic_rng(config.seed, "starting_player", 0)\n            starting_seat = starting_rng.randrange(len(config.deck_ids))\n        players = self._initialize_players(config, starting_seat, recorder)\n        order = players[starting_seat:] + players[:starting_seat]\n''',
        "simulate rng setup",
    )

    text = replace_once(
        text,
        '''    def _initialize_players(\n        self,\n        config: StructuralMatchConfig,\n        rng: random.Random,\n        recorder: _EventRecorder,\n    ) -> list[_Player]:\n        players: list[_Player] = []\n        for seat, deck_id in enumerate(config.deck_ids):\n            deck = self.decks[deck_id]\n            commander_names = set(deck.commander_names)\n            library = [card for card in deck.cards if card.oracle_name not in commander_names]\n            rng.shuffle(library)\n            pilot_config = config.pilot_configs[seat] if config.pilot_configs else PilotConfig()\n            pilot = build_pilot(pilot_config, strategy=deck.commander_strategy)\n            pilot_seed_raw = hashlib.sha256(\n                f"{ENGINE_VERSION}|{config.seed}|{config.match_id}|pilot|{seat}".encode()\n            ).digest()\n            player = _Player(\n                player_id=f"p{seat + 1}",\n                seat=seat,\n                deck=deck,\n                pilot=pilot,\n                pilot_rng=random.Random(int.from_bytes(pilot_seed_raw[:8], "big")),\n                library=library,\n''',
        '''    def _initialize_players(\n        self,\n        config: StructuralMatchConfig,\n        starting_seat: int,\n        recorder: _EventRecorder,\n    ) -> list[_Player]:\n        players: list[_Player] = []\n        pod_size = len(config.deck_ids)\n        for seat, deck_id in enumerate(config.deck_ids):\n            deck = self.decks[deck_id]\n            commander_names = set(deck.commander_names)\n            library = [card for card in deck.cards if card.oracle_name not in commander_names]\n            relative_position = (seat - starting_seat) % pod_size\n            library_rng = self._deterministic_rng(config.seed, "library", relative_position)\n            library_rng.shuffle(library)\n            pilot_config = config.pilot_configs[seat] if config.pilot_configs else PilotConfig()\n            pilot = build_pilot(pilot_config, strategy=deck.commander_strategy)\n            player = _Player(\n                player_id=f"p{seat + 1}",\n                seat=seat,\n                deck=deck,\n                pilot=pilot,\n                pilot_rng=self._deterministic_rng(config.seed, "pilot", relative_position),\n                library=library,\n''',
        "initialize player streams",
    )

    text = replace_once(
        text,
        '''                self._apply_opening_hand_override(\n                    player, config.opening_hand_overrides[seat] or (), rng, recorder\n                )\n            else:\n                self._london_mulligan(\n                    player,\n                    rng,\n                    recorder,\n''',
        '''                self._apply_opening_hand_override(\n                    player, config.opening_hand_overrides[seat] or (), library_rng, recorder\n                )\n            else:\n                self._london_mulligan(\n                    player,\n                    library_rng,\n                    recorder,\n''',
        "mulligan rng stream",
    )

    text = replace_once(
        text,
        '''        for opponent in players:\n            if opponent.player_id == player.player_id or not opponent.alive:\n                continue\n            outgoing = {\n''',
        '''        ordered_opponents = sorted(\n            (\n                opponent\n                for opponent in players\n                if opponent.player_id != player.player_id and opponent.alive\n            ),\n            key=lambda opponent: (\n                (opponent.seat - player.seat) % len(players),\n                opponent.player_id,\n            ),\n        )\n        for opponent in ordered_opponents:\n            outgoing = {\n''',
        "pilot opponent ordering",
    )

    text = replace_first_of_two(
        text,
        '''        targets = [\n            opponent\n            for opponent in players\n            if opponent.alive and opponent.player_id != player.player_id\n        ]\n        if not targets:\n            return\n        state = self._pilot_state(player, players, max(1, player.current_turn))\n        target_actions: list[PilotActionView] = []\n        target_mapping: dict[str, _Player] = {}\n        for opponent in targets:\n''',
        '''        targets = sorted(\n            (\n                opponent\n                for opponent in players\n                if opponent.alive and opponent.player_id != player.player_id\n            ),\n            key=lambda opponent: (\n                (opponent.seat - player.seat) % len(players),\n                opponent.player_id,\n            ),\n        )\n        if not targets:\n            return\n        state = self._pilot_state(player, players, max(1, player.current_turn))\n        target_actions: list[PilotActionView] = []\n        target_mapping: dict[str, _Player] = {}\n        for opponent in targets:\n''',
        "removal target ordering",
    )
    text = replace_once(
        text,
        '            action_id = f"removal_target:{opponent.player_id}"',
        '            priority = self._relative_target_priority(player, opponent, len(players))\n            action_id = f"removal_target:r{priority}:{opponent.player_id}"',
        "removal target id",
    )

    text = replace_once(
        text,
        '''        targets = [\n            opponent\n            for opponent in players\n            if opponent.alive and opponent.player_id != player.player_id\n        ]\n        if not targets:\n            return\n        state = self._pilot_state(player, players, max(1, player.current_turn))\n        target_actions: list[PilotActionView] = []\n        target_mapping: dict[str, _Player] = {}\n        for opponent in targets:\n''',
        '''        targets = sorted(\n            (\n                opponent\n                for opponent in players\n                if opponent.alive and opponent.player_id != player.player_id\n            ),\n            key=lambda opponent: (\n                (opponent.seat - player.seat) % len(players),\n                opponent.player_id,\n            ),\n        )\n        if not targets:\n            return\n        state = self._pilot_state(player, players, max(1, player.current_turn))\n        target_actions: list[PilotActionView] = []\n        target_mapping: dict[str, _Player] = {}\n        for opponent in targets:\n''',
        "graveyard target ordering",
    )
    text = replace_once(
        text,
        '            action_id = f"graveyard_target:{opponent.player_id}"',
        '            priority = self._relative_target_priority(player, opponent, len(players))\n            action_id = f"graveyard_target:r{priority}:{opponent.player_id}"',
        "graveyard target id",
    )

    text = replace_once(
        text,
        '''        targets = [\n            opponent\n            for opponent in players\n            if opponent.alive and opponent.player_id != player.player_id\n        ]\n        state = self._pilot_state(player, players, turn)\n''',
        '''        targets = sorted(\n            (\n                opponent\n                for opponent in players\n                if opponent.alive and opponent.player_id != player.player_id\n            ),\n            key=lambda opponent: (\n                (opponent.seat - player.seat) % len(players),\n                opponent.player_id,\n            ),\n        )\n        state = self._pilot_state(player, players, turn)\n''',
        "combat target ordering",
    )
    text = replace_once(
        text,
        '            action_id = f"combat_target:{opponent.player_id}"',
        '            priority = self._relative_target_priority(player, opponent, len(players))\n            action_id = f"combat_target:r{priority}:{opponent.player_id}"',
        "combat target id",
    )

    text = replace_once(
        text,
        '''    def _check_eliminations(\n        self, players: list[_Player], turn: int, recorder: _EventRecorder\n    ) -> None:\n        for player in players:\n            if not player.alive:\n                continue\n            commander_lethal = commander_damage_is_lethal(player.commander_damage_received)\n            if player.life <= 0 or commander_lethal or player.elimination_reason == "empty_library":\n                alive_before = sum(item.alive for item in players)\n                player.alive = False\n                player.placement = alive_before\n                player.eliminated_turn = turn\n                if player.elimination_reason is None:\n                    player.elimination_reason = (\n                        "commander_damage" if commander_lethal else "life_total"\n                    )\n                recorder.emit(\n                    "player_eliminated",\n                    actor_id=player.player_id,\n                    payload={\n                        "placement": player.placement,\n                        "reason": player.elimination_reason,\n                        "turn": turn,\n                    },\n                )\n''',
        '''    def _check_eliminations(\n        self, players: list[_Player], turn: int, recorder: _EventRecorder\n    ) -> None:\n        alive_before = sum(item.alive for item in players)\n        eliminated: list[tuple[_Player, bool]] = []\n        for player in players:\n            if not player.alive:\n                continue\n            commander_lethal = commander_damage_is_lethal(player.commander_damage_received)\n            if player.life <= 0 or commander_lethal or player.elimination_reason == "empty_library":\n                eliminated.append((player, commander_lethal))\n        if not eliminated:\n            return\n        tied_placement = alive_before - len(eliminated) + 1\n        for player, commander_lethal in eliminated:\n            player.alive = False\n            player.placement = tied_placement\n            player.eliminated_turn = turn\n            if player.elimination_reason is None:\n                player.elimination_reason = (\n                    "commander_damage" if commander_lethal else "life_total"\n                )\n            recorder.emit(\n                "player_eliminated",\n                actor_id=player.player_id,\n                payload={\n                    "placement": player.placement,\n                    "reason": player.elimination_reason,\n                    "turn": turn,\n                },\n            )\n''',
        "simultaneous eliminations",
    )

    fidelity = FIDELITY_PATH.read_text(encoding="utf-8")
    fidelity = replace_once(
        fidelity,
        "import hashlib\nimport random\n",
        "",
        "fidelity obsolete rng imports",
    )
    fidelity = replace_once(
        fidelity,
        'FIDELITY_ENGINE_VERSION = "structural-fidelity-overlay-2026-08-21-v1"',
        'FIDELITY_ENGINE_VERSION = "structural-fidelity-overlay-2026-08-25-v2"',
        "fidelity engine version",
    )
    fidelity = replace_once(
        fidelity,
        '''    def _initialize_players(\n        self,\n        config: StructuralMatchConfig,\n        rng: random.Random,\n        recorder: _EventRecorder,\n    ) -> list[_Player]:\n        players: list[_Player] = []\n        for seat, deck_id in enumerate(config.deck_ids):\n            deck = self.decks[deck_id]\n            commander_names = set(deck.commander_names)\n            library = [card for card in deck.cards if card.oracle_name not in commander_names]\n            rng.shuffle(library)\n            pilot_config = config.pilot_configs[seat] if config.pilot_configs else PilotConfig()\n            pilot = build_pilot(pilot_config, strategy=deck.commander_strategy)\n            pilot_seed_raw = hashlib.sha256(\n                f"{FIDELITY_ENGINE_VERSION}|{config.seed}|pilot|{seat}".encode()\n            ).digest()\n            player = _Player(\n                player_id=f"p{seat + 1}",\n                seat=seat,\n                deck=deck,\n                pilot=pilot,\n                pilot_rng=random.Random(int.from_bytes(pilot_seed_raw[:8], "big")),\n                library=library,\n                commanders={\n                    name: _Commander(\n                        name=name,\n                        base_cost=deck.commander_base_costs[name],\n                        base_power=deck.commander_base_power.get(name, 2.0),\n                        power=deck.commander_base_power.get(name, 2.0),\n                    )\n                    for name in deck.commander_names\n                },\n            )\n            if config.opening_hand_overrides and config.opening_hand_overrides[seat] is not None:\n                self._apply_opening_hand_override(\n                    player, config.opening_hand_overrides[seat] or (), rng, recorder\n                )\n            else:\n                self._london_mulligan(\n                    player,\n                    rng,\n                    recorder,\n                    config.free_multiplayer_mulligan and len(config.deck_ids) >= 3,\n                )\n            players.append(player)\n        return players\n''',
        '''    def _initialize_players(\n        self,\n        config: StructuralMatchConfig,\n        starting_seat: int,\n        recorder: _EventRecorder,\n    ) -> list[_Player]:\n        players: list[_Player] = []\n        pod_size = len(config.deck_ids)\n        for seat, deck_id in enumerate(config.deck_ids):\n            deck = self.decks[deck_id]\n            commander_names = set(deck.commander_names)\n            library = [card for card in deck.cards if card.oracle_name not in commander_names]\n            relative_position = (seat - starting_seat) % pod_size\n            library_rng = self._deterministic_rng(config.seed, "library", relative_position)\n            library_rng.shuffle(library)\n            pilot_config = config.pilot_configs[seat] if config.pilot_configs else PilotConfig()\n            pilot = build_pilot(pilot_config, strategy=deck.commander_strategy)\n            player = _Player(\n                player_id=f"p{seat + 1}",\n                seat=seat,\n                deck=deck,\n                pilot=pilot,\n                pilot_rng=self._deterministic_rng(config.seed, "pilot", relative_position),\n                library=library,\n                commanders={\n                    name: _Commander(\n                        name=name,\n                        base_cost=deck.commander_base_costs[name],\n                        base_power=deck.commander_base_power.get(name, 2.0),\n                        power=deck.commander_base_power.get(name, 2.0),\n                    )\n                    for name in deck.commander_names\n                },\n            )\n            if config.opening_hand_overrides and config.opening_hand_overrides[seat] is not None:\n                self._apply_opening_hand_override(\n                    player, config.opening_hand_overrides[seat] or (), library_rng, recorder\n                )\n            else:\n                self._london_mulligan(\n                    player,\n                    library_rng,\n                    recorder,\n                    config.free_multiplayer_mulligan and len(config.deck_ids) >= 3,\n                )\n            players.append(player)\n        return players\n''',
        "fidelity initialize player streams",
    )

    PATH.write_text(text, encoding="utf-8")
    FIDELITY_PATH.write_text(fidelity, encoding="utf-8")
    print("STRUCTURAL_SEAT_SYMMETRY_FIX_APPLIED=PASS")
    print("STRUCTURAL_FIDELITY_OVERLAY_SEAT_FIX_APPLIED=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
