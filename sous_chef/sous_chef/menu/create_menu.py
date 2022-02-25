import datetime
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import List

import pandas as pd
from omegaconf import DictConfig
from sous_chef.date.get_due_date import DueDatetimeFormatter
from sous_chef.formatter.ingredient.format_ingredient import (
    Ingredient,
    IngredientFormatter,
)
from sous_chef.messaging.gsheets_api import GsheetsHelper
from sous_chef.messaging.todoist_api import TodoistHelper
from sous_chef.recipe_book.read_recipe_book import Recipe, RecipeBook
from structlog import get_logger

ABS_FILE_PATH = Path(__file__).absolute().parent
FILE_LOGGER = get_logger(__name__)


# TODO method to scale recipe to desired servings? maybe in recipe checker?


@dataclass
class MenuIngredient:
    ingredient: Ingredient
    from_day: str
    from_recipe: str


@dataclass
class MenuRecipe:
    recipe: Recipe
    eat_factor: float
    freeze_factor: float
    from_day: str
    from_recipe: str


@dataclass
class Menu:
    config: DictConfig
    ingredient_formatter: IngredientFormatter
    recipe_book: RecipeBook
    dataframe: pd.DataFrame = None

    def finalize_fixed_menu(self, gsheets_helper: GsheetsHelper):
        self.dataframe = self._load_fixed_menu(gsheets_helper)
        self.dataframe = self.dataframe.apply(
            self._check_recipe_and_add_cooking_time, axis=1
        )
        self._save_menu()

    def get_menu_for_grocery_list(
        self,
    ) -> (List[MenuIngredient], List[MenuRecipe]):
        self.dataframe = self._load_local_menu()
        mask_grocery_list = self.dataframe["grocery_list"] == "Y"

        mask_manual_ingredient = self.dataframe["type"] == "ingredient"
        mask_manual_ingredient &= mask_grocery_list
        manual_ingredient_list = (
            self.dataframe[mask_manual_ingredient]
            .apply(self._retrieve_manual_menu_ingredient, axis=1)
            .tolist()
        )

        mask_recipe = self.dataframe["type"] == "recipe"
        mask_recipe &= mask_grocery_list
        recipe_list = (
            self.dataframe[mask_recipe]
            .apply(self._retrieve_menu_recipe, axis=1)
            .tolist()
        )
        return manual_ingredient_list, recipe_list

    def upload_menu_to_todoist(self, todoist_helper: TodoistHelper):
        project_name = self.config.todoist.project_name
        if self.config.todoist.remove_existing_task:
            [
                todoist_helper.delete_all_items_in_project(
                    project_name,
                    only_delete_after_date=DueDatetimeFormatter(
                        "Friday"
                    ).get_date(),
                )
                for _ in range(3)
            ]

        mask_menu_task = self.dataframe["menu_list"] == "Y"
        if sum(mask_menu_task) > 0:
            task_list, due_date_list = zip(
                *self.dataframe[mask_menu_task].apply(
                    self._format_task_and_due_date_list, axis=1
                )
            )

            todoist_helper.add_task_list_to_project_with_due_date_list(
                task_list=task_list,
                project=project_name,
                due_date_list=due_date_list,
            )

    @staticmethod
    def _check_fixed_menu_number(menu_number: int):
        if menu_number is None:
            raise ValueError("fixed menu number not specified")
        if not isinstance(menu_number, int):
            raise ValueError(f"fixed menu number ({menu_number}) not an int")
        return menu_number

    def _check_recipe_and_add_cooking_time(self, row: pd.Series) -> pd.Series:
        if row["type"] == "recipe":
            recipe = self.recipe_book.get_recipe_by_title(row["item"])
            row["item"] = recipe.title
            row["total_cook_time"] = recipe.total_cook_time

            # TODO remove/replace once recipes easily viewable in UI
            self._inspect_unrated_recipe(recipe)
        return row

    def _format_task_and_due_date_list(
        self, row: pd.Series
    ) -> (str, datetime.datetime):
        # TODO move default cook time to config?
        cooking_time_min = self._get_cooking_time_min(row.total_cook_time)

        factor_str = f"x eat: {row.eat_factor}"
        if row.freeze_factor:
            factor_str += f", x freeze: {row.freeze_factor}"
        task_str = f"{row['item']} ({factor_str}) [{cooking_time_min} min]"

        due_date = DueDatetimeFormatter().get_due_datetime_with_meal_time(
            weekday=row.weekday, meal_time=row.meal_time
        )
        due_date -= timedelta(minutes=cooking_time_min)
        return task_str, due_date

    @staticmethod
    def _get_cooking_time_min(total_cook_time: timedelta):
        if not total_cook_time:
            return 20
        return int(total_cook_time.total_seconds() / 60)

    def _inspect_unrated_recipe(self, recipe: Recipe):
        if self.config.run_mode.with_inspect_unrated_recipe:
            if recipe.rating == 0.0:
                FILE_LOGGER.warning(
                    "[unrated recipe]",
                    action="print out ingredient_field",
                    recipe_title=recipe.title,
                )
                print(recipe.ingredient_field)

    def _load_fixed_menu(self, gsheets_helper):
        menu_number = self._check_fixed_menu_number(
            self.config.fixed.menu_number
        )
        menu_file = f"{self.config.fixed.file_prefix}{menu_number}"
        fixed_menu = gsheets_helper.get_sheet_as_df(menu_file, menu_file)
        return fixed_menu

    def _load_local_menu(self):
        file_path = Path(ABS_FILE_PATH, self.config.local.file_path)
        # fillna("") to keep consistent with gsheets implementation
        return pd.read_csv(file_path, sep=";").fillna("")

    def _retrieve_manual_menu_ingredient(self, row: pd.Series):
        ingredient = self.ingredient_formatter.format_manual_ingredient(
            quantity=float(row["eat_factor"]),
            unit=row["eat_unit"],
            item=row["item"],
        )
        return MenuIngredient(
            ingredient=ingredient, from_recipe="manual", from_day=row["weekday"]
        )

    def _retrieve_menu_recipe(self, row: pd.Series) -> MenuRecipe:
        recipe = self.recipe_book.get_recipe_by_title(row["item"])
        return MenuRecipe(
            recipe=recipe,
            eat_factor=row["eat_factor"] if row["eat_factor"] else 0.0,
            freeze_factor=row["freeze_factor"] if row["freeze_factor"] else 0.0,
            from_day=row["weekday"],
            from_recipe=row["item"],
        )

    def _save_menu(self):
        tmp_menu_file = Path(ABS_FILE_PATH, self.config.local.file_path)
        FILE_LOGGER.info("[save menu]", tmp_menu_file=tmp_menu_file)
        self.dataframe.to_csv(tmp_menu_file, index=False, header=True, sep=";")
