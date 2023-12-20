import datetime
from dataclasses import dataclass
from typing import Union

import numpy as np
import pandas as pd
import pytest
from freezegun import freeze_time
from hydra import compose, initialize
from pandas import DataFrame
from pandera.typing.common import DataFrameBase
from sous_chef.menu.create_menu._menu_basic import (
    FinalizedMenuSchema,
    MenuSchema,
)
from sous_chef.menu.create_menu.create_menu import Menu
from tests.conftest import FROZEN_DATE


@pytest.fixture
def menu_config():
    with initialize(version_base=None, config_path="../../../../config/menu"):
        return compose(config_name="create_menu").create_menu


@pytest.fixture
@freeze_time(FROZEN_DATE)
def menu(
    menu_config,
    mock_gsheets,
    mock_ingredient_formatter,
    mock_menu_history,
    mock_recipe_book,
    frozen_due_datetime_formatter,
):
    return Menu(
        config=menu_config,
        due_date_formatter=frozen_due_datetime_formatter,
        gsheets_helper=mock_gsheets,
        ingredient_formatter=mock_ingredient_formatter,
        menu_historian=mock_menu_history,
        recipe_book=mock_recipe_book,
    )


@dataclass
class MenuBuilder:
    menu: pd.DataFrame = None

    def add_menu_row(self, row: pd.DataFrame):
        if self.menu is None:
            self.menu = row
        else:
            self.menu = pd.concat([self.menu, row], ignore_index=True)

    def add_menu_list(self, menu_row_list: list[pd.DataFrame]):
        for menu_row in menu_row_list:
            self.add_menu_row(menu_row)
        return self

    @staticmethod
    def create_menu_row(
        prep_day: int = 0,
        meal_time: str = "dinner",
        item_type: str = "recipe",
        eat_factor: float = 1.0,
        # gsheets has "", whereas read_csv defaults to np.nans
        eat_unit: str = "",
        freeze_factor: float = 0.0,
        defrost: str = "N",
        item: str = "dummy",
        # template matched with cook_days
        loaded_fixed_menu: bool = True,
        # after recipe/ingredient matched
        post_process_recipe: bool = False,
        rating: float = 3.0,  # np.nan, if unrated
        time_total_str: str = np.nan,
    ) -> Union[
        DataFrame, DataFrameBase[MenuSchema], DataFrameBase[FinalizedMenuSchema]
    ]:
        if item_type == "recipe":
            if time_total_str is np.nan:
                time_total_str = "5 min"
        elif item_type == "ingredient":
            if time_total_str is np.nan:
                time_total_str = "20 min"

        if (time_total := pd.to_timedelta(time_total_str)) is pd.NaT:
            time_total = None

        menu = {
            "weekday": "work_day_2",
            "prep_day": prep_day,
            "meal_time": meal_time,
            "eat_factor": eat_factor,
            "eat_unit": eat_unit,
            "freeze_factor": freeze_factor,
            "defrost": defrost,
            "item": item,
            "type": item_type,
            "selection": "either",
        }
        if not loaded_fixed_menu:
            return pd.DataFrame(menu, index=[0])
        menu["weekday"] = "Friday"
        menu["eat_datetime"] = pd.Timestamp(
            year=2022, month=1, day=21, hour=17, minute=45, tz="Europe/Berlin"
        )
        # needed for schema validation, not "proper" prep_datetime
        menu["prep_datetime"] = menu["eat_datetime"]
        menu["override_check"] = "N"
        if not post_process_recipe:
            return MenuSchema.validate(pd.DataFrame(menu, index=[0]))
        menu["rating"] = rating
        menu["time_total"] = time_total
        menu["uuid"] = "1666465773100"
        if prep_day != 0:
            menu["cook_datetime"] = menu["eat_datetime"]
            menu["prep_datetime"] = menu["eat_datetime"] - datetime.timedelta(
                days=prep_day
            )
        else:
            menu["cook_datetime"] = menu["eat_datetime"] - time_total
            menu["prep_datetime"] = menu["eat_datetime"] - time_total
        menu_df = pd.DataFrame(menu, index=[0])
        menu_df.time_total = pd.to_timedelta(menu_df.time_total)
        return FinalizedMenuSchema.validate(menu_df)

    def get_menu(self) -> pd.DataFrame:
        return self.menu


@pytest.fixture
def menu_builder():
    return MenuBuilder()