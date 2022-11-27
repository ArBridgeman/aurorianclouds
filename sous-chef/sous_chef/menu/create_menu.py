import datetime
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import List, Union

import pandas as pd
import pandera as pa
from omegaconf import DictConfig
from pandera.typing import Series
from pandera.typing.common import DataFrameBase
from sous_chef.date.get_due_date import DueDatetimeFormatter, MealTime, Weekday
from sous_chef.formatter.ingredient.format_ingredient import (
    Ingredient,
    IngredientFormatter,
)
from sous_chef.messaging.gmail_api import GmailHelper
from sous_chef.messaging.gsheets_api import GsheetsHelper
from sous_chef.messaging.todoist_api import TodoistHelper
from sous_chef.recipe_book.read_recipe_book import Recipe, RecipeBook
from structlog import get_logger
from todoist_api_python.models import Task

ABS_FILE_PATH = Path(__file__).absolute().parent
FILE_LOGGER = get_logger(__name__)


# TODO method to scale recipe to desired servings? maybe in recipe checker?


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


class MenuSchema(pa.SchemaModel):
    weekday: Series[str] = pa.Field(isin=Weekday.name_list("capitalize"))
    eat_day: Series[pd.DatetimeTZDtype] = pa.Field(
        dtype_kwargs={"unit": "ns", "tz": "UTC"}, coerce=True
    )
    make_day: Series[pd.DatetimeTZDtype] = pa.Field(
        dtype_kwargs={"unit": "ns", "tz": "UTC"}, coerce=True
    )
    meal_time: Series[str] = pa.Field(isin=MealTime.name_list("lower"))
    type: Series[str] = pa.Field(
        isin=["category", "ingredient", "recipe", "tag"]
    )
    eat_factor: Series[float] = pa.Field(gt=0, nullable=False, coerce=True)
    eat_unit: Series[str] = pa.Field(nullable=True)
    freeze_factor: Series[float] = pa.Field(ge=0, nullable=False, coerce=True)
    defrost: Series[str] = pa.Field(isin=["Y", "N"], nullable=True)
    item: Series[str]

    class Config:
        strict = True


class FinalizedMenuSchema(MenuSchema):
    type: Series[str] = pa.Field(isin=["ingredient", "recipe"])
    total_cook_time: Series[pd.Timedelta] = pa.Field(nullable=True)
    # manual ingredients are not rated
    rating: Series[float] = pa.Field(nullable=True, coerce=True)

    class Config:
        strict = True


@dataclass
class Menu:
    config: DictConfig
    gsheets_helper: GsheetsHelper
    ingredient_formatter: IngredientFormatter
    recipe_book: RecipeBook
    dataframe: Union[
        pd.DataFrame,
        DataFrameBase[MenuSchema],
        DataFrameBase[FinalizedMenuSchema],
    ] = None
    due_date_formatter: DueDatetimeFormatter = field(init=False)
    cook_days: dict = field(init=False)

    def __post_init__(self):
        self.due_date_formatter = DueDatetimeFormatter(self.config.anchor_day)
        self.cook_days = self.config.fixed.cook_days

    def finalize_fixed_menu(self):
        def _get_make_day(row):
            if row.prep_day_before == 0:
                return row.eat_day
            return self.due_date_formatter.replace_time_with_meal_time(
                due_date=row.eat_day - timedelta(days=row.prep_day_before),
                meal_time=self.config.prep_meal_time,
            )

        self.dataframe = self._load_fixed_menu(self.gsheets_helper).reset_index(
            drop=True
        )
        self.dataframe.prep_day_before = self.dataframe.prep_day_before.replace(
            "", "0"
        ).astype(int)
        self.dataframe.freeze_factor = self.dataframe.freeze_factor.replace(
            "", "0"
        )
        self.dataframe.defrost = self.dataframe.defrost.replace(
            "", "N"
        ).str.upper()

        self.dataframe["eat_day"] = self.dataframe.apply(
            lambda row: self.due_date_formatter.get_due_datetime_with_meal_time(
                weekday=row.weekday, meal_time=row.meal_time
            ),
            axis=1,
        )
        self.dataframe["make_day"] = self.dataframe.apply(
            lambda row: _get_make_day(row), axis=1
        )

        self.dataframe.drop(columns=["prep_day_before"], inplace=True)
        self._validate_menu_schema()
        self.dataframe = self.dataframe.apply(self._process_menu, axis=1)
        self._save_menu()

    def get_menu_for_grocery_list(
        self,
    ) -> (List[MenuIngredient], List[MenuRecipe]):
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
        return result_dict["ingredient"], result_dict["recipe"]

    def send_menu_to_gmail(self, gmail_helper: GmailHelper):
        mask_recipe = self.dataframe["type"] == "recipe"
        tmp_df = (
            self.dataframe[mask_recipe][
                ["item", "rating", "weekday", "total_cook_time"]
            ]
            .copy(deep=True)
            .sort_values(by=["rating"])
            .reset_index(drop=True)
        )

        tmp_df.total_cook_time = tmp_df.total_cook_time.apply(
            lambda value: self._get_cooking_time_min(value, default_time=pd.NaT)
        )

        calendar_week = self.due_date_formatter.get_calendar_week()
        subject = f"[sous_chef_menu] week {calendar_week}"
        gmail_helper.send_dataframe_in_email(subject, tmp_df)

    def upload_menu_to_todoist(
        self, todoist_helper: TodoistHelper
    ) -> List[Task]:
        project_name = self.config.todoist.project_name
        if self.config.todoist.remove_existing_task:
            anchor_date = self.due_date_formatter.get_anchor_date()
            [
                todoist_helper.delete_all_items_in_project(
                    project_name,
                    only_delete_after_date=anchor_date,
                )
                for _ in range(3)
            ]

        tasks = []
        project_id = todoist_helper.get_project_id(project_name)

        def _add_task(task_name: str, task_due_date: datetime.datetime):
            task_object = todoist_helper.add_task_to_project(
                task=task_name,
                project=project_name,
                project_id=project_id,
                due_date=task_due_date,
                priority=self.config.todoist.task_priority,
            )
            tasks.append(task_object)

        for _, row in self.dataframe.iterrows():
            task, due_date = self._format_task_and_due_date_list(row)
            _add_task(task_name=task, task_due_date=due_date)
            if row.eat_day != row.make_day:
                _add_task(
                    task_name=f"[PREP] {task}", task_due_date=row.make_day
                )
            if row.defrost == "Y":
                _add_task(
                    task_name=f"[DEFROST] {task}",
                    task_due_date=row.eat_day - timedelta(days=1),
                )
        return tasks

    def load_final_menu(self):
        workbook = self.config.final_menu.workbook
        worksheet = self.config.final_menu.worksheet
        self.dataframe = self.gsheets_helper.get_worksheet(
            workbook_name=workbook, worksheet_name=worksheet
        )
        self.dataframe.total_cook_time = pd.to_timedelta(
            self.dataframe.total_cook_time
        )
        self._validate_finalized_menu_schema()

    @staticmethod
    def _check_fixed_menu_number(menu_number: int):
        if menu_number is None:
            raise ValueError("fixed menu number not specified")
        if not isinstance(menu_number, int):
            raise ValueError(f"fixed menu number ({menu_number}) not an int")

    def _check_manual_ingredient(self, row: pd.Series):
        return self.ingredient_formatter.format_manual_ingredient(
            quantity=float(row["eat_factor"]),
            unit=row["eat_unit"],
            item=row["item"],
        )

    def _add_recipe_cook_time_and_rating(self, row: pd.Series) -> pd.Series:
        recipe = self.recipe_book.get_recipe_by_title(row["item"])
        row["item"] = recipe.title
        row["rating"] = recipe.rating
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

        make_time = row.eat_day
        if row.make_day == row.eat_day:
            make_time -= timedelta(minutes=cooking_time_min)

        return task_str, make_time

    @staticmethod
    def _get_cooking_time_min(
        total_cook_time: timedelta, default_time: int = 20
    ):
        if not isinstance(total_cook_time, timedelta):
            return default_time
        if (cook_time := int(total_cook_time.total_seconds() / 60)) < 0:
            return default_time
        return cook_time

    def _get_cook_day_as_weekday(self, cook_day: str):
        if cook_day in self.cook_days:
            return self.cook_days[cook_day]

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
        menu_basic = gsheets_helper.get_worksheet(
            menu_basic_file, menu_basic_file
        )

        menu_number = self.config.fixed.menu_number
        self._check_fixed_menu_number(menu_number)
        menu_fixed_file = f"{self.config.fixed.file_prefix}{menu_number}"
        menu_fixed = gsheets_helper.get_worksheet(
            menu_fixed_file, menu_fixed_file
        )

        combined_menu = pd.concat([menu_basic, menu_fixed]).sort_values(
            by=["weekday", "meal_time"]
        )
        combined_menu["weekday"] = combined_menu.weekday.apply(
            self._get_cook_day_as_weekday
        )

        # TODO create test for
        mask_skip_none = combined_menu["weekday"].isna()
        FILE_LOGGER.warning(
            "Menu entries ignored",
            skipped_entries=combined_menu[mask_skip_none],
        )
        return combined_menu[~mask_skip_none]

    def _process_menu(self, row: pd.Series):
        # due to schema validation row["type"], may only be 1 of these 4 types
        FILE_LOGGER.info(
            "[process menu]",
            action="processing",
            day=row["weekday"],
            item=row["item"],
            type=row["type"],
        )
        if row["type"] == "ingredient":
            # do NOT need returned as found as is
            self._check_manual_ingredient(row)
            return row
        return self._process_menu_recipe(row)

    def _process_menu_recipe(self, row: pd.Series):
        if row["type"] == "category":
            row = self._select_random_recipe(
                row, "get_random_recipe_by_category"
            )
        elif row["type"] == "tag":
            row = self._select_random_recipe(row, "get_random_recipe_by_tag")
        return self._add_recipe_cook_time_and_rating(row)

    def _retrieve_manual_menu_ingredient(
        self, row: pd.Series
    ) -> MenuIngredient:
        return MenuIngredient(
            ingredient=self._check_manual_ingredient(row),
            from_recipe="manual",
            for_day=row["make_day"],
        )

    def _retrieve_menu_recipe(self, row: pd.Series) -> MenuRecipe:
        recipe = self.recipe_book.get_recipe_by_title(row["item"])
        return MenuRecipe(
            recipe=recipe,
            eat_factor=row["eat_factor"],
            freeze_factor=row["freeze_factor"],
            for_day=row["make_day"],
            from_recipe=row["item"],
        )

    def _select_random_recipe(self, row: pd.Series, method: str):
        recipe = getattr(self.recipe_book, method)(row["item"])
        row["item"] = recipe.title
        row["type"] = "recipe"
        return row

    def _save_menu(self):
        workbook = self.config.final_menu.workbook
        worksheet = self.config.final_menu.worksheet
        FILE_LOGGER.info("[save menu]", workbook=workbook, worksheet=worksheet)
        self._validate_finalized_menu_schema()
        self.gsheets_helper.write_worksheet(
            df=self.dataframe,
            workbook_name=workbook,
            worksheet_name=worksheet,
        )

    def _validate_menu_schema(self):
        self.dataframe = MenuSchema.validate(self.dataframe)

    def _validate_finalized_menu_schema(self):
        self.dataframe = FinalizedMenuSchema.validate(self.dataframe)
