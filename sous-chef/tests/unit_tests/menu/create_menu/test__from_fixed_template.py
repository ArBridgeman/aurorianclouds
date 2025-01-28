import pandas as pd
import pytest
from freezegun import freeze_time
from sous_chef.formatter.ingredient.format_ingredient import Ingredient
from sous_chef.formatter.units import unit_registry
from sous_chef.menu.create_menu._from_fixed_template import (
    MenuFromFixedTemplate,
)
from tests.conftest import FROZEN_DATE
from tests.unit_tests.util import create_recipe

from utilities.testing.pandas_util import assert_equal_series


@pytest.fixture
@freeze_time(FROZEN_DATE)
def menu_from_fixed_template(
    menu_config,
    mock_ingredient_formatter,
    menu_recipe_processor,
):
    return MenuFromFixedTemplate(
        menu_config=menu_config,
        ingredient_formatter=mock_ingredient_formatter,
        menu_recipe_processor=menu_recipe_processor,
    )


class TestProcessMenu:
    @staticmethod
    @pytest.mark.parametrize(
        "quantity,pint_unit,item", [(1.0, unit_registry.cup, "frozen broccoli")]
    )
    def test__process_menu_ingredient(
        menu_from_fixed_template,
        menu_builder,
        mock_ingredient_formatter,
        quantity,
        pint_unit,
        item,
    ):
        row = menu_builder.create_loaded_menu_row(
            eat_factor=quantity,
            eat_unit=pint_unit,
            item=item,
            item_type="ingredient",
        ).squeeze()

        mock_ingredient_formatter.format_manual_ingredient.return_value = (
            Ingredient(quantity=quantity, pint_unit=pint_unit, item=item)
        )

        result = menu_from_fixed_template._process_menu(
            row.copy(deep=True), processed_uuid_list=[]
        )
        assert_equal_series(
            result,
            menu_builder.create_tmp_menu_row(
                eat_factor=quantity,
                eat_unit=pint_unit,
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
        menu_from_fixed_template,
        menu_builder,
        mock_recipe_book,
        log,
        item_type,
        method,
    ):
        row = menu_builder.create_loaded_menu_row(
            item_type=item_type,
            item=f"dummy_{item_type}",
        ).squeeze()

        recipe = create_recipe(title="dummy_recipe")
        getattr(mock_recipe_book, method).return_value = recipe
        mock_recipe_book.get_recipe_by_title.return_value = recipe

        result = menu_from_fixed_template._process_menu(
            row, processed_uuid_list=[]
        )

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
    def test_works_for_expected_usecase(
        self,
        menu_from_fixed_template,
        menu_builder,
        mock_recipe_book,
        default_menu_row_recipe_pair,
    ):
        menu_row, recipe = default_menu_row_recipe_pair

        result = menu_from_fixed_template._process_menu(
            menu_row.copy(deep=True), processed_uuid_list=[]
        )

        assert_equal_series(
            result,
            menu_builder.create_tmp_menu_row(
                item=recipe.title,
                item_type="recipe",
                time_total_str=pd.to_timedelta(recipe.time_total),
            ).squeeze(),
        )
