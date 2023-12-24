import datetime
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import List, Optional, Tuple, Union

import pandas as pd
import pandera as pa
from omegaconf import DictConfig
from pandera.typing import Series
from pandera.typing.common import DataFrameBase
from sous_chef.abstract.extended_enum import (
    ExtendedEnum,
    ExtendedIntEnum,
    extend_enum,
)
from sous_chef.abstract.handle_exception import BaseWithExceptionHandling
from sous_chef.date.get_due_date import DueDatetimeFormatter, MealTime, Weekday
from sous_chef.formatter.ingredient.format_ingredient import (
    IngredientFormatter,
    MapIngredientErrorToException,
)
from sous_chef.formatter.ingredient.format_line_abstract import (
    MapLineErrorToException,
)
from sous_chef.menu.record_menu_history import (
    MapMenuHistoryErrorToException,
    MenuHistorian,
    MenuHistoryError,
)
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from sous_chef.recipe_book.recipe_util import MapRecipeErrorToException
from structlog import get_logger

from utilities.api.gsheets_api import GsheetsHelper

ABS_FILE_PATH = Path(__file__).absolute().parent
FILE_LOGGER = get_logger(__name__)


class TypeProcessOrder(ExtendedIntEnum):
    recipe = 0
    ingredient = 1
    filter = 2
    tag = 3
    category = 4


class RandomSelectType(ExtendedEnum):
    rated = "rated"
    unrated = "unrated"
    either = "either"


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
class MenuConfigError(Exception):
    custom_message: str
    message: str = "[menu config error]"

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


@dataclass
class MenuFutureError(Exception):
    error_text: str
    recipe_title: str
    message: str = "[future menu]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        return (
            f"{self.message} recipe={self.recipe_title} error={self.error_text}"
        )


@extend_enum(
    [
        MapMenuHistoryErrorToException,
        MapIngredientErrorToException,
        MapLineErrorToException,
        MapRecipeErrorToException,
    ]
)
class MapMenuErrorToException(ExtendedEnum):
    menu_quality_check = MenuQualityError


class BasicMenuSchema(pa.SchemaModel):
    # TODO replace all panderas with pydantic & create own validator with
    #  dataframe returned, as no default functions & coerce is poorly made
    weekday: Series[str] = pa.Field(isin=Weekday.name_list("capitalize"))
    meal_time: Series[str] = pa.Field(isin=MealTime.name_list("lower"))
    type: Series[str] = pa.Field(isin=TypeProcessOrder.name_list())
    eat_factor: Series[float] = pa.Field(
        ge=0, default=0, nullable=False, coerce=True
    )
    eat_unit: Series[str] = pa.Field(nullable=True)
    freeze_factor: Series[float] = pa.Field(
        ge=0, default=0, nullable=False, coerce=True
    )
    defrost: Series[str] = pa.Field(
        isin=["Y", "N"], default="N", nullable=False, coerce=True
    )
    item: Series[str]

    class Config:
        strict = True
        coerce = True


class InProgressSchema(BasicMenuSchema):
    selection: Series[str] = pa.Field(
        isin=RandomSelectType.name_list(), nullable=True
    )
    prep_day: Optional[Series[float]] = pa.Field(
        ge=0, lt=7, default=0, nullable=False, coerce=True
    )
    override_check: Series[str] = pa.Field(
        isin=["Y", "N"], default="N", nullable=False, coerce=True
    )


class AllMenuSchemas(InProgressSchema):
    menu: Series[int] = pa.Field(ge=0, nullable=False)


class LoadedMenuSchema(InProgressSchema):
    cook_datetime: Optional[Series[pd.DatetimeTZDtype]] = pa.Field(
        dtype_kwargs={"unit": "ns", "tz": "UTC"}, coerce=True
    )
    prep_datetime: Series[pd.DatetimeTZDtype] = pa.Field(
        dtype_kwargs={"unit": "ns", "tz": "UTC"}, coerce=True, nullable=False
    )


class TmpMenuSchema(BasicMenuSchema):
    cook_datetime: Optional[Series[pd.DatetimeTZDtype]] = pa.Field(
        dtype_kwargs={"unit": "ns", "tz": "UTC"}, coerce=True
    )
    prep_datetime: Series[pd.DatetimeTZDtype] = pa.Field(
        dtype_kwargs={"unit": "ns", "tz": "UTC"}, coerce=True, nullable=False
    )
    # override as should be replaced with one of these
    type: Series[str] = pa.Field(isin=["ingredient", "recipe"])
    time_total: Series[pd.Timedelta] = pa.Field(nullable=False, coerce=True)
    cook_datetime: Series[pd.DatetimeTZDtype] = pa.Field(
        dtype_kwargs={"unit": "ns", "tz": "UTC"}, coerce=True, nullable=False
    )
    # manual ingredients lack these
    rating: Series[float] = pa.Field(nullable=True, coerce=True)
    uuid: Series[str] = pa.Field(nullable=True)

    class Config:
        strict = True
        coerce = True


@dataclass
class MenuBasic(BaseWithExceptionHandling):
    config: DictConfig
    due_date_formatter: DueDatetimeFormatter
    gsheets_helper: GsheetsHelper
    ingredient_formatter: IngredientFormatter
    recipe_book: RecipeBook
    menu_historian: MenuHistorian = None
    dataframe: Union[
        pd.DataFrame,
        DataFrameBase[BasicMenuSchema],
        DataFrameBase[TmpMenuSchema],
    ] = None
    menu_history_uuid_list: List = field(init=False)
    number_of_unrated_recipes: int = 0
    min_random_recipe_rating: int = None

    def __post_init__(self):
        self.set_tuple_log_and_skip_exception_from_config(
            config_errors=self.config.errors,
            exception_mapper=MapMenuErrorToException,
        )
        self.menu_history_uuid_list = self._set_menu_history_uuid_list()

    def load_final_menu(self):
        workbook = self.config.final_menu.workbook
        worksheet = self.config.final_menu.worksheet
        self.dataframe = self.gsheets_helper.get_worksheet(
            workbook_name=workbook, worksheet_name=worksheet
        )
        self.dataframe.time_total = pd.to_timedelta(self.dataframe.time_total)
        self.dataframe = validate_menu_schema(
            dataframe=self.dataframe, model=TmpMenuSchema
        )

    def save_with_menu_historian(self):
        self.menu_historian.add_current_menu_to_history(self.dataframe)

    def _add_recipe_columns(
        self, row: pd.Series, recipe: pd.Series
    ) -> pd.Series:
        prep_config = self.config.prep_separate

        def _cook_prep_datetime() -> (datetime.timedelta, datetime.timedelta):
            if row.defrost == "Y":
                return row.cook_datetime, row.cook_datetime

            default_cook_datetime = row.cook_datetime - recipe.time_total
            default_prep_datetime = default_cook_datetime

            if (
                recipe.time_inactive is not pd.NaT
                and recipe.time_inactive
                >= timedelta(minutes=int(prep_config.min_inactive_minutes))
            ):
                # inactive too great, so separately schedule prep
                default_cook_datetime += recipe.time_inactive

            if row.prep_day == 0:
                return default_cook_datetime, default_prep_datetime
            # prep_day was set, so use prep_config default time; unsure
            # how cook time altered, but assume large inactive times handled
            return default_cook_datetime, row.prep_datetime

        row["item"] = recipe.title
        row["rating"] = recipe.rating
        row["time_total"] = recipe.time_total
        row["uuid"] = recipe.uuid
        row["cook_datetime"], row["prep_datetime"] = _cook_prep_datetime()

        if row.override_check == "N":
            self._check_menu_quality(
                weekday=row.prep_datetime.weekday(), recipe=recipe
            )

        self._inspect_unrated_recipe(recipe)
        return row

    @BaseWithExceptionHandling.ExceptionHandler.handle_exception
    def _check_manual_ingredient(self, row: pd.Series):
        return self.ingredient_formatter.format_manual_ingredient(
            quantity=float(row["eat_factor"]),
            unit=row["eat_unit"],
            item=row["item"],
        )

    def _check_menu_quality(self, weekday: int, recipe: pd.Series):
        quality_check_config = self.config.quality_check

        self._ensure_rating_exceed_min(
            recipe=recipe,
            recipe_rating_min=float(quality_check_config.recipe_rating_min),
        )

        day_type = "workday"
        if weekday >= 5:
            day_type = "weekend"

        if not quality_check_config[day_type].recipe_unrated_allowed:
            self._ensure_not_unrated_recipe(recipe=recipe, day_type=day_type)
        self._ensure_does_not_exceed_max_active_cook_time(
            recipe=recipe,
            max_cook_active_minutes=float(
                quality_check_config[day_type].cook_active_minutes_max
            ),
            day_type=day_type,
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
    def _ensure_not_unrated_recipe(self, recipe: pd.Series, day_type: str):
        if pd.isna(recipe.rating):
            raise MenuQualityError(
                recipe_title=recipe.title,
                error_text=f"(on {day_type}) unrated recipe",
            )

    @BaseWithExceptionHandling.ExceptionHandler.handle_exception
    def _ensure_does_not_exceed_max_active_cook_time(
        self, recipe: pd.Series, max_cook_active_minutes: float, day_type: str
    ):
        time_total = recipe.time_total
        if recipe.time_inactive is not pd.NaT:
            time_total -= recipe.time_inactive
        cook_active_minutes = time_total.total_seconds() / 60
        if cook_active_minutes > max_cook_active_minutes:
            error_text = (
                f"(on {day_type}) "
                f"cook_active_minutes={cook_active_minutes} > "
                f"{max_cook_active_minutes}"
            )
            raise MenuQualityError(
                recipe_title=recipe.title, error_text=error_text
            )

    def _inspect_unrated_recipe(self, recipe: pd.Series):
        if pd.isna(recipe.rating):
            self.number_of_unrated_recipes += 1
            # TODO unneeded if in UI
            if self.config.run_mode.with_inspect_unrated_recipe:
                FILE_LOGGER.warning(
                    "[unrated recipe]",
                    action="print out ingredients",
                    recipe_title=recipe.title,
                )
                print(recipe.ingredients)

        if (
            self.number_of_unrated_recipes
            == self.config.max_number_of_unrated_recipes
            and self.min_random_recipe_rating is None
        ):
            FILE_LOGGER.warning(
                "[max number of unrated recipes reached]",
                action="will limit to rated recipes for further randomization",
            )
            self.min_random_recipe_rating = (
                self.config.quality_check.recipe_rating_min
            )

    @BaseWithExceptionHandling.ExceptionHandler.handle_exception
    def _retrieve_recipe(
        self,
        row: pd.Series,
        processed_uuid_list: List,
        future_uuid_tuple: Optional[Tuple] = (),
    ) -> DataFrameBase[TmpMenuSchema]:
        recipe = self.recipe_book.get_recipe_by_title(row["item"])
        if row.override_check == "N":
            if recipe.uuid in processed_uuid_list:
                raise MenuQualityError(
                    recipe_title=recipe.title,
                    error_text="recipe already processed in menu",
                )
            elif recipe.uuid in self.menu_history_uuid_list:
                raise MenuHistoryError(recipe_title=recipe.title)
            elif recipe.uuid in future_uuid_tuple:
                raise MenuFutureError(
                    recipe_title=recipe.title,
                    error_text="recipe is in an upcoming menu",
                )
        row = self._add_recipe_columns(row=row, recipe=recipe)
        return validate_menu_schema(dataframe=row, model=TmpMenuSchema)

    @BaseWithExceptionHandling.ExceptionHandler.handle_exception
    def _select_random_recipe(
        self,
        row: pd.Series,
        entry_type: str,
        processed_uuid_list: List,
        future_uuid_tuple: Optional[Tuple],
    ) -> DataFrameBase[TmpMenuSchema]:
        max_cook_active_minutes = None
        if row.override_check == "N":
            if row.prep_datetime.weekday() < 5:
                max_cook_active_minutes = float(
                    self.config.quality_check.workday.cook_active_minutes_max
                )
            elif row.prep_datetime.weekday() >= 5:
                max_cook_active_minutes = float(
                    self.config.quality_check.weekend.cook_active_minutes_max
                )

        exclude_uuid_list = self.menu_history_uuid_list
        if processed_uuid_list:
            exclude_uuid_list += processed_uuid_list + list(future_uuid_tuple)

        recipe = getattr(
            self.recipe_book, f"get_random_recipe_by_{entry_type}"
        )(
            row["item"],
            selection_type=row["selection"],
            exclude_uuid_list=exclude_uuid_list,
            max_cook_active_minutes=max_cook_active_minutes,
            min_rating=self.min_random_recipe_rating,
        )
        row["item"] = recipe.title
        row["type"] = "recipe"
        row = self._add_recipe_columns(row=row, recipe=recipe)
        return validate_menu_schema(dataframe=row, model=TmpMenuSchema)

    def _save_menu(self):
        save_loc = self.config.final_menu
        FILE_LOGGER.info(
            "[save menu]",
            workbook=save_loc.workbook,
            worksheet=save_loc.worksheet,
        )
        self.dataframe = validate_menu_schema(
            dataframe=self.dataframe, model=TmpMenuSchema
        )
        self.gsheets_helper.write_worksheet(
            df=self.dataframe.sort_values(by=["cook_datetime"]).reindex(
                sorted(self.dataframe.columns), axis=1
            ),
            workbook_name=save_loc.workbook,
            worksheet_name=save_loc.worksheet,
        )

    def _set_menu_history_uuid_list(self) -> List:
        if self.menu_historian is not None:
            menu_history_recent_df = self.menu_historian.get_history_from(
                days_ago=self.config.menu_history_recent_days
            )
            if not menu_history_recent_df.empty:
                return list(menu_history_recent_df.uuid.values)
        return []


def validate_menu_schema(
    dataframe: Union[pd.Series, pd.DataFrame], model
) -> Union[DataFrameBase, pd.Series]:
    def validate_schema(tmp_df: pd.DataFrame):
        selected_cols = model._collect_fields().keys()
        return model.validate(tmp_df[selected_cols].copy())

    if isinstance(dataframe, pd.DataFrame):
        return validate_schema(tmp_df=dataframe)
    elif isinstance(dataframe, pd.Series):
        tmp_df = validate_schema(tmp_df=dataframe.to_frame().T)
        return tmp_df.squeeze()


def get_weekday_from_short(short_week_day: str):
    # TODO move to config
    day_mapping = {
        "mon": "Monday",
        "tue": "Tuesday",
        "tues": "Tuesday",
        "wed": "Wednesday",
        "thu": "Thursday",
        "fri": "Friday",
        "sat": "Saturday",
        "sun": "Sunday",
    }
    if short_week_day.lower() in day_mapping:
        return day_mapping[short_week_day.lower()]
    raise MenuConfigError(f"{short_week_day} unknown weekday!")
