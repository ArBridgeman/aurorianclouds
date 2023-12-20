import pandas as pd
import pytest
from sous_chef.formatter.ingredient.format_ingredient import Ingredient
from sous_chef.menu.create_menu._menu_basic import MenuFutureError
from sous_chef.menu.record_menu_history import MenuHistoryError
from tests.unit_tests.util import create_recipe

from utilities.testing.pandas_util import assert_equal_series


class TestCheckFixedMenuNumber:
    @staticmethod
    @pytest.mark.parametrize("menu_number", [1, 12])
    def test__menu_number_expected_passes(menu, menu_number):
        menu._check_fixed_menu_number(menu_number)

    @staticmethod
    @pytest.mark.parametrize(
        "menu_number,error_message",
        [
            (None, "fixed menu number not specified"),
            (1.2, "fixed menu number (1.2) not an int"),
            ("a", "fixed menu number (a) not an int"),
        ],
    )
    def test__menu_number_not_integer_raise_value_error(
        menu, menu_number, error_message
    ):
        with pytest.raises(ValueError) as error:
            menu._check_fixed_menu_number(menu_number)
        assert str(error.value) == error_message

    def test__get_future_menu_uuids(self):
        # TODO implement mocked test to get future menu ids?
        pass


class TestProcessMenu:
    @staticmethod
    @pytest.mark.parametrize(
        "quantity,unit,item", [(1.0, "cup", "frozen broccoli")]
    )
    def test__process_menu_ingredient(
        menu, menu_builder, mock_ingredient_formatter, quantity, unit, item
    ):
        row = menu_builder.create_menu_row(
            eat_factor=quantity,
            eat_unit=unit,
            item=item,
            item_type="ingredient",
            loaded_fixed_menu=True,
            post_process_recipe=True,
        ).squeeze()

        ingredient = Ingredient(quantity=quantity, unit=unit, item=item)
        mock_ingredient_formatter.format_manual_ingredient.return_value = (
            ingredient
        )

        result = menu._process_menu(row.copy(deep=True), processed_uuid_list=[])
        assert_equal_series(result, row)

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
        row = menu_builder.create_menu_row(
            item_type=item_type,
            item=f"dummy_{item_type}",
            loaded_fixed_menu=True,
        ).squeeze()

        recipe = create_recipe(title="dummy_recipe")
        getattr(mock_recipe_book, method).return_value = recipe
        mock_recipe_book.get_recipe_by_title.return_value = recipe

        result = menu._process_menu(row, processed_uuid_list=[])

        assert_equal_series(
            result,
            menu_builder.create_menu_row(
                post_process_recipe=True,
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
        row = menu_builder.create_menu_row(
            item=self.recipe_title, item_type="recipe", loaded_fixed_menu=True
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
            menu_builder.create_menu_row(
                post_process_recipe=True,
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
