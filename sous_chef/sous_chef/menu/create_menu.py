import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import List

import pandas as pd
from omegaconf import DictConfig
from sous_chef.date.get_date import (
    DAYS_OF_WEEK,
    DESIRED_MEAL_TIMES,
    get_anchor_date,
    get_due_date,
)
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


@dataclass
class MenuIngredient:
    ingredient: Ingredient
    from_day: str
    from_recipe: str


@dataclass
class MenuRecipe:
    recipe: Recipe
    factor: float
    from_day: str
    from_recipe: str


@dataclass
class Menu:
    config: DictConfig
    ingredient_formatter: IngredientFormatter
    recipe_book: RecipeBook
    dataframe: pd.DataFrame = pd.DataFrame()

    def finalize_fixed_menu(self, gsheets_helper: GsheetsHelper):
        self.dataframe = self._load_fixed_menu(gsheets_helper)
        self._validate_menu_with_user()
        self.dataframe = self.dataframe[self.dataframe.factor > 0]
        self.dataframe = self.dataframe.apply(
            self._enrich_with_cooking_time, axis=1
        )
        self._save_menu()

    def get_menu_for_grocery_list(
        self,
    ) -> (List[MenuIngredient], List[MenuRecipe]):
        self._load_local_menu()
        mask_grocery_list = self.dataframe["grocery_list"] == "Y"
        menu_for_grocery_list = self.dataframe[mask_grocery_list].copy(
            deep=True
        )

        mask_manual_ingredient = menu_for_grocery_list["type"] == "ingredient"
        manual_ingredient_list = self._retrieve_manual_menu_ingredient_list(
            menu_for_grocery_list[mask_manual_ingredient].copy(deep=True)
        )

        mask_recipe = menu_for_grocery_list["type"] == "recipe"
        recipe_list = self._retrieve_menu_recipe_list(
            menu_for_grocery_list[mask_recipe].copy(deep=True)
        )
        return manual_ingredient_list, recipe_list

    def upload_menu_to_todoist(self, todoist_helper: TodoistHelper):
        project_name = self.config.todoist.project_name

        if self.config.todoist.remove_existing_task:
            [
                todoist_helper.delete_all_items_in_project(
                    project_name,
                    only_delete_after_date=get_due_date(4).date(),
                )
                for _ in range(3)
            ]

        for _, item in self.dataframe.iterrows():
            if item.menu_list != "Y":
                continue

            # TODO in menu split name to name and time_of_day column
            # TODO make time_of_day an enum or something here
            # by default dinner entry
            time_in_day = "evening"

            weekday = item.weekday
            if "_" in weekday:
                weekday, time_in_day = weekday.split("_")
            weekday_index = DAYS_OF_WEEK.index(weekday.lower())

            in_day_split = DESIRED_MEAL_TIMES[time_in_day].split(":")
            due_date = get_due_date(
                weekday_index,
                get_anchor_date(4),
                hour=int(in_day_split[0]),
                minute=int(in_day_split[1]),
            )

            # TODO move default cook time to config
            cooking_time_min = 20
            if not pd.isna(item.total_cook_time):
                cooking_time_min = int(
                    item.total_cook_time.total_seconds() / 60
                )

            due_date = due_date - datetime.timedelta(minutes=cooking_time_min)
            due_date_str = due_date.strftime("on %Y-%m-%d at %H:%M")
            due_dict = {"string": due_date_str}

            formatted_item = "{item} (x {factor}) [{time} min]".format(
                item=item["item"],
                factor=item["factor"],
                time=cooking_time_min,
            )

            todoist_helper.add_item_to_project(
                formatted_item,
                project_name,
                due_date_dict=due_dict,
            )

    @staticmethod
    def _check_fixed_menu_number(menu_number: int):
        if menu_number is None:
            raise ValueError("fixed menu number not specified")
        if not isinstance(menu_number, int):
            raise ValueError(f"fixed menu number ({menu_number}) not an int")
        return menu_number

    @staticmethod
    def _edit_item_factor(factor: float) -> float:
        FILE_LOGGER.info("[edit item factor]")
        changed_factor = input(f"new factor (old: {factor}): \n")
        return float(changed_factor)

    def _enrich_with_cooking_time(self, row: pd.Series) -> pd.Series:
        if row["type"] == "recipe":
            recipe = self.recipe_book.get_recipe_by_title(row["item"])
            row["item"] = recipe.title
            row["total_cook_time"] = recipe.total_cook_time
        return row

    def _load_fixed_menu(self, gsheets_helper):
        menu_number = self._check_fixed_menu_number(
            self.config.fixed.menu_number
        )
        menu_file = f"{self.config.fixed.file_prefix}{menu_number}"
        fixed_menu = gsheets_helper.get_sheet_as_df(menu_file, menu_file)
        return fixed_menu

    def _load_local_menu(self):
        file_path = Path(ABS_FILE_PATH, self.config.local.file_path)
        self.dataframe = pd.read_csv(file_path, sep=";")

    def _retrieve_manual_menu_ingredient(self, row: pd.Series):
        ingredient = self.ingredient_formatter.format_manual_ingredient(
            quantity=row["factor"], unit=row["unit"], item=row["item"]
        )
        return MenuIngredient(
            ingredient=ingredient, from_recipe="manual", from_day=row["weekday"]
        )

    def _retrieve_manual_menu_ingredient_list(self, df: pd.DataFrame):
        return [
            self._retrieve_manual_menu_ingredient(row)
            for _, row in df.iterrows()
        ]

    def _retrieve_menu_recipe(self, row: pd.Series) -> MenuRecipe:
        recipe = self.recipe_book.get_recipe_by_title(row["item"])
        return MenuRecipe(
            recipe=recipe,
            factor=row["factor"],
            from_day=row["weekday"],
            from_recipe=row["item"],
        )

    def _retrieve_menu_recipe_list(self, df: pd.DataFrame) -> List[MenuRecipe]:
        return [self._retrieve_menu_recipe(row) for _, row in df.iterrows()]

    def _save_menu(self):
        tmp_menu_file = Path(ABS_FILE_PATH, self.config.local.file_path)
        FILE_LOGGER.info("[save menu]", tmp_menu_file=tmp_menu_file)
        self.dataframe.to_csv(tmp_menu_file, index=False, header=True, sep=";")

    def _validate_menu_with_user(self):
        return (
            self.dataframe.groupby("weekday", sort=False)
            .apply(lambda group: self._validate_menu_by_day_with_user(group))
            .reset_index(drop=True)
        )

    def _validate_menu_by_day_with_user(
        self, group: pd.DataFrame
    ) -> pd.DataFrame:
        tmp_group = group.copy()
        FILE_LOGGER.info("[validate menu]", weekday=group.weekday.unique()[0])
        print(group[["factor", "item"]])

        menu_status = input("menu [g]ood as is, [e]dit, or [d]elete:\n")
        if menu_status == "e":
            tmp_group["factor"] = tmp_group.factor.apply(self._edit_item_factor)
        elif menu_status == "d":
            tmp_group["factor"] = 0
        return tmp_group
