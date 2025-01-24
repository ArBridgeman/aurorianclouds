from unittest.mock import PropertyMock, patch

import pytest
from freezegun import freeze_time
from sous_chef.date.get_due_date import DueDatetimeFormatter
from sous_chef.menu.create_menu.create_menu import Menu
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from sous_chef.recipe_book.recipe_util import RecipeNotFoundError
from tests.conftest import FROZEN_DATE
from tests.integration_tests.menu.conftest import PROJECT

from utilities.testing.pandas_util import assert_equal_dataframe
from utilities.validate_choice import YesNoChoices


@pytest.fixture
def menu_with_recipe_book(config):
    return Menu(config=config)


@pytest.fixture
@freeze_time(FROZEN_DATE)
def menu(config):
    return Menu(config=config)


@pytest.fixture
def mock_recipe_book(monkeypatch):
    def side_effect(*args, **kwargs):
        raise RecipeNotFoundError(recipe_title="dummy", search_results="dummy")

    monkeypatch.setattr(
        RecipeBook, RecipeBook.get_recipe_by_title.__name__, side_effect
    )


@pytest.mark.gsheets
class TestMenu:
    @staticmethod
    def test_fill_menu_template_and_load_final_menu(
        menu_with_recipe_book,
        menu_config,
        frozen_due_datetime_formatter,
        gsheets_helper,
        fixed_final_menu,
    ):
        with patch.object(
            DueDatetimeFormatter,
            "anchor_datetime",
            new_callable=PropertyMock,
            return_value=frozen_due_datetime_formatter.anchor_datetime,
        ):
            final_menu_df = menu_with_recipe_book.fill_menu_template()

        assert_equal_dataframe(final_menu_df, fixed_final_menu)

        final_menu_df = menu_with_recipe_book._load_final_menu(
            gsheets_helper=gsheets_helper
        )
        assert_equal_dataframe(final_menu_df, fixed_final_menu)

    @staticmethod
    def test_fill_menu_template_fails_for_record_exception(
        menu, menu_config, mock_recipe_book, capsys
    ):
        menu_config.fixed.menu_number = 0
        menu.tuple_log_exception = (RecipeNotFoundError,)

        # derived exception MenuIncompleteError
        with pytest.raises(Exception) as error:
            menu.fill_menu_template()

        assert (
            str(error.value)
            == "[menu had errors] will not send to finalize until fixed"
        )
        assert (
            "[recipe not found] recipe=dummy search_results=[dummy]"
            in capsys.readouterr().out
        )

    @staticmethod
    def test_get_menu_for_grocery_list(menu_with_recipe_book):
        menu_with_recipe_book.get_menu_for_grocery_list()

    @staticmethod
    def test_get_menu_for_grocery_list_fails_for_record_exception(
        menu, menu_config, mock_recipe_book, capsys
    ):
        menu_config.errors["recipe_not_found"] = "log"

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
    def test__upload_menu_to_todoist(
        menu, frozen_due_datetime_formatter, gsheets_helper, todoist_helper
    ):
        final_menu_df = menu._load_final_menu(gsheets_helper=gsheets_helper)
        with patch("builtins.input", side_effect=[YesNoChoices.yes.value]):
            menu._upload_menu_to_todoist(
                final_menu_df=final_menu_df,
                due_date_formatter=frozen_due_datetime_formatter,
                todoist_helper=todoist_helper,
            )

        with patch("builtins.input", side_effect=[YesNoChoices.yes.value]):
            todoist_helper.delete_all_items_in_project(project=PROJECT)
