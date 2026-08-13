from commander_lab.optimization.constraints import DEFAULT_CONSTRAINTS

def test_h_legacy_phase7_land_constraints_are_unchanged():
    constraints = DEFAULT_CONSTRAINTS["rogshai/current"]
    assert constraints.minimum_lands == 36 and constraints.maximum_lands == 38
    assert constraints.required_commanders == ("Ishai, Ojutai Dragonspeaker", "Rograkh, Son of Rohgahh")
