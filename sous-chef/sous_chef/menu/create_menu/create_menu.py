from dataclasses import dataclass
from pathlib import Path

from sous_chef.menu.create_menu._for_grocery_list import MenuForGroceryList
from sous_chef.menu.create_menu._for_todoist import MenuForTodoist
from sous_chef.menu.create_menu._from_fixed_template import (
    MenuFromFixedTemplate,
)
from structlog import get_logger

from utilities.api.todoist_api import TodoistHelper

ABS_FILE_PATH = Path(__file__).absolute().parent
FILE_LOGGER = get_logger(__name__)


@dataclass
class Menu(MenuForGroceryList, MenuFromFixedTemplate):
    def upload_menu_to_todoist(self, todoist_helper: TodoistHelper):
        menu_for_todoist = MenuForTodoist(
            config=self.config.todoist,
            dataframe=self.dataframe,
            due_date_formatter=self.due_date_formatter,
            todoist_helper=todoist_helper,
        )
        menu_for_todoist.upload_menu_to_todoist()
