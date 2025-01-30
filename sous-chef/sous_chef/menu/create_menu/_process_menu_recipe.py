from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple, Union

import pandas as pd
from omegaconf import DictConfig
from pandera.typing.common import DataFrameBase
from sous_chef.date.get_due_date import Weekday
from sous_chef.menu.create_menu._select_menu_template import MenuTemplates
from sous_chef.menu.create_menu.exceptions import (
    MenuFutureError,
    MenuQualityError,
)
from sous_chef.menu.create_menu.models import (
    TmpMenuSchema,
    Type,
    YesNo,
    validate_menu_schema,
)
from sous_chef.menu.record_menu_history import MenuHistorian, MenuHistoryError
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from structlog import get_logger

ABS_FILE_PATH = Path(__file__).absolute().parent
FILE_LOGGER = get_logger(__name__)


class MenuRecipeProcessor:
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

    def _get_cook_prep_datetime(
        self, row: pd.Series, recipe: pd.Series
    ) -> Tuple[datetime, datetime]:
        prep_config = self.menu_config.prep_separate

        if row.defrost == YesNo.yes.value:
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

    def _get_entry_with_recipe_columns(
        self, row: pd.Series, recipe: pd.Series
    ) -> DataFrameBase[TmpMenuSchema]:
        cook_datetime, prep_datetime = self._get_cook_prep_datetime(
            row=row, recipe=recipe
        )

        if row.override_check == "N" and row.defrost == "N":
            self._check_menu_quality(
                weekday_index=prep_datetime.weekday(), recipe=recipe
            )

        self._inspect_unrated_recipe(recipe)
        self.processed_uuids.append(recipe.uuid)

        entry_df = pd.DataFrame(
            [
                {
                    **row.to_dict(),
                    "item": recipe.title,
                    "type": Type.recipe.value,
                    "rating": recipe.rating,
                    "time_total": recipe.time_total,
                    "uuid": recipe.uuid,
                    "cook_datetime": cook_datetime,
                    "prep_datetime": prep_datetime,
                }
            ]
        )
        return validate_menu_schema(dataframe=entry_df, model=TmpMenuSchema)

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

    @staticmethod
    def _ensure_rating_exceed_min(recipe: pd.Series, recipe_rating_min: float):
        if not pd.isna(recipe.rating) and (recipe.rating < recipe_rating_min):
            raise MenuQualityError(
                recipe_title=recipe.title,
                error_text=f"rating={recipe.rating} < {recipe_rating_min}",
            )

    @staticmethod
    def _ensure_not_unrated_recipe(recipe: pd.Series, day_type: str):
        if pd.isna(recipe.rating):
            raise MenuQualityError(
                recipe_title=recipe.title,
                error_text=f"(on {day_type}) unrated recipe",
            )

    @staticmethod
    def _ensure_does_not_exceed_max_active_cook_time(
        recipe: pd.Series, max_cook_active_minutes: float, day_type: str
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

        return self._get_entry_with_recipe_columns(row=row, recipe=recipe)

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

        return self._get_entry_with_recipe_columns(row=row, recipe=recipe)

    def set_future_menu_uuids(self, menu_templates: MenuTemplates) -> None:
        future_menus = menu_templates.select_upcoming_menus(
            num_weeks_in_future=self.menu_config.fixed.already_in_future_menus.num_weeks  # noqa: E501
        )
        mask_recipe = future_menus["type"] == Type.recipe.value

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
