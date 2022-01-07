from dataclasses import dataclass

import pandas as pd


@dataclass
class Recipe:
    title: str
    min_prep_time: int
    min_cook_time: int
    quantity: str
    is_favorite: bool
    rating: int
    tags: list


recipe1 = Recipe(
    "Bourbon Chicken",
    10,
    30,
    "4 servings",
    False,
    0,
    ["poultry", "American", "BBQ"],
)

RECIPES = pd.DataFrame([recipe1])
