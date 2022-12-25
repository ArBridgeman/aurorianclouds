import datetime
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import List, Optional, Union

import pandas as pd
import pandera as pa
from omegaconf import DictConfig
from pandera.typing import Series
from pandera.typing.common import DataFrameBase
from sous_chef.abstract.extended_enum import ExtendedEnum, extend_enum
from sous_chef.abstract.handle_exception import BaseWithExceptionHandling
from sous_chef.date.get_due_date import DueDatetimeFormatter, MealTime, Weekday
from sous_chef.formatter.ingredient.format_ingredient import (
    Ingredient,
    IngredientFormatter,
    MapIngredientErrorToException,
)
from sous_chef.formatter.ingredient.format_line_abstract import (
    MapLineErrorToException,
)
from sous_chef.messaging.gmail_api import GmailHelper
from sous_chef.messaging.gsheets_api import GsheetsHelper
from sous_chef.messaging.todoist_api import TodoistHelper
from sous_chef.recipe_book.read_recipe_book import (
    MapRecipeErrorToException,
    Recipe,
    RecipeBook,
)
from structlog import get_logger
from termcolor import cprint
from todoist_api_python.models import Task

ABS_FILE_PATH = Path(__file__).absolute().parent
FILE_LOGGER = get_logger(__name__)


# TODO method to scale recipe to desired servings? maybe in recipe checker?
@dataclass
class MenuIncompleteError(Exception):
    custom_message: str
    message: str = "[menu had errors]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message} {self.custom_message}"


@dataclass
class MenuQualityError(Exception):
    error_text: str
    recipe_title: str
    message: str = "[menu quality]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        return (
            f"{self.message} recipe={self.recipe_title} error={self.error_text}"
        )


@extend_enum(
    [
        MapIngredientErrorToException,
        MapLineErrorToException,
        MapRecipeErrorToException,
    ]
)
class MapMenuErrorToException(ExtendedEnum):
    menu_quality_check = MenuQualityError


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
    prep_day_before: Optional[Series[float]] = pa.Field(
        ge=0, lt=7, nullable=False, coerce=True
    )
    eat_datetime: Optional[Series[pd.DatetimeTZDtype]] = pa.Field(
        dtype_kwargs={"unit": "ns", "tz": "UTC"}, coerce=True
    )
    meal_time: Series[str] = pa.Field(isin=MealTime.name_list("lower"))
    type: Series[str] = pa.Field(
        isin=["category", "ingredient", "recipe", "tag"]
    )
    eat_factor: Series[float] = pa.Field(gt=0, nullable=False, coerce=True)
    eat_unit: Series[str] = pa.Field(nullable=True)
    freeze_factor: Series[float] = pa.Field(ge=0, nullable=False, coerce=True)
    defrost: Series[str] = pa.Field(
        isin=["Y", "N"], nullable=False, coerce=True
    )
    override_check: Optional[Series[str]] = pa.Field(
        isin=["Y", "N"], nullable=False, coerce=True
    )
    item: Series[str]

    class Config:
        strict = True


class FinalizedMenuSchema(MenuSchema):
    # override as should be replaced with one of these
    type: Series[str] = pa.Field(isin=["ingredient", "recipe"])
    time_total: Series[pd.Timedelta] = pa.Field(nullable=False)
    cook_datetime: Series[pd.DatetimeTZDtype] = pa.Field(
        dtype_kwargs={"unit": "ns", "tz": "UTC"}, coerce=True, nullable=False
    )
    prep_datetime: Series[pd.DatetimeTZDtype] = pa.Field(
        dtype_kwargs={"unit": "ns", "tz": "UTC"}, coerce=True, nullable=False
    )
    # manual ingredients lack these
    rating: Series[float] = pa.Field(nullable=True, coerce=True)
    uuid: Series[str] = pa.Field(nullable=True)

    class Config:
        strict = True


@dataclass
class Menu(BaseWithExceptionHandling):
    config: DictConfig
    due_date_formatter: DueDatetimeFormatter
    gsheets_helper: GsheetsHelper
    ingredient_formatter: IngredientFormatter
    recipe_book: RecipeBook
    dataframe: Union[
        pd.DataFrame,
        DataFrameBase[MenuSchema],
        DataFrameBase[FinalizedMenuSchema],
    ] = None
    cook_days: dict = field(init=False)

    def __post_init__(self):
        self.cook_days = self.config.fixed.cook_days
        self.set_tuple_log_and_skip_exception_from_config(
            config_errors=self.config.errors,
            exception_mapper=MapMenuErrorToException,
        )

    def finalize_fixed_menu(self):
        self.record_exception = []

        self.dataframe = self._load_fixed_menu().reset_index(drop=True)

        # remove menu entries that are inactive and drop column
        mask_inactive = self.dataframe.inactive.str.upper() == "Y"
        self.dataframe = self.dataframe.loc[~mask_inactive].drop(
            columns=["inactive"]
        )

        # applied schema model coerces int already
        self.dataframe.freeze_factor.replace("", "0", inplace=True)
        self.dataframe.prep_day_before.replace("", "0", inplace=True)
        self.dataframe.defrost = self.dataframe.defrost.replace(
            "", "N"
        ).str.upper()
        if "override_check" in self.dataframe.columns:
            self.dataframe.override_check = (
                self.dataframe.override_check.fillna("")
                .replace("", "N")
                .str.upper()
            )

        self.dataframe["eat_datetime"] = self.dataframe.apply(
            lambda row: self.due_date_formatter.get_due_datetime_with_meal_time(
                weekday=row.weekday, meal_time=row.meal_time
            ),
            axis=1,
        )

        # validate schema & process menu
        self._validate_menu_schema()
        self.dataframe = self.dataframe.apply(self._process_menu, axis=1)

        if len(self.record_exception) > 0:
            cprint("\t" + "\n\t".join(self.record_exception), "green")
            raise MenuIncompleteError(
                custom_message="will not send to finalize until fixed"
            )

        columns_to_drop = ["eat_datetime", "prep_day_before"]
        if "override_check" in self.dataframe.columns:
            columns_to_drop += ["override_check"]
        self.dataframe.drop(columns=columns_to_drop, inplace=True)
        self._save_menu()

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

    def send_menu_to_gmail(self, gmail_helper: GmailHelper):
        mask_recipe = self.dataframe["type"] == "recipe"
        tmp_df = (
            self.dataframe[mask_recipe][
                ["item", "rating", "weekday", "time_total"]
            ]
            .copy(deep=True)
            .sort_values(by=["rating"])
            .reset_index(drop=True)
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
            todoist_helper.delete_all_items_in_project(
                project_name,
                only_delete_after_date=anchor_date,
            )

        tasks = []
        project_id = todoist_helper.get_project_id(project_name)

        def _add_task(
            task_name: str,
            task_due_date: Union[datetime.date, datetime.datetime] = None,
            parent_id: str = None,
        ):
            task_object = todoist_helper.add_task_to_project(
                task=task_name,
                project=project_name,
                project_id=project_id,
                due_date=task_due_date,
                priority=self.config.todoist.task_priority,
                parent_id=parent_id,
            )
            tasks.append(task_object)
            return task_object

        calendar_week = self.due_date_formatter.get_calendar_week()
        edit_task = _add_task(
            task_name=f"edit recipes from week #{calendar_week}",
            task_due_date=self.due_date_formatter.get_anchor_date()
            + timedelta(days=7),
        )

        for _, row in self.dataframe.iterrows():
            task = self._format_task_name(row)
            # task for when to cook
            _add_task(task_name=task, task_due_date=row.cook_datetime)

            # task reminder to edit recipes
            if row["type"] == "recipe":
                _add_task(task_name=row["item"], parent_id=edit_task.id)

            # task for separate preparation
            if row.cook_datetime != row.prep_datetime:
                _add_task(
                    task_name=f"[PREP] {task}", task_due_date=row.prep_datetime
                )
            if row.defrost == "Y":
                _add_task(
                    task_name=f"[DEFROST] {task}",
                    task_due_date=row.cook_datetime - timedelta(days=1),
                )
        return tasks

    def load_final_menu(self) -> pd.DataFrame:
        workbook = self.config.final_menu.workbook
        worksheet = self.config.final_menu.worksheet
        self.dataframe = self.gsheets_helper.get_worksheet(
            workbook_name=workbook, worksheet_name=worksheet
        )
        self.dataframe.time_total = pd.to_timedelta(self.dataframe.time_total)
        self._validate_finalized_menu_schema()
        return self.dataframe

    @staticmethod
    def _check_fixed_menu_number(menu_number: int):
        if menu_number is None:
            raise ValueError("fixed menu number not specified")
        if not isinstance(menu_number, int):
            raise ValueError(f"fixed menu number ({menu_number}) not an int")

    @BaseWithExceptionHandling.ExceptionHandler.handle_exception
    def _check_manual_ingredient(self, row: pd.Series):
        return self.ingredient_formatter.format_manual_ingredient(
            quantity=float(row["eat_factor"]),
            unit=row["eat_unit"],
            item=row["item"],
        )

    def _add_recipe_columns(
        self, row: pd.Series, recipe: pd.Series
    ) -> pd.Series:
        prep_config = self.config.prep_separate

        def _eat_prep_datetime() -> (datetime.timedelta, datetime.timedelta):
            default_cook_datetime = row.eat_datetime - recipe.time_total
            default_prep_datetime = default_cook_datetime

            if (
                recipe.time_inactive is not pd.NaT
                and recipe.time_inactive
                >= timedelta(minutes=int(prep_config.min_inactive_minutes))
            ):
                # inactive too great, so separately schedule prep
                default_cook_datetime += recipe.time_inactive

            if row.prep_day_before == 0:
                return default_cook_datetime, default_prep_datetime
            # prep_day_before was set, so use prep_config default time; unsure
            # how cook time altered, but assume large inactive times handled
            return (
                default_cook_datetime,
                self.due_date_formatter.replace_time_with_meal_time(
                    due_date=row.eat_datetime
                    - timedelta(days=row.prep_day_before),
                    meal_time=prep_config.default_time,
                ),
            )

        if "override_check" in row.keys() and row.override_check == "N":
            self._check_menu_quality(
                weekday=row.prep_datetime.weekday(), recipe=recipe
            )

        row["item"] = recipe.title
        row["rating"] = recipe.rating
        row["time_total"] = recipe.time_total
        row["uuid"] = recipe.uuid
        row["cook_datetime"], row["prep_datetime"] = _eat_prep_datetime()

        # TODO remove/replace once recipes easily viewable in UI
        self._inspect_unrated_recipe(recipe)
        return row

    def _check_menu_quality(self, weekday: int, recipe: pd.Series):
        quality_check_config = self.config.quality_check

        self._ensure_rating_exceed_min(
            recipe=recipe,
            recipe_rating_min=float(quality_check_config.recipe_rating_min),
        )

        # workday = weekday
        if weekday < 5:
            if not quality_check_config.workday.recipe_unrated_allowed:
                self._ensure_workday_not_unrated_recipe()
            self._ensure_workday_not_exceed_active_cook_time(
                recipe=recipe,
                cook_active_minutes_max=float(
                    quality_check_config.workday.cook_active_minutes_max
                ),
            )

    @BaseWithExceptionHandling.ExceptionHandler.handle_exception
    def _ensure_rating_exceed_min(
        self, recipe: pd.Series, recipe_rating_min: float
    ):
        if not pd.isna(recipe.rating) and (recipe.rating < recipe_rating_min):
            raise MenuQualityError(
                recipe_title=recipe.title,
                error_text=f"rating={recipe.rating} < {recipe_rating_min}",
            )

    @BaseWithExceptionHandling.ExceptionHandler.handle_exception
    def _ensure_workday_not_unrated_recipe(self, recipe: pd.Series):
        if pd.isna(recipe.rating):
            raise MenuQualityError(
                recipe_title=recipe.title,
                error_text="(on workday) unrated recipe",
            )

    @BaseWithExceptionHandling.ExceptionHandler.handle_exception
    def _ensure_workday_not_exceed_active_cook_time(
        self, recipe: pd.Series, cook_active_minutes_max: float
    ):
        time_total = recipe.time_total
        if recipe.time_inactive is not pd.NaT:
            time_total -= recipe.time_inactive
        cook_active_minutes = time_total.total_seconds() / 60
        if cook_active_minutes > cook_active_minutes_max:
            error_text = (
                "(on workday) "
                f"cook_active_minutes={cook_active_minutes} > "
                f"{cook_active_minutes_max}"
            )
            raise MenuQualityError(
                recipe_title=recipe.title, error_text=error_text
            )

    @staticmethod
    def _format_task_name(
        row: pd.Series,
    ) -> (str, datetime.datetime):
        factor_str = f"x eat: {row.eat_factor}"
        if row.freeze_factor > 0:
            factor_str += f", x freeze: {row.freeze_factor}"

        time_total = int(row.time_total.total_seconds() / 60)
        return f"{row['item']} ({factor_str}) [{time_total} min]"

    def _get_cook_day_as_weekday(self, cook_day: str):
        if cook_day in self.cook_days:
            return self.cook_days[cook_day]

    def _inspect_unrated_recipe(self, recipe: pd.Series):
        if self.config.run_mode.with_inspect_unrated_recipe:
            if pd.isna(recipe.rating):
                FILE_LOGGER.warning(
                    "[unrated recipe]",
                    action="print out ingredients",
                    recipe_title=recipe.title,
                )
                print(recipe.ingredients)

    def _load_fixed_menu(self):
        menu_basic_file = self.config.fixed.basic
        menu_basic = self.gsheets_helper.get_worksheet(
            menu_basic_file, menu_basic_file
        )

        menu_number = self.config.fixed.menu_number
        self._check_fixed_menu_number(menu_number)
        menu_fixed_file = f"{self.config.fixed.file_prefix}{menu_number}"
        menu_fixed = self.gsheets_helper.get_worksheet(
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
        if sum(mask_skip_none) > 0:
            FILE_LOGGER.warning(
                "Menu entries ignored",
                skipped_entries=combined_menu[mask_skip_none],
            )
        return combined_menu[~mask_skip_none]

    def _process_menu(self, row: pd.Series):
        FILE_LOGGER.info(
            "[process menu]",
            action="processing",
            day=row["weekday"],
            item=row["item"],
            type=row["type"],
        )
        if row["type"] == "ingredient":
            return self._process_ingredient(row)
        return self._process_menu_recipe(row)

    def _process_ingredient(self, row: pd.Series):
        # do NOT need returned, as just ensuring exists
        self._check_manual_ingredient(row=row)

        row["time_total"] = timedelta(
            minutes=int(self.config.ingredient.default_cook_minutes)
        )

        cook_datetime = row["eat_datetime"] - row["time_total"]
        row["cook_datetime"] = cook_datetime
        row["prep_datetime"] = cook_datetime
        return row

    def _process_menu_recipe(self, row: pd.Series):
        if row["type"] == "category":
            return self._select_random_recipe(
                row, "get_random_recipe_by_category"
            )
        elif row["type"] == "tag":
            return self._select_random_recipe(row, "get_random_recipe_by_tag")
        return self._retrieve_recipe(row)

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
    def _retrieve_recipe(self, row: pd.Series):
        recipe = self.recipe_book.get_recipe_by_title(row["item"])
        return self._add_recipe_columns(row=row, recipe=recipe)

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

    @BaseWithExceptionHandling.ExceptionHandler.handle_exception
    def _select_random_recipe(self, row: pd.Series, method: str):
        recipe = getattr(self.recipe_book, method)(row["item"])
        row["item"] = recipe.title
        row["type"] = "recipe"
        return self._add_recipe_columns(row=row, recipe=recipe)

    def _save_menu(self):
        save_loc = self.config.final_menu
        FILE_LOGGER.info(
            "[save menu]",
            workbook=save_loc.workbook,
            worksheet=save_loc.worksheet,
        )
        self._validate_finalized_menu_schema()
        self.gsheets_helper.write_worksheet(
            df=self.dataframe.sort_values(by=["cook_datetime"]),
            workbook_name=save_loc.workbook,
            worksheet_name=save_loc.worksheet,
        )

    def _validate_menu_schema(self):
        self.dataframe = MenuSchema.validate(self.dataframe)

    def _validate_finalized_menu_schema(self):
        self.dataframe = FinalizedMenuSchema.validate(self.dataframe)
