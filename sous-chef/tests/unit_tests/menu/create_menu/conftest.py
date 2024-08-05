import datetime
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest
from freezegun import freeze_time
from hydra import compose, initialize
from pandera.typing.common import DataFrameBase
from pint import Unit
from sous_chef.formatter.units import unit_registry
from sous_chef.menu.create_menu._menu_basic import (
    AllMenuSchema,
    LoadedMenuSchema,
    TmpMenuSchema,
    validate_menu_schema,
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
    def create_all_menu_row(
        prep_day: int = 0,
        meal_time: str = "dinner",
        item_type: str = "recipe",
        eat_factor: float = 1.0,
        # gsheets has "", whereas read_csv defaults to np.nans
        eat_unit: Unit = unit_registry.dimensionless,
        freeze_factor: float = 0.0,
        defrost: str = "N",
        item: str = "dummy",
        **kwargs,
    ) -> DataFrameBase[AllMenuSchema]:

        eat_unit = str(eat_unit)
        if eat_unit == "dimensionless":
            eat_unit = ""

        return AllMenuSchema.validate(
            pd.DataFrame(
                {
                    "menu": 1,
                    "weekday": "Friday",
                    "prep_day": prep_day,
                    "meal_time": meal_time,
                    "type": item_type,
                    "selection": "either",
                    "eat_factor": eat_factor,
                    "eat_unit": eat_unit,
                    "freeze_factor": freeze_factor,
                    "defrost": defrost,
                    "override_check": "N",
                    "item": item,
                },
                index=[0],
            )
        )

    def create_loaded_menu_row(
        self, **kwargs
    ) -> DataFrameBase[LoadedMenuSchema]:
        loaded_menu_row = self.create_all_menu_row(**kwargs)
        cook_datetime = pd.Timestamp(
            year=2022, month=1, day=21, hour=17, minute=45, tz="Europe/Berlin"
        )
        loaded_menu_row["cook_datetime"] = cook_datetime
        # not realistic prep_datetime
        loaded_menu_row["prep_datetime"] = cook_datetime
        return validate_menu_schema(
            dataframe=loaded_menu_row, model=LoadedMenuSchema
        )

    def create_tmp_menu_row(
        self,
        item_type: str = "recipe",
        prep_day: int = 0,
        rating: float = 3.0,  # np.nan, if unrated
        time_total_str: str = np.nan,
        **kwargs,
    ) -> DataFrameBase[TmpMenuSchema]:
        tmp_menu = self.create_loaded_menu_row(
            item_type=item_type, prep_day=prep_day, **kwargs
        )
        # template matched with cook_days
        # after recipe/ingredient matched

        if item_type == "recipe":
            tmp_menu["rating"] = rating
            tmp_menu["uuid"] = "1666465773100"
            if time_total_str is np.nan:
                time_total_str = "5 min"
        elif item_type == "ingredient":
            tmp_menu["rating"] = np.NaN
            tmp_menu["uuid"] = np.NaN
            if time_total_str is np.nan:
                time_total_str = "20 min"

        time_total = pd.to_timedelta(time_total_str)
        tmp_menu["time_total"] = time_total

        if prep_day != 0:
            tmp_menu["cook_datetime"] = tmp_menu["cook_datetime"]
            tmp_menu["prep_datetime"] = tmp_menu[
                "cook_datetime"
            ] - datetime.timedelta(days=prep_day)
        else:
            tmp_menu["cook_datetime"] = tmp_menu["cook_datetime"] - time_total
            tmp_menu["prep_datetime"] = tmp_menu["cook_datetime"]
        tmp_menu.time_total = pd.to_timedelta(tmp_menu.time_total)
        return validate_menu_schema(dataframe=tmp_menu, model=TmpMenuSchema)

    def get_menu(self) -> pd.DataFrame:
        return self.menu


@pytest.fixture
def menu_builder():
    return MenuBuilder()
