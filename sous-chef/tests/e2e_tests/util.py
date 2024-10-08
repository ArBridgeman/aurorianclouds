from pathlib import Path
from unittest.mock import patch

from hydra import compose, initialize
from omegaconf import DictConfig
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from tests.data.util_data import get_local_recipe_book_path

abs_path = Path(__file__).parent.absolute()

PROJECT = "Pytest-area"


class Base:
    @staticmethod
    def _get_config(config_name: str):
        with initialize(version_base=None, config_path="../../config"):
            return compose(config_name=config_name)

    @staticmethod
    def _get_local_recipe_book(config: DictConfig):
        with patch.object(RecipeBook, "__post_init__", lambda x: None):
            recipe_book = RecipeBook(config)
            # TODO see if something else using & move
            recipe_book.recipe_book_path = get_local_recipe_book_path()
            recipe_book._read_recipe_book()
            recipe_book._load_pint_quantity()
            return recipe_book.dataframe

    @staticmethod
    def _set_config_menu(config: DictConfig):
        create_menu = config.menu.create_menu
        create_menu.final_menu.worksheet = "test-tmp-menu"
        create_menu.fixed.workbook = "test-fixed_menus"
        create_menu.fixed.basic_number = 0
        create_menu.fixed.menu_number = 1
        create_menu.todoist.project_name = PROJECT
