import pandas as pd
import pytest
from freezegun import freeze_time
from sous_chef.formatter.ingredient.format_ingredient import Ingredient
from sous_chef.formatter.units import unit_registry
from sous_chef.menu.create_menu._fill_menu_template import MenuTemplateFiller
from sous_chef.menu.create_menu.models import Type, TypeProcessOrder
from tests.conftest import FROZEN_DATE
from tests.unit_tests.util import create_recipe

from utilities.testing.pandas_util import assert_equal_dataframe


@pytest.fixture
@freeze_time(FROZEN_DATE)
def menu_template_filler(
    menu_config,
    mock_ingredient_formatter,
    menu_recipe_processor,
):
    return MenuTemplateFiller(
        menu_config=menu_config,
        ingredient_formatter=mock_ingredient_formatter,
        menu_recipe_processor=menu_recipe_processor,
    )


class TestProcessMenu:
    @staticmethod
    @pytest.mark.parametrize(
        "quantity,pint_unit,item", [(1.0, unit_registry.cup, "frozen broccoli")]
    )
    def test__works_as_expected_for_ingredient(
        menu_template_filler,
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
            item_type=TypeProcessOrder.ingredient.name,
        ).squeeze()

        mock_ingredient_formatter.format_manual_ingredient.return_value = (
            Ingredient(quantity=quantity, pint_unit=pint_unit, item=item)
        )

        result = menu_template_filler._process_menu(row)
        assert_equal_dataframe(
            result,
            menu_builder.create_tmp_menu_row(
                eat_factor=quantity,
                eat_unit=pint_unit,
                item=item,
                item_type="ingredient",
            ),
        )

    @staticmethod
    @pytest.mark.parametrize(
        "item_type,method",
        [
            (TypeProcessOrder.category.name, "get_random_recipe_by_category"),
            (TypeProcessOrder.filter.name, "get_random_recipe_by_filter"),
            (TypeProcessOrder.tag.name, "get_random_recipe_by_tag"),
        ],
    )
    def test__works_as_expected_for_random_selection(
        menu_template_filler,
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

        result = menu_template_filler._process_menu(row)

        assert_equal_dataframe(
            result,
            menu_builder.create_tmp_menu_row(
                item=recipe.title,
                item_type=Type.recipe.value,
                time_total_str=recipe.time_total,
                rating=recipe.rating,
            ),
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

    def test__works_as_expected_for_recipe(
        self,
        menu_template_filler,
        menu_builder,
        mock_recipe_book,
        default_menu_row_recipe_pair,
    ):
        menu_row, recipe = default_menu_row_recipe_pair

        result = menu_template_filler._process_menu(menu_row)

        assert_equal_dataframe(
            result,
            menu_builder.create_tmp_menu_row(
                item=recipe.title,
                item_type=Type.recipe.value,
                time_total_str=pd.to_timedelta(recipe.time_total),
            ),
        )
