import datetime
from datetime import timedelta
from pathlib import Path
from typing import Union

import pandas as pd
from omegaconf import DictConfig
from pandera.typing.common import DataFrameBase
from sous_chef.abstract.handle_exception import BaseWithExceptionHandling
from sous_chef.date.get_due_date import Weekday
from sous_chef.formatter.ingredient.format_ingredient import (
    MapIngredientErrorToException,
)
from sous_chef.formatter.ingredient.format_line_abstract import (
    MapLineErrorToException,
)
from sous_chef.menu.create_menu._select_menu_template import MenuTemplates
from sous_chef.menu.create_menu.exceptions import (
    MenuFutureError,
    MenuQualityError,
)
from sous_chef.menu.create_menu.models import (
    TmpMenuSchema,
    validate_menu_schema,
)
from sous_chef.menu.record_menu_history import (
    MapMenuHistoryErrorToException,
    MenuHistorian,
    MenuHistoryError,
)
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from sous_chef.recipe_book.recipe_util import MapRecipeErrorToException
from structlog import get_logger

from utilities.extended_enum import ExtendedEnum, extend_enum

ABS_FILE_PATH = Path(__file__).absolute().parent
FILE_LOGGER = get_logger(__name__)


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
    menu_future_error = MenuFutureError


class MenuRecipeProcessor(BaseWithExceptionHandling):
    def __init__(
        self,
        menu_config: DictConfig,
        recipe_book: RecipeBook,
    ):
        self.menu_config = menu_config
        self.recipe_book = recipe_book

        self.menu_history_uuids = ()
        self.future_menu_uuids = ()
        self.processed_uuids = []

        self.number_of_unrated_recipes: int = 0
        self.min_random_recipe_rating: Union[int, None] = None

        self.set_tuple_log_and_skip_exception_from_config(
            config_errors=self.menu_config.errors,
            exception_mapper=MapMenuErrorToException,
        )

    def _add_recipe_columns(
        self, row: pd.Series, recipe: pd.Series
    ) -> pd.Series:
        prep_config = self.menu_config.prep_separate

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

        if row.override_check == "N" and row.defrost == "N":
            self._check_menu_quality(
                weekday_index=row.prep_datetime.weekday(), recipe=recipe
            )

        self._inspect_unrated_recipe(recipe)
        return row

    def _check_menu_quality(self, weekday_index: int, recipe: pd.Series):
        quality_check_config = self.menu_config.quality_check

        self._ensure_rating_exceed_min(
            recipe=recipe,
            recipe_rating_min=float(quality_check_config.recipe_rating_min),
        )

        day_type = "workday"
        if isinstance(weekday_index, int):
            day_type = Weekday.get_by_index(index=weekday_index).day_type
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

        if (
            cook_active_minutes := time_total.total_seconds() / 60
        ) > max_cook_active_minutes:
            raise MenuQualityError(
                recipe_title=recipe.title,
                error_text=(
                    f"(on {day_type}) "
                    f"cook_active_minutes={cook_active_minutes} > "
                    f"{max_cook_active_minutes}"
                ),
            )

    def _inspect_unrated_recipe(self, recipe: pd.Series):
        if pd.isna(recipe.rating):
            self.number_of_unrated_recipes += 1
            if self.menu_config.run_mode.with_inspect_unrated_recipe:
                FILE_LOGGER.warning(
                    "[unrated recipe]",
                    action="print out ingredients",
                    recipe_title=recipe.title,
                )
                print(recipe.ingredients)

        if (
            self.number_of_unrated_recipes
            == self.menu_config.max_number_of_unrated_recipes
            and self.min_random_recipe_rating is None
        ):
            FILE_LOGGER.warning(
                "[max number of unrated recipes reached]",
                action="will limit to rated recipes for further randomization",
            )
            self.min_random_recipe_rating = (
                self.menu_config.quality_check.recipe_rating_min
            )

    @BaseWithExceptionHandling.ExceptionHandler.handle_exception
    def retrieve_recipe(self, row: pd.Series) -> DataFrameBase[TmpMenuSchema]:
        recipe = self.recipe_book.get_recipe_by_title(row["item"])
        if row.override_check == "N":
            if recipe.uuid in self.processed_uuids:
                raise MenuQualityError(
                    recipe_title=recipe.title,
                    error_text="recipe already processed in menu",
                )
            if recipe.uuid in self.menu_history_uuids:
                raise MenuHistoryError(recipe_title=recipe.title)
            if recipe.uuid in self.future_menu_uuids:
                raise MenuFutureError(
                    recipe_title=recipe.title,
                    error_text="recipe is in an upcoming menu",
                )
        row = self._add_recipe_columns(row=row, recipe=recipe)
        self.processed_uuids.append(recipe.uuid)
        return validate_menu_schema(dataframe=row, model=TmpMenuSchema)

    @BaseWithExceptionHandling.ExceptionHandler.handle_exception
    def select_random_recipe(
        self,
        row: pd.Series,
        entry_type: str,
    ) -> DataFrameBase[TmpMenuSchema]:
        max_cook_active_minutes = None
        if row.override_check == "N":
            weekday = Weekday.get_by_index(row.prep_datetime.weekday())
            max_cook_active_minutes = float(
                self.menu_config.quality_check[
                    weekday.day_type
                ].cook_active_minutes_max
            )

        exclude_uuid_list = (
            list(self.menu_history_uuids)
            + self.processed_uuids
            + list(self.future_menu_uuids)
        )

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
        self.processed_uuids.append(recipe.uuid)
        return validate_menu_schema(dataframe=row, model=TmpMenuSchema)

    def set_future_menu_uuids(self, menu_templates: MenuTemplates) -> None:
        future_menus = menu_templates.select_upcoming_menus(
            num_weeks_in_future=self.menu_config.fixed.already_in_future_menus.num_weeks  # noqa: E501
        )
        mask_recipe = future_menus["type"] == "recipe"

        if sum(mask_recipe) > 0:
            self.future_menu_uuids = tuple(
                self.recipe_book.get_recipe_by_title(recipe).uuid
                for recipe in future_menus[mask_recipe]["item"].values
            )

    def set_menu_history_uuids(self, menu_historian: MenuHistorian) -> None:
        menu_history_recent_df = menu_historian.get_history_from(
            days_ago=self.menu_config.menu_history_recent_days
        )
        if not menu_history_recent_df.empty:
            self.menu_history_uuids = tuple(menu_history_recent_df.uuid.values)
