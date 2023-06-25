import datetime
from collections import defaultdict
from dataclasses import dataclass
from typing import List

import pandas as pd
from sous_chef.abstract.handle_exception import BaseWithExceptionHandling
from sous_chef.formatter.ingredient.format_ingredient import Ingredient
from sous_chef.menu.create_menu._menu_basic import (
    MenuBasic,
    MenuIncompleteError,
)
from sous_chef.recipe_book.recipe_util import Recipe
from termcolor import cprint


@dataclass
class MenuIngredient:
    ingredient: Ingredient
    for_day: datetime.datetime
    from_recipe: str


@dataclass
class MenuRecipe:
    recipe: Recipe
    eat_factor: float
    freeze_factor: float
    for_day: datetime.datetime
    from_recipe: str


class MenuForGroceryList(MenuBasic):
    def get_menu_for_grocery_list(
        self,
    ) -> (List[MenuIngredient], List[MenuRecipe]):
        self.record_exception = []

        self.load_final_menu()

        entry_funcs = {
            "ingredient": self._retrieve_manual_menu_ingredient,
            "recipe": self._retrieve_menu_recipe,
        }
        result_dict = defaultdict(list)
        mask_defrost = self.dataframe.defrost != "Y"
        for entry, entry_fct in entry_funcs.items():
            if (mask := self.dataframe["type"] == entry).sum() > 0:
                result_dict[entry] = (
                    self.dataframe[mask & mask_defrost]
                    .apply(entry_fct, axis=1)
                    .tolist()
                )
        if len(self.record_exception) > 0:
            cprint("\t" + "\n\t".join(self.record_exception), "green")
            raise MenuIncompleteError(
                custom_message="will not send to grocery list until fixed"
            )
        return result_dict["ingredient"], result_dict["recipe"]

    @BaseWithExceptionHandling.ExceptionHandler.handle_exception
    def _retrieve_manual_menu_ingredient(
        self, row: pd.Series
    ) -> MenuIngredient:
        return MenuIngredient(
            ingredient=self._check_manual_ingredient(row),
            from_recipe="manual",
            for_day=row["prep_datetime"],
        )

    @BaseWithExceptionHandling.ExceptionHandler.handle_exception
    def _retrieve_menu_recipe(self, row: pd.Series) -> MenuRecipe:
        recipe = self.recipe_book.get_recipe_by_title(row["item"])
        return MenuRecipe(
            recipe=recipe,
            eat_factor=row["eat_factor"],
            freeze_factor=row["freeze_factor"],
            for_day=row["prep_datetime"],
            from_recipe=row["item"],
        )
