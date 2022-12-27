import pytest
from freezegun import freeze_time
from hydra import compose, initialize
from sous_chef.formatter.ingredient.format_ingredient import IngredientFormatter
from sous_chef.menu.create_menu import Menu
from tests.conftest import FROZEN_DATE
from tests.integration_tests.util import clean_up_add_todoist_task


@pytest.fixture
def ingredient_formatter(pantry_list, unit_formatter):
    with initialize(version_base=None, config_path="../../../config/formatter"):
        config = compose(config_name="format_ingredient")
        return IngredientFormatter(
            config=config.format_ingredient,
            pantry_list=pantry_list,
            unit_formatter=unit_formatter,
        )


@pytest.fixture
def menu_config():
    with initialize(version_base=None, config_path="../../../config/menu"):
        config = compose(config_name="create_menu").create_menu
        config.final_menu.worksheet = "test-tmp-menu"
        config.fixed.basic = "test-menu-basic"
        config.fixed.file_prefix = "test-menu-"
        config.todoist.project_name = "Pytest-area"
        return config


@pytest.fixture
@freeze_time(FROZEN_DATE)
def menu_with_recipe_book(
    menu_config,
    gsheets_helper,
    ingredient_formatter,
    recipe_book,
    frozen_due_datetime_formatter,
):
    menu = Menu(
        config=menu_config,
        due_date_formatter=frozen_due_datetime_formatter,
        gsheets_helper=gsheets_helper,
        ingredient_formatter=ingredient_formatter,
        recipe_book=recipe_book,
    )
    return menu


@pytest.fixture
@freeze_time(FROZEN_DATE)
def menu(
    menu_config,
    gsheets_helper,
    mock_ingredient_formatter,
    mock_recipe_book,
    frozen_due_datetime_formatter,
):
    menu = Menu(
        config=menu_config,
        due_date_formatter=frozen_due_datetime_formatter,
        gsheets_helper=gsheets_helper,
        ingredient_formatter=mock_ingredient_formatter,
        recipe_book=mock_recipe_book,
    )
    return menu


@pytest.mark.gsheets
class TestMenu:
    @staticmethod
    @pytest.mark.dropbox
    def test_finalize_fixed_menu(menu_with_recipe_book, menu_config):
        menu_config.fixed.menu_number = 0
        menu_with_recipe_book.finalize_fixed_menu()

    @staticmethod
    @pytest.mark.dropbox
    def test_get_menu_for_grocery_list(menu_with_recipe_book):
        menu_with_recipe_book.get_menu_for_grocery_list()

    @staticmethod
    def test_load_final_menu(menu):
        menu.load_final_menu()

    @staticmethod
    @pytest.mark.todoist
    def test_upload_menu_to_todoist(menu, todoist_helper):
        menu.load_final_menu()
        tasks = menu.upload_menu_to_todoist(todoist_helper)
        for task in tasks:
            if task:
                clean_up_add_todoist_task(todoist_helper, task.id)
