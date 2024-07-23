import pandas as pd
from pint import Quantity
from sous_chef.formatter.units import unit_registry
from sous_chef.recipe_book.recipe_util import RecipeSchema


def create_recipe(
    title: str = "dummy_title",
    rating: float = 3.0,
    time_total_str: str = "5 minutes",
    time_inactive_str: str = "0 min",
    ingredients: str = "1 dummy ingredient",
    factor: float = 1.0,
    amount: str = None,
    pint_quantity: Quantity = 3 * unit_registry.cups,
):
    if (time_total := pd.to_timedelta(time_total_str)) is pd.NaT:
        time_total = None
    return RecipeSchema.validate(
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
                    "output": f"{pint_quantity}",
                    "quantity": pint_quantity,
                    "tags": [],
                    "uuid": "1666465773100",
                    "factor": factor,
                    "amount": amount,
                    "url": "nan",
                }
            ],
            index=[0],
        )
    ).squeeze()
