from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from omegaconf import DictConfig
from pandera.typing.common import DataFrameBase
from sous_chef.date.get_due_date import DueDatetimeFormatter
from sous_chef.menu.create_menu.models import (
    AllMenuSchema,
    BasicMenuSchema,
    LoadedMenuSchema,
    Season,
    get_weekday_from_short,
    validate_menu_schema,
)
from structlog import get_logger

from utilities.api.gsheets_api import GsheetsHelper

FILE_LOGGER = get_logger(__name__)


class MenuTemplates:
    def __init__(
        self,
        config: DictConfig,
        due_date_formatter: DueDatetimeFormatter,
        gsheets_helper: GsheetsHelper,
    ):
        self.config = config
        self.due_date_formatter = due_date_formatter
        self.all_menus_df = self._get_all_menu_templates(
            gsheets_helper=gsheets_helper
        )

    def _check_menu_template_number(self, menu_number: int):
        if not isinstance(menu_number, int):
            raise ValueError(f"template menu number ({menu_number}) not an int")
        if menu_number not in self.all_menus_df.menu.values:
            raise ValueError(
                f"template menu number ({menu_number}) is not found"
            )

    @staticmethod
    def _check_season(season: str):
        if season not in Season.value_list():
            raise ValueError(f"season ({season}) not in {Season.value_list()}")

    @staticmethod
    def _convert_menu_templates_to_all_menu_schemas(
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
            .sort_values(by=["menu", "season", "weekday", "meal_time"])
            .reset_index(drop=True)
        )

    def _get_all_menu_templates(
        self, gsheets_helper: GsheetsHelper
    ) -> DataFrameBase[AllMenuSchema]:
        FILE_LOGGER.info("[_get_all_menu_templates]")

        workbook = gsheets_helper.get_workbook(
            workbook_name=self.config.workbook
        )

        all_menus = pd.DataFrame()
        for sheet, meal_time in self.config.sheet_to_mealtime.items():
            sheet_pd = workbook.get_worksheet(worksheet_name=sheet)
            sheet_pd["meal_time"] = meal_time
            all_menus = pd.concat([all_menus, sheet_pd])

        # remove inactive entries as not part of active menus
        all_menus = all_menus.loc[~(all_menus.inactive.str.upper() == "Y")]
        return self._convert_menu_templates_to_all_menu_schemas(all_menus)

    def _get_default_cook_datetime(self, row: pd.Series) -> datetime:
        return self.due_date_formatter.get_due_datetime_with_meal_time(
            weekday=row.weekday, meal_time=row.meal_time
        )

    def _get_default_prep_datetime(self, row: pd.Series) -> datetime:
        return self.due_date_formatter.replace_time_with_meal_time(
            due_date=row.cook_datetime - timedelta(days=int(row.prep_day)),
            meal_time=self.config.default_time,
        )

    def load_menu_template(self) -> DataFrameBase[LoadedMenuSchema]:
        FILE_LOGGER.info("[load_menu_template]")

        basic_number = self.config.basic_number
        self._check_menu_template_number(basic_number)
        menu_number = self.config.menu_number
        self._check_menu_template_number(menu_number)
        mask = self.all_menus_df.menu.isin([basic_number, menu_number])

        basic_season = self.config.basic_season.casefold()
        self._check_season(basic_season)
        selected_season = self.config.selected_season.casefold()
        self._check_season(selected_season)
        mask &= self.all_menus_df.season.isin([basic_season, selected_season])

        menu_template = self.all_menus_df[mask].copy()
        menu_template["cook_datetime"] = menu_template.apply(
            self._get_default_cook_datetime, axis=1
        )
        menu_template["prep_datetime"] = menu_template.apply(
            self._get_default_prep_datetime, axis=1
        )
        return validate_menu_schema(
            dataframe=menu_template, model=LoadedMenuSchema
        )

    def select_upcoming_menus(
        self, num_weeks_in_future: int
    ) -> DataFrameBase[BasicMenuSchema]:
        FILE_LOGGER.info("[select_upcoming_menus]")

        menu_number = self.config.menu_number
        self._check_menu_template_number(menu_number)

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
