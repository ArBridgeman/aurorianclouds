import pandas as pd
import pytest
from sous_chef.formatter.ingredient.format_ingredient import Ingredient
from sous_chef.formatter.units import unit_registry
from sous_chef.menu.create_menu._for_grocery_list import (
    MenuForGroceryList,
    MenuIngredient,
    MenuRecipe,
)
from tests.unit_tests.util import create_recipe


@pytest.fixture
def menu_for_grocery_list(
    menu_config,
    mock_ingredient_formatter,
    mock_recipe_book,
):
    return MenuForGroceryList(
        config_errors=menu_config.errors,
        # not needed in unit tests as row given explicitly
        final_menu_df=pd.DataFrame(),
        ingredient_formatter=mock_ingredient_formatter,
        recipe_book=mock_recipe_book,
    )


class TestForGroceryList:
    @staticmethod
    @pytest.mark.parametrize(
        "quantity,pint_unit,item", [(1.0, unit_registry.cup, "frozen broccoli")]
    )
    def test__retrieve_manual_menu_ingredient(
        menu_for_grocery_list,
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

        ingredient = Ingredient(
            quantity=quantity, pint_unit=pint_unit, item=item
        )
        mock_ingredient_formatter.format_manual_ingredient.return_value = (
            ingredient
        )
        result = menu_for_grocery_list._retrieve_manual_menu_ingredient(row)
        assert (
            result.__dict__
            == MenuIngredient(
                ingredient=ingredient,
                from_recipe="manual",
                for_day=row["prep_datetime"],
            ).__dict__
        )

    @staticmethod
    @pytest.mark.parametrize(
        "recipe_title",
        ["grilled cheese", "garlic aioli"],
    )
    def test__retrieve_menu_recipe(
        menu_for_grocery_list,
        menu_builder,
        mock_recipe_book,
        recipe_title,
    ):
        row = menu_builder.create_loaded_menu_row(
            item=recipe_title,
            item_type="recipe",
        ).squeeze()
        recipe_with_recipe_title = create_recipe(title=recipe_title)
        mock_recipe_book.get_recipe_by_title.return_value = (
            recipe_with_recipe_title
        )

        result = menu_for_grocery_list._retrieve_menu_recipe(row)

        assert (
            result.__dict__
            == MenuRecipe(
                recipe=recipe_with_recipe_title,
                eat_factor=row["eat_factor"],
                freeze_factor=0.0,
                for_day=row["prep_datetime"],
                from_recipe=row["item"],
            ).__dict__
        )
