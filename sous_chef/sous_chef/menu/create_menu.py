import datetime
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pandera as pa
from omegaconf import DictConfig
from pandera.typing import Series
from sous_chef.date.get_due_date import DueDatetimeFormatter, MealTime, Weekday
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


class MenuSchema(pa.SchemaModel):
    weekday: Series[str] = pa.Field(isin=Weekday.name_list("capitalize"))
    meal_time: Series[str] = pa.Field(isin=MealTime.name_list("lower"))
    type: Series[str] = pa.Field(
        isin=["category", "ingredient", "recipe", "tag"]
    )
    eat_factor: Series[float] = pa.Field(gt=0, nullable=False)
    eat_unit: Series[str]
    freeze_factor: Series[float] = pa.Field(ge=0, nullable=False)
    item: Series[str]
    grocery_list: Series[str] = pa.Field(isin=["Y", "N"])
    menu_list: Series[str] = pa.Field(isin=["Y", "N"])


@dataclass
class Menu:
    config: DictConfig
    ingredient_formatter: IngredientFormatter
    recipe_book: RecipeBook
    dataframe: pd.DataFrame = None

    def finalize_fixed_menu(self, gsheets_helper: GsheetsHelper):
        self.dataframe = self._load_fixed_menu(gsheets_helper)
        self._validate_menu()
        self.dataframe = self.dataframe.apply(self._process_menu, axis=1)
        self._save_menu()

    def get_menu_for_grocery_list(
        self,
    ) -> (list[MenuIngredient], list[MenuRecipe]):
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
            anchor_date = DueDatetimeFormatter().get_anchor_date()
            [
                todoist_helper.delete_all_items_in_project(
                    project_name,
                    only_delete_after_date=anchor_date,
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

    def _check_manual_ingredient(self, row: pd.Series):
        return self.ingredient_formatter.format_manual_ingredient(
            quantity=float(row["eat_factor"]),
            unit=row["eat_unit"],
            item=row["item"],
        )

    def _check_recipe_and_add_cooking_time(self, row: pd.Series) -> pd.Series:
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
        if row.freeze_factor > 0:
            factor_str += f", x freeze: {row.freeze_factor}"
        task_str = f"{row['item']} ({factor_str}) [{cooking_time_min} min]"

        due_date = DueDatetimeFormatter().get_due_datetime_with_meal_time(
            weekday=row.weekday, meal_time=row.meal_time
        )
        due_date -= timedelta(minutes=cooking_time_min)
        return task_str, due_date

    @staticmethod
    def _get_cooking_time_min(
        total_cook_time: timedelta, default_time: int = 20
    ):
        if not isinstance(total_cook_time, timedelta):
            return default_time
        if (cook_time := int(total_cook_time.total_seconds() / 60)) < 0:
            return default_time
        return cook_time

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
        menu_basic_file = self.config.fixed.basic
        menu_basic = gsheets_helper.get_sheet_as_df(
            menu_basic_file, menu_basic_file
        )

        menu_number = self._check_fixed_menu_number(
            self.config.fixed.menu_number
        )
        menu_fixed_file = f"{self.config.fixed.file_prefix}{menu_number}"
        menu_fixed = gsheets_helper.get_sheet_as_df(
            menu_fixed_file, menu_fixed_file
        )
        return pd.concat([menu_basic, menu_fixed]).sort_values(
            by=["weekday", "meal_time"]
        )

    def _load_local_menu(self):
        file_path = Path(ABS_FILE_PATH, self.config.local.file_path)
        # fillna("") to keep consistent with gsheets implementation
        return pd.read_csv(file_path, sep=";").fillna("")

    def _process_menu(self, row: pd.Series):
        # due to schema validation row["type"], may only be 1 of these 4 types
        FILE_LOGGER.info(
            "[process menu]",
            action="processing",
            day=row["weekday"],
            item=row["item"],
            type=row["type"],
        )
        if row["type"] == "category":
            return self._select_random_recipe(
                row, "get_random_recipe_by_category"
            )
        if row["type"] == "ingredient" and row["grocery_list"] == "Y":
            # do NOT need returned as found as is
            self._check_manual_ingredient(row)
            return row
        if row["type"] == "recipe":
            return self._check_recipe_and_add_cooking_time(row)
        if row["type"] == "tag":
            return self._select_random_recipe(row, "get_random_recipe_by_tag")

    def _retrieve_manual_menu_ingredient(
        self, row: pd.Series
    ) -> MenuIngredient:
        return MenuIngredient(
            ingredient=self._check_manual_ingredient(row),
            from_recipe="manual",
            from_day=row["weekday"],
        )

    def _retrieve_menu_recipe(self, row: pd.Series) -> MenuRecipe:
        recipe = self.recipe_book.get_recipe_by_title(row["item"])
        return MenuRecipe(
            recipe=recipe,
            eat_factor=row["eat_factor"],
            freeze_factor=row["freeze_factor"],
            from_day=row["weekday"],
            from_recipe=row["item"],
        )

    def _select_random_recipe(self, row: pd.Series, method: str):
        recipe = getattr(self.recipe_book, method)(row["item"])
        row["item"] = recipe.title
        row["type"] = "recipe"
        return row

    def _save_menu(self):
        tmp_menu_file = Path(ABS_FILE_PATH, self.config.local.file_path)
        FILE_LOGGER.info("[save menu]", tmp_menu_file=tmp_menu_file)
        self.dataframe.to_csv(tmp_menu_file, index=False, header=True, sep=";")

    def _validate_menu(self):
        # if fails, tosses SchemaError
        # TODO do we want to return their type? do we trust it?
        MenuSchema.validate(self.dataframe)
