from dataclasses import dataclass
from datetime import timedelta
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
from omegaconf import DictConfig
from pandera.typing.common import DataFrameBase
from sous_chef.date.get_due_date import DueDatetimeFormatter
from sous_chef.menu.create_menu._menu_basic import (
    AllMenuSchema,
    BasicMenuSchema,
    LoadedMenuSchema,
    MenuBasic,
    MenuIncompleteError,
    Season,
    TmpMenuSchema,
    get_weekday_from_short,
    validate_menu_schema,
)
from structlog import get_logger
from termcolor import cprint

from utilities.api.gsheets_api import GsheetsHelper
from utilities.extended_enum import ExtendedIntEnum

FILE_LOGGER = get_logger(__name__)


class TypeProcessOrder(ExtendedIntEnum):
    recipe = 0
    ingredient = 1
    filter = 2
    tag = 3
    category = 4


class MenuFromFixedTemplate(MenuBasic):
    def finalize_fixed_menu(self):
        self.record_exception = []

        fixed_templates = FixedTemplates(
            config=self.config.fixed,
            due_date_formatter=self.due_date_formatter,
            gsheets_helper=self.gsheets_helper,
        )
        self.dataframe = fixed_templates.load_fixed_menu()

        # sort by desired order to be processed
        self.dataframe["process_order"] = self.dataframe["type"].apply(
            lambda x: TypeProcessOrder[x].value
        )
        self.dataframe["is_unrated"] = (
            self.dataframe.selection == "unrated"
        ).astype(int)

        self.dataframe = self.dataframe.sort_values(
            by=["is_unrated", "process_order"], ascending=[False, True]
        ).drop(columns=["process_order", "is_unrated"])

        future_uuid_tuple = ()
        if self.config.fixed.already_in_future_menus.active:
            future_uuid_tuple = self._get_future_menu_uuids(
                future_menus=fixed_templates.select_upcoming_menus(
                    num_weeks_in_future=self.config.fixed.already_in_future_menus.num_weeks  # noqa: E501
                )
            )

        holder_dataframe = pd.DataFrame()
        processed_uuid_list = []
        for _, entry in self.dataframe.iterrows():
            processed_entry = self._process_menu(
                row=entry,
                processed_uuid_list=processed_uuid_list,
                future_uuid_tuple=future_uuid_tuple,
            )

            # in cases where error is logged
            if processed_entry is None:
                continue

            if processed_entry["type"] == "recipe":
                processed_uuid_list.append(processed_entry.uuid)

            processed_df = pd.DataFrame([processed_entry])
            holder_dataframe = pd.concat([processed_df, holder_dataframe])
        self.dataframe = holder_dataframe

        if len(self.record_exception) > 0:
            cprint("\t" + "\n\t".join(self.record_exception), "green")
            raise MenuIncompleteError(
                custom_message="will not send to finalize until fixed"
            )
        self._save_menu()

    def _get_future_menu_uuids(
        self, future_menus: DataFrameBase[AllMenuSchema]
    ) -> Tuple:
        FILE_LOGGER.info("[_get_future_menu_uuids]")
        mask_type = future_menus["type"] == "recipe"
        return tuple(
            self.recipe_book.get_recipe_by_title(recipe).uuid
            for recipe in future_menus[mask_type]["item"].values
        )

    def _process_menu(
        self,
        row: pd.Series,
        processed_uuid_list: List,
        future_uuid_tuple: Optional[Tuple] = (),
    ) -> DataFrameBase[TmpMenuSchema]:
        FILE_LOGGER.info(
            "[process menu]",
            action="processing",
            day=row["weekday"],
            item=row["item"],
            type=row["type"],
        )
        tmp_row = row.copy(deep=True)
        if row["type"] == "ingredient":
            return self._process_ingredient(tmp_row)
        return self._process_menu_recipe(
            tmp_row,
            processed_uuid_list=processed_uuid_list,
            future_uuid_tuple=future_uuid_tuple,
        )

    def _process_ingredient(
        self, row: pd.Series
    ) -> DataFrameBase[TmpMenuSchema]:
        # do NOT need returned, as just ensuring exists
        self._check_manual_ingredient(row=row)

        row["time_total"] = timedelta(
            minutes=int(self.config.ingredient.default_cook_minutes)
        )
        row["rating"] = np.NaN
        row["uuid"] = np.NaN
        row["cook_datetime"] = row["cook_datetime"] - row["time_total"]
        row["prep_datetime"] = row["cook_datetime"]
        return validate_menu_schema(dataframe=row, model=TmpMenuSchema)

    def _process_menu_recipe(
        self,
        row: pd.Series,
        processed_uuid_list: List,
        future_uuid_tuple: Optional[Tuple] = (),
    ) -> DataFrameBase[TmpMenuSchema]:
        if row["type"] in ["category", "tag", "filter"]:
            return self._select_random_recipe(
                row=row,
                entry_type=row["type"],
                processed_uuid_list=processed_uuid_list,
                future_uuid_tuple=future_uuid_tuple,
            )
        return self._retrieve_recipe(
            row,
            processed_uuid_list=processed_uuid_list,
            future_uuid_tuple=future_uuid_tuple,
        )


@dataclass
class FixedTemplates:
    config: DictConfig
    due_date_formatter: DueDatetimeFormatter
    gsheets_helper: GsheetsHelper
    all_menus_df: DataFrameBase[AllMenuSchema] = None

    def __post_init__(self):
        self.all_menus_df = self._get_all_fixed_menus()

    def _check_fixed_menu_number(self, menu_number: int):
        if not isinstance(menu_number, int):
            raise ValueError(f"fixed menu number ({menu_number}) not an int")
        elif menu_number not in self.all_menus_df.menu.values:
            raise ValueError(f"fixed menu number ({menu_number}) is not found")

    @staticmethod
    def _check_season(season: str):
        if season not in Season.value_list():
            raise ValueError(f"season ({season}) not in {Season.value_list()}")

    @staticmethod
    def _convert_fixed_menu_to_all_menu_schemas(
        all_menus: pd.DataFrame,
    ) -> DataFrameBase[AllMenuSchema]:
        # need already converted to default for "prep_datetime" calculation
        all_menus["prep_day"] = all_menus.prep_day.replace("", 0)

        # pandera does not support replacing "" with default values, only NAs
        nan_columns = [
            "selection",
            "freeze_factor",
            "defrost",
            "override_check",
        ]
        all_menus[nan_columns] = all_menus[nan_columns].replace("", np.NaN)

        # unravel short form for weekday values
        all_menus["weekday"] = (
            all_menus.day.str.split("_").str[1].apply(get_weekday_from_short)
        )
        return (
            validate_menu_schema(dataframe=all_menus, model=AllMenuSchema)
            .sort_values(by=["weekday", "meal_time"])
            .reset_index(drop=True)
        )

    def _get_all_fixed_menus(self) -> DataFrameBase[AllMenuSchema]:
        FILE_LOGGER.info("[_get_all_fixed_menus]")
        # TODO move to config
        sheet_to_mealtime = {
            "breakfast": "breakfast",
            "snack": "snack",
            "dinner": "dinner",
            "dessert": "dessert",
        }
        all_menus = pd.DataFrame()
        workbook = self.gsheets_helper.get_workbook(
            workbook_name=self.config.workbook
        )
        for sheet, meal_time in sheet_to_mealtime.items():
            sheet_pd = workbook.get_worksheet(worksheet_name=sheet)
            sheet_pd["meal_time"] = meal_time
            all_menus = pd.concat([all_menus, sheet_pd])

        # remove inactives as not part of active menus
        all_menus = all_menus.loc[~(all_menus.inactive.str.upper() == "Y")]
        return self._convert_fixed_menu_to_all_menu_schemas(all_menus)

    def _get_default_prep_datetime(self, row: pd.Series):
        return self.due_date_formatter.replace_time_with_meal_time(
            due_date=row.cook_datetime - timedelta(days=int(row.prep_day)),
            meal_time=self.config.default_time,
        )

    def load_fixed_menu(self) -> DataFrameBase[LoadedMenuSchema]:
        FILE_LOGGER.info("[load_fixed_menu]")
        basic_number = self.config.basic_number
        self._check_fixed_menu_number(basic_number)
        menu_number = self.config.menu_number
        self._check_fixed_menu_number(menu_number)
        fixed_menu = self.all_menus_df[
            self.all_menus_df.menu.isin([basic_number, menu_number])
        ].copy()

        basic_season = self.config.basic_season.casefold()
        self._check_season(basic_season)
        selected_season = self.config.selected_season.casefold()
        self._check_season(selected_season)
        fixed_menu = fixed_menu[
            fixed_menu.season.isin([basic_season, selected_season])
        ]

        fixed_menu["cook_datetime"] = fixed_menu.apply(
            lambda row: self.due_date_formatter.get_due_datetime_with_meal_time(
                weekday=row.weekday, meal_time=row.meal_time
            ),
            axis=1,
        )
        fixed_menu["prep_datetime"] = fixed_menu.apply(
            self._get_default_prep_datetime, axis=1
        )
        return validate_menu_schema(
            dataframe=fixed_menu, model=LoadedMenuSchema
        )

    def select_upcoming_menus(
        self, num_weeks_in_future: int
    ) -> DataFrameBase[BasicMenuSchema]:
        FILE_LOGGER.info("[select_upcoming_menus]")

        menu_number = self.config.menu_number
        self._check_fixed_menu_number(menu_number)

        if not isinstance(num_weeks_in_future, int) or num_weeks_in_future <= 0:
            raise ValueError(
                "fixed.already_in_future_menus.num_weeks "
                f"({num_weeks_in_future}) must be int>0"
            )

        max_num_menu = self.all_menus_df.menu.max()

        num_current_menu = menu_number
        num_future_menus = []
        for x in range(num_weeks_in_future):
            num_current_menu += 1
            if num_current_menu > max_num_menu:
                num_current_menu = max(
                    self.all_menus_df.menu.min(), self.config.min_menu_number
                )
            num_future_menus.append(num_current_menu)

        mask_num_future_menus = self.all_menus_df.menu.isin(num_future_menus)
        return self.all_menus_df[mask_num_future_menus].copy()
