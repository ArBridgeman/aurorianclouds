from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

import pandas as pd
import pandera as pa
from omegaconf import DictConfig
from pandera.typing import DataFrame, Series

# from sous_chef.menu.create_menu import FinalizedMenuSchema
from sous_chef.abstract.extended_enum import ExtendedEnum
from sous_chef.messaging.gsheets_api import GsheetsHelper
from structlog import get_logger

FILE_LOGGER = get_logger(__name__)


@dataclass
class MenuHistoryError(Exception):
    recipe_title: str
    message: str = "[in recent menu history]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        return f"{self.message} recipe={self.recipe_title}"


class MapMenuHistoryErrorToException(ExtendedEnum):
    recipe_in_recent_menu_history = MenuHistoryError


class MenuHistory(pa.SchemaModel):
    cook_datetime: Series[pd.DatetimeTZDtype] = pa.Field(
        dtype_kwargs={"unit": "ns", "tz": "UTC"}, coerce=True
    )
    eat_factor: Series[float] = pa.Field(gt=0, nullable=False, coerce=True)
    item: Series[str]
    uuid: Series[str]

    class Config:
        strict = True


@dataclass
class MenuHistorian:
    config: DictConfig
    gsheets_helper: GsheetsHelper
    current_menu_start_date: datetime
    dataframe: DataFrame[MenuHistory] = None
    columns: List[str] = MenuHistory.__annotations__.keys()

    def __post_init__(self):
        self._load_history()

    def _load_history(self):
        save_loc = self.config.save_loc
        menu_history = self.gsheets_helper.get_worksheet(
            save_loc.workbook, save_loc.worksheet
        )
        if menu_history.shape == (0, 0):
            menu_history = pd.DataFrame(columns=self.columns)

        menu_history = MenuHistory.validate(menu_history)
        # exclude future so can re-run current menu with ease
        mask_not_future = (
            menu_history.cook_datetime < self.current_menu_start_date
        )
        self.dataframe = menu_history[mask_not_future]

    def add_current_menu_to_history(self, current_menu: DataFrame):
        menu_recipes = current_menu[current_menu["type"] == "recipe"][
            self.columns
        ]

        self.dataframe = pd.concat([self.dataframe, menu_recipes])
        self.dataframe = MenuHistory.validate(self.dataframe)

        save_loc = self.config.save_loc
        self.gsheets_helper.write_worksheet(
            df=self.dataframe,
            workbook_name=save_loc.workbook,
            worksheet_name=save_loc.worksheet,
        )

    def get_history_from(self, days_ago: int):
        mask_max_past = (
            self.dataframe.cook_datetime
            >= self.current_menu_start_date - timedelta(days=days_ago)
        )
        return self.dataframe.loc[mask_max_past]
