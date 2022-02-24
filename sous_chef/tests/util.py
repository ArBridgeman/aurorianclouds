import pandas as pd
from sous_chef.recipe_book.read_recipe_book import Recipe


class RecipeBuilder:
    def __init__(self):
        self._entity = Recipe(
            title="dummy_title",
            rating=0.0,
            total_cook_time=pd.to_timedelta("5 minutes"),
            ingredient_field="1 dummy text",
        )

    def with_recipe_title(self, recipe_title: str):
        self._entity.title = recipe_title
        return self

    def with_total_cook_time(self, total_cook_time_str: str):
        self._entity.total_cook_time = pd.to_timedelta(total_cook_time_str)
        return self

    def with_rating(self, rating: float):
        self._entity.rating = rating
        return self

    def build(self):
        return self._entity
