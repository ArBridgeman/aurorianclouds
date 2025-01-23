from datetime import timedelta
from pathlib import Path
from typing import List

import pandas as pd
from omegaconf import DictConfig
from pandera.typing.common import DataFrameBase
from sous_chef.date.get_due_date import DueDatetimeFormatter
from sous_chef.formatter.format_unit import UnitFormatter
from sous_chef.formatter.ingredient.format_ingredient import IngredientFormatter
from sous_chef.menu.create_menu._for_grocery_list import (
    MenuForGroceryList,
    MenuIngredient,
    MenuRecipe,
)
from sous_chef.menu.create_menu._for_todoist import MenuForTodoist
from sous_chef.menu.create_menu._from_fixed_template import (
    MenuFromFixedTemplate,
)
from sous_chef.menu.create_menu._menu_basic import validate_menu_schema
from sous_chef.menu.create_menu.models import TmpMenuSchema
from sous_chef.menu.record_menu_history import MenuHistorian
from sous_chef.pantry_list.read_pantry_list import PantryList
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from structlog import get_logger

from utilities.api.gsheets_api import GsheetsHelper
from utilities.api.todoist_api import TodoistHelper

ABS_FILE_PATH = Path(__file__).absolute().parent
FILE_LOGGER = get_logger(__name__)


class Menu:
    def __init__(self, config: DictConfig):
        self.config = config
        self.menu_config = config.menu.create_menu

    def fill_menu_template(self) -> DataFrameBase[TmpMenuSchema]:
        due_date_formatter = DueDatetimeFormatter(
            config=self.config.date.due_date
        )
        gsheets_helper = GsheetsHelper(self.config.api.gsheets)
        ingredient_formatter = _get_ingredient_formatter(
            config=self.config, gsheets_helper=gsheets_helper
        )
        recipe_book = RecipeBook(self.config.recipe_book)
        menu_historian = MenuHistorian(
            config=self.config.menu.record_menu_history,
            current_menu_start_date=due_date_formatter.get_anchor_datetime()
            + timedelta(days=1),
            gsheets_helper=gsheets_helper,
        )

        menu_from_fixed_template = MenuFromFixedTemplate(
            config=self.config,
            menu_config=self.config.menu.create_menu,
            due_date_formatter=due_date_formatter,
            gsheets_helper=gsheets_helper,
            ingredient_formatter=ingredient_formatter,
            menu_historian=menu_historian,
            recipe_book=recipe_book,
        )

        return menu_from_fixed_template.finalize_fixed_menu()

    def finalize_menu_to_external_services(
        self, config_todoist: DictConfig
    ) -> DataFrameBase[TmpMenuSchema]:
        due_date_formatter = DueDatetimeFormatter(
            config=self.config.date.due_date
        )
        gsheets_helper = GsheetsHelper(self.config.api.gsheets)

        final_menu_df = self._load_final_menu(gsheets_helper=gsheets_helper)

        menu_historian = MenuHistorian(
            config=self.config.menu.record_menu_history,
            current_menu_start_date=due_date_formatter.get_anchor_datetime()
            + timedelta(days=1),
            gsheets_helper=gsheets_helper,
        )
        menu_historian.add_current_menu_to_history(current_menu=final_menu_df)

        if self.menu_config.todoist.is_active:
            todoist_helper = TodoistHelper(config_todoist)
            self._upload_menu_to_todoist(
                final_menu_df=final_menu_df,
                due_date_formatter=due_date_formatter,
                todoist_helper=todoist_helper,
            )
        return final_menu_df

    def get_menu_for_grocery_list(
        self,
    ) -> (List[MenuIngredient], List[MenuRecipe]):
        recipe_book = RecipeBook(self.config.recipe_book)
        gsheets_helper = GsheetsHelper(self.config.api.gsheets)
        ingredient_formatter = _get_ingredient_formatter(
            config=self.config, gsheets_helper=gsheets_helper
        )

        final_menu_df = self._load_final_menu(gsheets_helper=gsheets_helper)
        menu_for_grocery_list = MenuForGroceryList(
            config_errors=self.menu_config.errors,
            final_menu_df=final_menu_df,
            ingredient_formatter=ingredient_formatter,
            recipe_book=recipe_book,
        )
        return menu_for_grocery_list.get_menu_for_grocery_list()

    def _load_final_menu(
        self, gsheets_helper: GsheetsHelper
    ) -> DataFrameBase[TmpMenuSchema]:
        worksheet = self.menu_config.final_menu.worksheet
        workbook = gsheets_helper.get_workbook(
            self.menu_config.final_menu.workbook
        )

        final_menu_df = workbook.get_worksheet(worksheet_name=worksheet)
        final_menu_df.time_total = pd.to_timedelta(final_menu_df.time_total)
        return validate_menu_schema(
            dataframe=final_menu_df, model=TmpMenuSchema
        )

    def _upload_menu_to_todoist(
        self,
        final_menu_df: DataFrameBase[TmpMenuSchema],
        due_date_formatter: DueDatetimeFormatter,
        todoist_helper: TodoistHelper,
    ):
        menu_for_todoist = MenuForTodoist(
            config=self.menu_config.todoist,
            final_menu_df=final_menu_df,
            due_date_formatter=due_date_formatter,
            todoist_helper=todoist_helper,
        )
        menu_for_todoist.upload_menu_to_todoist()


def _get_ingredient_formatter(
    config: DictConfig, gsheets_helper: GsheetsHelper
):
    pantry_list = PantryList(config.pantry_list, gsheets_helper=gsheets_helper)
    return IngredientFormatter(
        config.formatter.format_ingredient,
        unit_formatter=UnitFormatter(),
        pantry_list=pantry_list,
    )
