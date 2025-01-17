from unittest.mock import patch

import pytest
from freezegun import freeze_time
from hydra import compose, initialize
from sous_chef.formatter.ingredient.format_ingredient import IngredientFormatter
from sous_chef.menu.create_menu.create_menu import Menu
from sous_chef.recipe_book.recipe_util import RecipeNotFoundError
from tests.conftest import FROZEN_DATE
from tests.data.util_data import get_tmp_menu
from tests.integration_tests.menu.create_menu.conftest import PROJECT

from utilities.testing.pandas_util import assert_equal_dataframe
from utilities.validate_choice import YesNoChoices


@pytest.fixture
def ingredient_formatter(pantry_list, unit_formatter):
    with initialize(
        version_base=None, config_path="../../../../config/formatter"
    ):
        config = compose(config_name="format_ingredient")
        return IngredientFormatter(
            config=config.format_ingredient,
            pantry_list=pantry_list,
            unit_formatter=unit_formatter,
        )


@pytest.fixture
@freeze_time(FROZEN_DATE)
def menu_with_recipe_book(
    menu_config,
    gsheets_helper,
    ingredient_formatter,
    local_recipe_book,
    frozen_due_datetime_formatter,
):
    menu = Menu(
        config=menu_config,
        due_date_formatter=frozen_due_datetime_formatter,
        gsheets_helper=gsheets_helper,
        ingredient_formatter=ingredient_formatter,
        recipe_book=local_recipe_book,
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
    def test_finalize_fixed_menu_and_load_final_menu(
        menu_with_recipe_book, menu_config
    ):
        menu_config.fixed.menu_number = 1
        menu_with_recipe_book.finalize_fixed_menu()
        menu_with_recipe_book.load_final_menu()
        assert_equal_dataframe(menu_with_recipe_book.dataframe, get_tmp_menu())

    @staticmethod
    def test_finalize_fixed_menu_fails_for_record_exception(
        menu, menu_config, mock_recipe_book
    ):
        menu_config.fixed.menu_number = 0
        menu.tuple_log_exception = (RecipeNotFoundError,)

        mock_recipe_book.get_recipe_by_title.side_effect = RecipeNotFoundError(
            recipe_title="dummy", search_results="dummy"
        )

        # derived exception MenuIncompleteError
        with pytest.raises(Exception) as error:
            menu.finalize_fixed_menu()

        assert (
            str(error.value)
            == "[menu had errors] will not send to finalize until fixed"
        )
        assert set(menu.record_exception) == {
            "[recipe not found] recipe=dummy search_results=[dummy]"
        }

    @staticmethod
    def test_get_menu_for_grocery_list(menu_with_recipe_book):
        menu_with_recipe_book.get_menu_for_grocery_list()

    @staticmethod
    def test_get_menu_for_grocery_list_fails_for_record_exception(
        menu, menu_config, mock_recipe_book, capsys
    ):
        menu_config.errors["recipe_not_found"] = "log"
        mock_recipe_book.get_recipe_by_title.side_effect = RecipeNotFoundError(
            recipe_title="dummy", search_results="dummy"
        )

        # derived exception MenuIncompleteError
        with pytest.raises(Exception) as error:
            menu.get_menu_for_grocery_list()

        assert (
            str(error.value)
            == "[menu had errors] will not send to grocery list until fixed"
        )
        assert (
            "[recipe not found] recipe=dummy search_results=[dummy]"
            in capsys.readouterr().out
        )

    @staticmethod
    @pytest.mark.todoist
    def test_upload_menu_to_todoist(menu, todoist_helper):
        menu.load_final_menu()
        menu.upload_menu_to_todoist(todoist_helper)
        with patch("builtins.input", side_effect=[YesNoChoices.yes.value]):
            todoist_helper.delete_all_items_in_project(project=PROJECT)
