from commander_lab.whole_deck.search_models import WholeDeckSearchConfig

def neutral_config(seed: int) -> WholeDeckSearchConfig:
    return WholeDeckSearchConfig(seed=seed, diversified_starts=2, max_steps_per_start=10, minimum_neighborhood_changes=6, maximum_neighborhood_changes=10, finalist_limit=3)
