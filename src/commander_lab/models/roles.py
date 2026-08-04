from enum import StrEnum


class CardRole(StrEnum):
    MANA_SOURCE = "mana_source"
    RAMP = "ramp"
    DRAW = "draw"
    SELECTION = "selection"
    REMOVAL = "removal"
    COUNTER = "counter"
    PROTECTION = "protection"
    WIPE = "wipe"
    RECURSION = "recursion"
    GRAVEYARD_HATE = "graveyard_hate"
    ENGINE = "engine"
    ENABLER = "enabler"
    PAYOFF = "payoff"
    FINISHER = "finisher"
    COMBAT_PAYOFF = "combat_payoff"
    TOKEN_SOURCE = "token_source"
    SACRIFICE_OUTLET = "sacrifice_outlet"
    LAND_SYNERGY = "land_synergy"
