import pytest
from freezegun import freeze_time
from hydra import compose, initialize
from sous_chef.menu.create_menu import Menu
from tests.conftest import FROZEN_DATE


@pytest.fixture
def menu_config():
    with initialize(version_base=None, config_path="../../../config/menu"):
        config = compose(config_name="create_menu").create_menu
        config.final_menu.worksheet = "test-tmp-menu"
        return config


@pytest.fixture
@freeze_time(FROZEN_DATE)
def menu_with_recipe_book(
    menu_config,
    gsheets_helper,
    mock_ingredient_formatter,
    recipe_book,
    frozen_due_datetime_formatter,
):
    menu = Menu(
        config=menu_config,
        gsheets_helper=gsheets_helper,
        ingredient_formatter=mock_ingredient_formatter,
        recipe_book=recipe_book,
    )
    menu.due_date_formatter = frozen_due_datetime_formatter
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
        gsheets_helper=gsheets_helper,
        ingredient_formatter=mock_ingredient_formatter,
        recipe_book=mock_recipe_book,
    )
    menu.due_date_formatter = frozen_due_datetime_formatter
    return menu


@pytest.mark.gsheets
class TestMenu:
    @staticmethod
    @pytest.mark.dropbox
    def test_finalize_fixed_menu(menu_with_recipe_book, menu_config):
        menu_config.fixed.menu_number = 1
        menu_with_recipe_book.finalize_fixed_menu()

    @staticmethod
    def test_load_final_menu(menu):
        menu.load_final_menu()
