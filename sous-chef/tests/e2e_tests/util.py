from pathlib import Path

from hydra import compose, initialize
from tests.data.util_data import get_local_recipe_book_path

abs_path = Path(__file__).parent.absolute()

PROJECT = "Pytest-area"


class Base:
    @staticmethod
    def _get_config(config_name: str):
        with initialize(version_base=None, config_path="../../config"):
            config = compose(config_name=config_name)

            config.recipe_book.path = get_local_recipe_book_path()

            create_menu = config.menu.create_menu
            create_menu.final_menu.worksheet = "test-tmp-menu"
            create_menu.fixed.workbook = "test-fixed_menus"
            create_menu.fixed.basic_number = 0
            create_menu.fixed.menu_number = 1
            create_menu.todoist.project_name = PROJECT
            create_menu.todoist.is_active = True

            return config
