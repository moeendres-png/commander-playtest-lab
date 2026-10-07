"""A scripted Protocol-2 surface for the #572 starting-player negative controls.

The fake answers only the transport messages the generic driver's launch,
create, start and decision surfaces need. It computes no legality and, in
particular, publishes the XMage start readback and CR 103.2 prompt identities
independently so a test can remove or mismatch any one of them.
"""

from __future__ import annotations

from typing import Any


class StartingFrameProcess:
    """A Protocol-2 surface that records every create request and submission."""

    def __init__(
        self,
        *,
        candidate: str,
        offered_seats: list[str | None] | None = None,
        create_echo: int | None = None,
        create_echo_present: bool = True,
        start_player_id: str | None = "engine-p1",
        start_player_id_present: bool = True,
        start_chooser_id: str | None = None,
        start_chooser_id_present: bool = True,
        start_chosen_id: str | None = None,
        start_chosen_id_present: bool = True,
        submit_error: dict[str, Any] | None = None,
    ) -> None:
        self.candidate = candidate
        self.offered_seats = offered_seats
        self.create_echo = create_echo
        self.create_echo_present = create_echo_present
        self.start_player_id = start_player_id
        self.start_player_id_present = start_player_id_present
        # The compatibility bridge reports the identities of the CR 103.2
        # prompt it answered. None means "the same engine id the engine
        # established", which is what the real bridge records when it answers
        # with the declared seat; an explicit override or a
        # ``*_present=False`` models a mismatched or unanswered prompt role.
        self.start_chooser_id = start_chooser_id
        self.start_chooser_id_present = start_chooser_id_present
        self.start_chosen_id = start_chosen_id
        self.start_chosen_id_present = start_chosen_id_present
        self.submit_error = submit_error
        self.create_requests: list[dict[str, Any]] = []
        self.submissions: list[dict[str, Any]] = []
        self.passes = 0
        self.handles = 0

    def request(
        self,
        message_type: str,
        payload: dict[str, Any],
        *,
        game_id: str | None = None,
        timeout_s: float = 0,
    ) -> dict[str, Any]:
        del game_id, timeout_s
        if message_type in {"start_engine", "get_provider_version"}:
            return {"success": True, "payload": {}}
        if message_type == "get_capabilities":
            return {"success": True, "payload": {"capabilities": {"seed_supported": False}}}
        if message_type == "import_deck":
            self.handles += 1
            return {"success": True, "payload": {"deck_handle": {"handle_id": f"d{self.handles}"}}}
        if message_type == "create_commander_game":
            self.create_requests.append(payload["request"])
            created: dict[str, Any] = {"player_count": 2}
            if self.create_echo_present:
                created["starting_player_seat"] = self.create_echo
            return {"success": True, "payload": created}
        if message_type == "start_game":
            started: dict[str, Any] = {"status": "started"}
            if self.start_player_id_present:
                started["starting_player_id"] = self.start_player_id
                if self.start_chooser_id_present:
                    started["starting_player_chooser_id"] = (
                        self.start_player_id
                        if self.start_chooser_id is None
                        else self.start_chooser_id
                    )
                if self.start_chosen_id_present:
                    started["starting_player_chosen_id"] = (
                        self.start_player_id
                        if self.start_chosen_id is None
                        else self.start_chosen_id
                    )
            return {"success": True, "payload": started}
        if message_type == "get_game_state":
            # The engine's own seat roster: principal envelope + live engine id
            # per seat, as the compatibility lane publishes it.
            observer = str(payload["observer_player_id"])
            index = 0 if observer == "p1" else 1
            engine_id = "engine-p1" if index == 0 else "engine-p2"
            rows = [
                {
                    "player_id": "engine-p1" if position == 0 else "engine-p2",
                    "seat": position,
                    "zones": {"hand": [None] * 7, "library_size": 92},
                }
                for position in range(2)
            ]
            return {
                "success": True,
                "payload": {
                    "observer_player_id": observer,
                    "observer_seat": index,
                    "observer_engine_player_id": engine_id,
                    "state": {"players": rows},
                },
            }
        if message_type == "submit_action":
            self.submissions.append(payload)
            if self.submit_error is not None:
                return self.submit_error
            return {"success": True, "payload": {"decision": {"executed": True}}}
        if message_type == "pass_priority":
            self.passes += 1
            return {"success": True, "payload": {}}
        raise AssertionError(f"unexpected request {message_type}")
