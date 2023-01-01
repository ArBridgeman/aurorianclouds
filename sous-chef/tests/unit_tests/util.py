import pandas as pd
from sous_chef.recipe_book.read_recipe_book import Recipe


def create_recipe(
    title: str = "dummy_title",
    rating: float = 3.0,
    time_total_str: str = "5 minutes",
    time_inactive_str: str = "0 min",
    ingredients: str = "1 dummy ingredient",
    factor: float = 1.0,
    amount: str = None,
):
    if (time_total := pd.to_timedelta(time_total_str)) is pd.NaT:
        time_total = None
    return Recipe.validate(
        pd.DataFrame(
            [
                {
                    "title": title,
                    "time_preparation": time_total,
                    "time_cooking": pd.to_timedelta("0 min"),
                    "time_inactive": pd.to_timedelta(time_inactive_str),
                    "time_total": time_total,
                    "ingredients": ingredients,
                    "instructions": "",
                    "rating": rating,
                    "favorite": False,
                    "categories": [],
                    "quantity": "3 servings",
                    "tags": [],
                    "uuid": "1666465773100",
                    "factor": factor,
                    "amount": amount,
                }
            ],
            index=[0],
        )
    ).squeeze()
