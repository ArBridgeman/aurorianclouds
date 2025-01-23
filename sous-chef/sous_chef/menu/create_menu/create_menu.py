from dataclasses import dataclass
from pathlib import Path
from typing import List

import pandas as pd
from omegaconf import DictConfig
from pandera.typing.common import DataFrameBase
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
from structlog import get_logger

from utilities.api.todoist_api import TodoistHelper

ABS_FILE_PATH = Path(__file__).absolute().parent
FILE_LOGGER = get_logger(__name__)


@dataclass
class Menu(MenuFromFixedTemplate):
    def fill_menu_template(self) -> DataFrameBase[TmpMenuSchema]:
        self.finalize_fixed_menu()
        return self.dataframe

    def finalize_menu_to_external_services(
        self, config_todoist: DictConfig
    ) -> DataFrameBase[TmpMenuSchema]:
        final_menu_df = self._load_final_menu()
        self.menu_historian.add_current_menu_to_history(
            current_menu=final_menu_df
        )

        if self.config.todoist.is_active:
            todoist_helper = TodoistHelper(config_todoist)
            self._upload_menu_to_todoist(
                final_menu_df=final_menu_df, todoist_helper=todoist_helper
            )
        return final_menu_df

    def get_menu_for_grocery_list(
        self,
    ) -> (List[MenuIngredient], List[MenuRecipe]):
        final_menu_df = self._load_final_menu()
        menu_for_grocery_list = MenuForGroceryList(
            config_errors=self.config.errors,
            final_menu_df=final_menu_df,
            ingredient_formatter=self.ingredient_formatter,
            recipe_book=self.recipe_book,
        )
        return menu_for_grocery_list.get_menu_for_grocery_list()

    def _load_final_menu(self) -> DataFrameBase[TmpMenuSchema]:
        worksheet = self.config.final_menu.worksheet
        workbook = self.gsheets_helper.get_workbook(
            self.config.final_menu.workbook
        )

        final_menu_df = workbook.get_worksheet(worksheet_name=worksheet)
        final_menu_df.time_total = pd.to_timedelta(final_menu_df.time_total)
        return validate_menu_schema(
            dataframe=final_menu_df, model=TmpMenuSchema
        )

    def _upload_menu_to_todoist(
        self,
        final_menu_df: DataFrameBase[TmpMenuSchema],
        todoist_helper: TodoistHelper,
    ):
        menu_for_todoist = MenuForTodoist(
            config=self.config.todoist,
            final_menu_df=final_menu_df,
            due_date_formatter=self.due_date_formatter,
            todoist_helper=todoist_helper,
        )
        menu_for_todoist.upload_menu_to_todoist()
