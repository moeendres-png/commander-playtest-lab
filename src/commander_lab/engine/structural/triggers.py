from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class AbstractTrigger:
    trigger_id: str
    controller_seat: int
    source_name: str
    controller_order: int = 0
    mandatory: bool = True


def order_simultaneous_triggers(
    triggers: Iterable[AbstractTrigger],
    *,
    active_player_seat: int,
    pod_size: int,
) -> tuple[AbstractTrigger, ...]:
    """Return deterministic stack insertion order using an APNAP abstraction.

    The active player's triggers are put on the stack first, then nonactive players in
    turn order.  Within one controller's group, ``controller_order`` is authoritative;
    source name and trigger id are deterministic tie-breakers.  Resolution order is the
    reverse of this tuple.
    """

    if pod_size < 1:
        raise ValueError("pod_size must be positive")
    if not 0 <= active_player_seat < pod_size:
        raise ValueError("active_player_seat is outside the pod")
    trigger_list = tuple(triggers)
    if any(not 0 <= trigger.controller_seat < pod_size for trigger in trigger_list):
        raise ValueError("trigger controller seat is outside the pod")

    def apnap_position(seat: int) -> int:
        return (seat - active_player_seat) % pod_size

    return tuple(
        sorted(
            trigger_list,
            key=lambda trigger: (
                apnap_position(trigger.controller_seat),
                trigger.controller_order,
                trigger.source_name.casefold(),
                trigger.trigger_id,
            ),
        )
    )


def trigger_resolution_order(
    triggers: Iterable[AbstractTrigger],
    *,
    active_player_seat: int,
    pod_size: int,
) -> tuple[AbstractTrigger, ...]:
    return tuple(
        reversed(
            order_simultaneous_triggers(
                triggers,
                active_player_seat=active_player_seat,
                pod_size=pod_size,
            )
        )
    )
