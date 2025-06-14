import datetime
from collections import defaultdict
from dataclasses import dataclass
from typing import List
from warnings import warn

import pandas as pd
from omegaconf import DictConfig
from pandera.typing.common import DataFrameBase
from sous_chef.abstract.handle_exception import BaseWithExceptionHandling
from sous_chef.formatter.ingredient.format_ingredient import (
    Ingredient,
    IngredientFormatter,
)
from sous_chef.menu.create_menu._fill_menu_template import (
    MapMenuErrorToException,
)
from sous_chef.menu.create_menu.exceptions import MenuIncompleteError
from sous_chef.menu.create_menu.models import TmpMenuSchema, YesNo
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from sous_chef.recipe_book.recipe_util import RecipeSchema
from termcolor import cprint


@dataclass
class MenuIngredient:
    ingredient: Ingredient
    for_day: datetime.datetime
    from_recipe: str


@dataclass
class MenuRecipe:
    recipe: RecipeSchema
    eat_factor: float
    freeze_factor: float
    for_day: datetime.datetime
    from_recipe: str


class MenuForGroceryList(BaseWithExceptionHandling):
    def __init__(
        self,
        config_errors: DictConfig,
        final_menu_df: DataFrameBase[TmpMenuSchema],
        ingredient_formatter: IngredientFormatter,
        recipe_book: RecipeBook,
    ):
        warn(
            f"{self.__class__.__name__} is deprecated. "
            "This should be reduced & instead be in the grocery_list service",
            DeprecationWarning,
            stacklevel=2,
        )

        self.dataframe = final_menu_df
        self.ingredient_formatter = ingredient_formatter
        self.recipe_book = recipe_book

        self.set_tuple_log_and_skip_exception_from_config(
            config_errors=config_errors,
            exception_mapper=MapMenuErrorToException,
        )

    def get_menu_for_grocery_list(
        self,
    ) -> (List[MenuIngredient], List[MenuRecipe]):
        self.record_exception = []

        entry_funcs = {
            "ingredient": self._retrieve_manual_menu_ingredient,
            "recipe": self._retrieve_menu_recipe,
        }
        result_dict = defaultdict(list)
        mask_defrost = self.dataframe.defrost != YesNo.yes.value
        for entry, entry_fct in entry_funcs.items():
            if (
                mask := ((self.dataframe["type"] == entry) & mask_defrost)
            ).sum() > 0:
                result_dict[entry] = (
                    self.dataframe[mask].apply(entry_fct, axis=1).tolist()
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
        ingredient = self.ingredient_formatter.format_manual_ingredient(
            quantity=float(row["eat_factor"]),
            unit=row["eat_unit"],
            item=row["item"],
        )
        return MenuIngredient(
            ingredient=ingredient,
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
