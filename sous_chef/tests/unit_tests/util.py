import pandas as pd
from sous_chef.recipe_book.read_recipe_book import Recipe


def create_recipe(
    title="dummy_title",
    rating=0.0,
    total_cook_time_str="5 minutes",
    ingredient_field="1 dummy text",
    factor=1.0,
):
    return Recipe(
        title=title,
        rating=rating,
        total_cook_time=pd.to_timedelta(total_cook_time_str),
        ingredient_field=ingredient_field,
        factor=factor,
    )
