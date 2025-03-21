from datetime import timedelta
from pathlib import Path
from typing import List

import pandas as pd
from omegaconf import DictConfig
from pandera.typing.common import DataFrameBase
from sous_chef.date.get_due_date import DueDatetimeFormatter
from sous_chef.formatter.format_unit import UnitFormatter
from sous_chef.formatter.ingredient.format_ingredient import IngredientFormatter
from sous_chef.menu.create_menu._export_to_todoist import MenuForTodoist
from sous_chef.menu.create_menu._fill_menu_template import MenuTemplateFiller
from sous_chef.menu.create_menu._output_for_grocery_list import (
    MenuForGroceryList,
    MenuIngredient,
    MenuRecipe,
)
from sous_chef.menu.create_menu._process_menu_recipe import MenuRecipeProcessor
from sous_chef.menu.create_menu._select_menu_template import MenuTemplates
from sous_chef.menu.create_menu.models import (
    TmpMenuSchema,
    validate_menu_schema,
)
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

    def _get_menu_recipe_processor(
        self,
        due_date_formatter: DueDatetimeFormatter,
        gsheets_helper: GsheetsHelper,
        menu_templates: MenuTemplates,
    ) -> MenuRecipeProcessor:
        menu_recipe_processor = MenuRecipeProcessor(
            menu_config=self.menu_config,
            recipe_book=RecipeBook(self.config.recipe_book),
        )

        menu_historian = MenuHistorian(
            config=self.config.menu.record_menu_history,
            current_menu_start_date=due_date_formatter.get_anchor_datetime()
            + timedelta(days=1),
            gsheets_helper=gsheets_helper,
        )
        menu_recipe_processor.set_menu_history_uuids(
            menu_historian=menu_historian
        )

        if self.menu_config.fixed.already_in_future_menus.active:
            menu_recipe_processor.set_future_menu_uuids(
                menu_templates=menu_templates
            )

        return menu_recipe_processor

    def fill_menu_template_and_save(self) -> DataFrameBase[TmpMenuSchema]:
        due_date_formatter = DueDatetimeFormatter(
            config=self.config.date.due_date
        )
        gsheets_helper = GsheetsHelper(self.config.api.gsheets)

        # load and use menu templates
        menu_templates = MenuTemplates(
            config=self.menu_config.fixed,
            due_date_formatter=due_date_formatter,
            gsheets_helper=gsheets_helper,
        )
        menu_template_df = menu_templates.load_menu_template()

        # set up key service for filling menu template
        menu_template_filler = MenuTemplateFiller(
            menu_config=self.config.menu.create_menu,
            ingredient_formatter=IngredientFormatter(
                config=self.config.formatter.format_ingredient,
                unit_formatter=UnitFormatter(),
                pantry_list=PantryList(
                    self.config.pantry_list, gsheets_helper=gsheets_helper
                ),
            ),
            menu_recipe_processor=self._get_menu_recipe_processor(
                due_date_formatter=due_date_formatter,
                gsheets_helper=gsheets_helper,
                menu_templates=menu_templates,
            ),
        )

        # fill menu template & save
        final_menu_df = menu_template_filler.fill_menu_template(
            menu_template_df=menu_template_df
        )
        gsheets_helper.write_worksheet(
            df=final_menu_df,
            workbook_name=self.menu_config.final_menu.workbook,
            worksheet_name=self.menu_config.final_menu.worksheet,
        )
        return final_menu_df

    def finalize_menu_to_external_services(
        self,
    ) -> DataFrameBase[TmpMenuSchema]:
        due_date_formatter = DueDatetimeFormatter(
            config=self.config.date.due_date
        )
        gsheets_helper = GsheetsHelper(self.config.api.gsheets)
        menu_historian = MenuHistorian(
            config=self.config.menu.record_menu_history,
            current_menu_start_date=due_date_formatter.get_anchor_datetime()
            + timedelta(days=1),
            gsheets_helper=gsheets_helper,
        )

        final_menu_df = self.load_final_menu(gsheets_helper=gsheets_helper)
        # send to external services
        menu_historian.add_current_menu_to_history(current_menu=final_menu_df)
        if self.menu_config.todoist.is_active:
            menu_for_todoist = MenuForTodoist(
                config=self.menu_config.todoist,
                final_menu_df=final_menu_df,
                due_date_formatter=due_date_formatter,
                todoist_helper=TodoistHelper(self.config.api.todoist),
            )
            menu_for_todoist.upload_menu_to_todoist()
        return final_menu_df

    def get_menu_for_grocery_list(
        self,
    ) -> (List[MenuIngredient], List[MenuRecipe]):
        recipe_book = RecipeBook(self.config.recipe_book)
        gsheets_helper = GsheetsHelper(self.config.api.gsheets)
        ingredient_formatter = IngredientFormatter(
            config=self.config.formatter.format_ingredient,
            unit_formatter=UnitFormatter(),
            pantry_list=PantryList(
                config=self.config.pantry_list, gsheets_helper=gsheets_helper
            ),
        )

        final_menu_df = self.load_final_menu(gsheets_helper=gsheets_helper)
        menu_for_grocery_list = MenuForGroceryList(
            config_errors=self.menu_config.errors,
            final_menu_df=final_menu_df,
            ingredient_formatter=ingredient_formatter,
            recipe_book=recipe_book,
        )
        return menu_for_grocery_list.get_menu_for_grocery_list()

    def load_final_menu(
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
