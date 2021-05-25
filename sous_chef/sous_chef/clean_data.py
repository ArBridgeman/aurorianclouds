from dataclasses import dataclass
from pathlib import Path

from filter_recipes import create_category_or_filter, create_tags_or_filter
from menu.create_manual_menu import retrieve_cuisine_map
from read_recipes import read_recipes


@dataclass
class Config:
    cuisine: str = "cuisine_map.yml"
    recipe_path: Path = Path("../recipe_data")
    recipe_pattern: str = "recipes*.json"
    template_path: Path = Path("../menu_template")


config = Config()
recipes = read_recipes(config)
cuisine_filepath = Path(config.template_path, config.cuisine)
cuisine = retrieve_cuisine_map(cuisine_filepath)
cuisine_tags = [tag for group in cuisine.keys() for tag in cuisine[group]]

mask_is_side_or_entree = create_category_or_filter(recipes, ["Entree", "Side"])
mask_has_no_cuisine = ~create_tags_or_filter(recipes, cuisine_tags)
mask = mask_is_side_or_entree & mask_has_no_cuisine

print(recipes[mask][["title", "tags"]].head(15))
print(recipes[mask].shape)
