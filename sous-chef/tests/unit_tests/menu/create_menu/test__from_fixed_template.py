from unittest.mock import patch

import pandas as pd
import pytest
from freezegun import freeze_time
from sous_chef.formatter.ingredient.format_ingredient import Ingredient
from sous_chef.menu.create_menu._from_fixed_template import FixedTemplates
from sous_chef.menu.create_menu._menu_basic import MenuFutureError
from sous_chef.menu.record_menu_history import MenuHistoryError
from tests.conftest import FROZEN_DATE
from tests.unit_tests.util import create_recipe

from utilities.testing.pandas_util import assert_equal_series


@pytest.fixture
@freeze_time(FROZEN_DATE)
def fixed_templates(
    menu_config, mock_gsheets, frozen_due_datetime_formatter, mock_all_menus_df
):
    menu_config.fixed.menu_number = 2
    with patch.object(FixedTemplates, "__post_init__"):
        fixed_templates = FixedTemplates(
            config=menu_config.fixed,
            due_date_formatter=frozen_due_datetime_formatter,
            gsheets_helper=mock_gsheets,
        )
        fixed_templates.all_menus_df = mock_all_menus_df
        return fixed_templates


class TestFixedTemplates:
    @staticmethod
    @pytest.mark.parametrize("menu_number", [1, 12])
    def test__check_fixed_menu_number_expected_passes(
        fixed_templates, menu_number
    ):
        fixed_templates._check_fixed_menu_number(menu_number)

    @staticmethod
    @pytest.mark.parametrize(
        "menu_number,error_message",
        [
            (None, "fixed menu number (None) not an int"),
            (1.2, "fixed menu number (1.2) not an int"),
            ("a", "fixed menu number (a) not an int"),
        ],
    )
    def test__check_fixed_menu_number_not_integer_raise_value_error(
        fixed_templates, menu_number, error_message
    ):
        with pytest.raises(ValueError) as error:
            fixed_templates._check_fixed_menu_number(menu_number)
        assert str(error.value) == error_message

    @staticmethod
    def test_load_fixed_menu(fixed_templates):
        result = fixed_templates.load_fixed_menu()
        # from basic + 2
        assert result.shape[0] == 2

    @staticmethod
    def test_select_upcoming_menus(fixed_templates):
        num_weeks = 4
        result = fixed_templates.select_upcoming_menus(
            num_weeks_in_future=num_weeks
        )
        assert len(result.menu.unique()) == num_weeks

    @staticmethod
    @pytest.mark.parametrize("num_weeks", [None, 1.2, "a", 0])
    def test_select_upcoming_menus_num_weeks_unexpected_value(
        fixed_templates, num_weeks
    ):
        with pytest.raises(ValueError) as error:
            fixed_templates.select_upcoming_menus(num_weeks_in_future=num_weeks)
        assert (
            str(error.value) == "fixed.already_in_future_menus.num_weeks "
            f"({num_weeks}) must be int>0"
        )


class TestProcessMenu:
    @staticmethod
    @pytest.mark.parametrize(
        "quantity,unit,item", [(1.0, "cup", "frozen broccoli")]
    )
    def test__process_menu_ingredient(
        menu, menu_builder, mock_ingredient_formatter, quantity, unit, item
    ):
        row = menu_builder.create_loaded_menu_row(
            eat_factor=quantity,
            eat_unit=unit,
            item=item,
            item_type="ingredient",
        ).squeeze()

        ingredient = Ingredient(quantity=quantity, unit=unit, item=item)
        mock_ingredient_formatter.format_manual_ingredient.return_value = (
            ingredient
        )

        result = menu._process_menu(row.copy(deep=True), processed_uuid_list=[])
        assert_equal_series(
            result,
            menu_builder.create_tmp_menu_row(
                eat_factor=quantity,
                eat_unit=unit,
                item=item,
                item_type="ingredient",
            ).squeeze(),
        )

    @staticmethod
    @pytest.mark.parametrize(
        "item_type,method",
        [
            ("tag", "get_random_recipe_by_tag"),
            ("category", "get_random_recipe_by_category"),
        ],
    )
    def test__process_menu_category_or_tag(
        menu, menu_builder, mock_recipe_book, log, item_type, method
    ):
        row = menu_builder.create_loaded_menu_row(
            item_type=item_type,
            item=f"dummy_{item_type}",
        ).squeeze()

        recipe = create_recipe(title="dummy_recipe")
        getattr(mock_recipe_book, method).return_value = recipe
        mock_recipe_book.get_recipe_by_title.return_value = recipe

        result = menu._process_menu(row, processed_uuid_list=[])

        assert_equal_series(
            result,
            menu_builder.create_tmp_menu_row(
                item=recipe.title,
                item_type="recipe",
                time_total_str=recipe.time_total,
                rating=recipe.rating,
            ).squeeze(),
        )
        assert log.events == [
            {
                "event": "[process menu]",
                "level": "info",
                "action": "processing",
                "day": "Friday",
                "item": f"dummy_{item_type}",
                "type": item_type,
            },
        ]


class TestCreateMenuProcessMenuRecipe:
    recipe_title = "garlic aioli"
    time_total_str = "5 minutes"

    def _set_up_recipe(self, menu_builder, mock_recipe_book):
        row = menu_builder.create_loaded_menu_row(
            item=self.recipe_title, item_type="recipe"
        ).squeeze()

        recipe_with_time_total = create_recipe(
            title=self.recipe_title, time_total_str=self.time_total_str
        )
        mock_recipe_book.get_recipe_by_title.return_value = (
            recipe_with_time_total
        )
        return row, recipe_with_time_total.uuid

    def test__normal(self, menu, menu_builder, mock_recipe_book):
        menu_row, _ = self._set_up_recipe(menu_builder, mock_recipe_book)

        result = menu._process_menu(
            menu_row.copy(deep=True), processed_uuid_list=[]
        )

        assert_equal_series(
            result,
            menu_builder.create_tmp_menu_row(
                item=self.recipe_title,
                item_type="recipe",
                time_total_str=pd.to_timedelta(self.time_total_str),
            ).squeeze(),
        )

    def test__error_when_in_processed_uuid_list(
        self, menu, menu_builder, mock_recipe_book
    ):
        menu_row, recipe_uuid = self._set_up_recipe(
            menu_builder, mock_recipe_book
        )

        # derived exception MenuQualityError
        with pytest.raises(Exception) as error:
            menu._process_menu(menu_row, processed_uuid_list=[recipe_uuid])
        assert (
            str(error.value) == "[menu quality] recipe=garlic aioli "
            "error=recipe already processed in menu"
        )

    def test__error_when_in_menu_history_uuid_list(
        self, menu, menu_builder, mock_recipe_book
    ):
        menu_row, recipe_uuid = self._set_up_recipe(
            menu_builder, mock_recipe_book
        )

        menu.menu_history_uuid_list = [recipe_uuid]

        with pytest.raises(MenuHistoryError) as error:
            menu._process_menu(menu_row, processed_uuid_list=[])
        assert (
            str(error.value) == "[in recent menu history] recipe=garlic aioli"
        )

    def test__error_when_in_future_menu_history_uuid_list(
        self, menu, menu_builder, mock_recipe_book
    ):
        menu_row, recipe_uuid = self._set_up_recipe(
            menu_builder, mock_recipe_book
        )

        with pytest.raises(MenuFutureError) as error:
            menu._process_menu(
                menu_row, processed_uuid_list=[], future_uuid_tuple=recipe_uuid
            )
        assert str(error.value) == (
            "[future menu] recipe=garlic aioli "
            "error=recipe is in an upcoming menu"
        )
