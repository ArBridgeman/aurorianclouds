from unittest.mock import PropertyMock, patch

import pytest
from freezegun import freeze_time
from sous_chef.date.get_due_date import DueDatetimeFormatter
from sous_chef.menu.create_menu.create_menu import Menu
from sous_chef.recipe_book.read_recipe_book import RecipeBook
from sous_chef.recipe_book.recipe_util import RecipeNotFoundError
from tests.conftest import FROZEN_DATE

from utilities.testing.pandas_util import assert_equal_dataframe


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
class TestMenuGsheets:
    @staticmethod
    def test_fill_menu_template(
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
            final_menu_df = menu_with_recipe_book.fill_menu_template_and_save()

        assert_equal_dataframe(final_menu_df, fixed_final_menu)

    @staticmethod
    def test_load_final_menu(menu, gsheets_helper, fixed_final_menu):
        final_menu_df = menu.load_final_menu(gsheets_helper=gsheets_helper)
        assert_equal_dataframe(final_menu_df, fixed_final_menu)
