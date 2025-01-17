from dataclasses import dataclass
from pathlib import Path
from typing import List

from sous_chef.menu.create_menu._for_grocery_list import (
    MenuForGroceryList,
    MenuIngredient,
    MenuRecipe,
)
from sous_chef.menu.create_menu._for_todoist import MenuForTodoist
from sous_chef.menu.create_menu._from_fixed_template import (
    MenuFromFixedTemplate,
)
from structlog import get_logger

from utilities.api.todoist_api import TodoistHelper

ABS_FILE_PATH = Path(__file__).absolute().parent
FILE_LOGGER = get_logger(__name__)


@dataclass
class Menu(MenuFromFixedTemplate):
    def temporarily_output_menu_for_review(self):
        pass

    def finalize_menu_to_external_services(self):
        pass

    def get_menu_for_grocery_list(
        self,
    ) -> (List[MenuIngredient], List[MenuRecipe]):
        final_menu_df = self.load_final_menu()
        menu_for_grocery_list = MenuForGroceryList(
            config_errors=self.config.errors,
            final_menu_df=final_menu_df,
            ingredient_formatter=self.ingredient_formatter,
            recipe_book=self.recipe_book,
        )
        return menu_for_grocery_list.get_menu_for_grocery_list()

    def upload_menu_to_todoist(self, todoist_helper: TodoistHelper):
        menu_for_todoist = MenuForTodoist(
            config=self.config.todoist,
            final_menu_df=self.dataframe,
            due_date_formatter=self.due_date_formatter,
            todoist_helper=todoist_helper,
        )
        menu_for_todoist.upload_menu_to_todoist()
