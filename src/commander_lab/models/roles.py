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


class StructuralMechanic(StrEnum):
    """Orthogonal structural mechanics used for decision quality, not rules fidelity."""

    SACRIFICE_COST = "sacrifice_cost"
    SACRIFICE_OUTLET = "sacrifice_outlet"
    SACRIFICE_PAYOFF = "sacrifice_payoff"
    DEATH_TRIGGER = "death_trigger"
    TOKEN_ENGINE = "token_engine"
    REPEATABLE_TOKEN_SOURCE = "repeatable_token_source"
    LAND_RECURSION = "land_recursion"
    ARTIFACT_ENGINE = "artifact_engine"
    GRAVEYARD_RECURSION = "graveyard_recursion"
    GO_WIDE = "go_wide"
    TABLE_DAMAGE = "table_damage"
    COMMANDER_DAMAGE_SUPPORT = "commander_damage_support"
    REBUILD = "rebuild"
    STACK_INTERACTION = "stack_interaction"
    FINISHER_COMPRESSION = "finisher_compression"
    COMMANDER_DEPENDENT = "commander_dependent"
    COMMANDER_INDEPENDENT = "commander_independent"
