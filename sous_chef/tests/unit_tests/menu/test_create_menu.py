from unittest.mock import Mock

import pandas as pd
import pytest
from hydra import compose, initialize
from sous_chef.formatter.ingredient.format_ingredient import (
    Ingredient,
    IngredientFormatter,
)
from sous_chef.menu.create_menu import Menu, MenuIngredient, MenuRecipe
from tests.util import RecipeBuilder


@pytest.fixture
def recipe_with_total_cook_time(recipe_title, total_cook_time_str):
    return (
        RecipeBuilder()
        .with_recipe_title(recipe_title)
        .with_total_cook_time(total_cook_time_str)
        .build()
    )


@pytest.fixture
def recipe_with_rating(rating):
    return RecipeBuilder().with_rating(rating).build()


@pytest.fixture
def ingredient(quantity, unit, item):
    return Ingredient(quantity=quantity, unit=unit, item=item)


@pytest.fixture
def mock_ingredient_formatter():
    with initialize(config_path="../../../config/formatter"):
        config = compose(config_name="format_ingredient")
        return Mock(IngredientFormatter(config, None, None))


@pytest.fixture()
def menu_config():
    with initialize(config_path="../../../config"):
        return compose(config_name="menu").menu


@pytest.fixture
def menu(menu_config, mock_ingredient_formatter, mock_recipe_book):
    return Menu(
        ingredient_formatter=mock_ingredient_formatter,
        config=menu_config,
        recipe_book=mock_recipe_book,
    )


def create_menu_row(
    item: str = "dummy",
    item_type: str = "recipe",
    factor: float = 1.0,
    unit: str = None,
):
    return pd.Series(
        {
            "factor": factor,
            "unit": unit,
            "item": item,
            "type": item_type,
            "weekday": "Friday",
        }
    )


class TestMenu:
    @staticmethod
    @pytest.mark.parametrize("menu_number", [1, 12])
    def test__check_fixed_menu_number(menu, menu_number):
        assert menu._check_fixed_menu_number(menu_number) == menu_number

    @staticmethod
    @pytest.mark.parametrize(
        "menu_number,error_message",
        [
            (None, "fixed menu number not specified"),
            (1.2, "fixed menu number (1.2) not an int"),
            ("a", "fixed menu number (a) not an int"),
        ],
    )
    def test__check_fixed_menu_number_raise_value_error(
        menu, menu_number, error_message
    ):
        with pytest.raises(ValueError) as e:
            menu._check_fixed_menu_number(menu_number)
        assert e.value.args[0] == error_message

    @staticmethod
    @pytest.mark.parametrize("old_factor,new_factor", [(1, 1.5), (1.0, 2.0)])
    def test__edit_item_factor(menu, monkeypatch, old_factor, new_factor):
        monkeypatch.setattr("builtins.input", lambda _: f"{new_factor}")
        assert menu._edit_item_factor(old_factor) == new_factor

    @staticmethod
    @pytest.mark.parametrize(
        "recipe_title,total_cook_time_str",
        [("garlic aioli", "5 minutes"), ("banana souffle", "1 hour 4 minutes")],
    )
    def test__enrich_with_cooking_time(
        menu,
        mock_recipe_book,
        recipe_title,
        total_cook_time_str,
        recipe_with_total_cook_time,
    ):
        row = create_menu_row(item=recipe_title, item_type="recipe")
        mock_recipe_book.get_recipe_by_title.return_value = (
            recipe_with_total_cook_time
        )
        result = menu._enrich_with_cooking_time(row)

        assert result["item"] == recipe_with_total_cook_time.title
        assert (
            result["total_cook_time"]
            == recipe_with_total_cook_time.total_cook_time
        )

    @staticmethod
    @pytest.mark.parametrize("rating", [0.0])
    def test__inspect_unrated_recipe(
        capsys,
        log,
        menu_config,
        menu,
        recipe_with_rating,
        rating,
    ):
        menu_config.run_mode.with_inspect_unrated_recipe = True

        menu._inspect_unrated_recipe(recipe_with_rating)
        out, err = capsys.readouterr()

        assert log.events == [
            {
                "action": "print out ingredient_field",
                "event": "[unrated recipe]",
                "level": "warning",
                "recipe_title": "dummy_title",
            }
        ]
        assert out == "1 dummy text\n"
        assert err == ""

    @staticmethod
    @pytest.mark.parametrize(
        "quantity,unit,item", [(1, "cup", "frozen broccoli")]
    )
    def test__retrieve_manual_menu_ingredient(
        menu, mock_ingredient_formatter, ingredient, quantity, unit, item
    ):
        row = create_menu_row(
            factor=quantity, unit=unit, item=item, item_type="ingredient"
        )
        mock_ingredient_formatter.format_manual_ingredient.return_value = (
            ingredient
        )
        result = menu._retrieve_manual_menu_ingredient(row)
        assert result == MenuIngredient(
            ingredient=ingredient, from_recipe="manual", from_day=row["weekday"]
        )

    @staticmethod
    @pytest.mark.parametrize("factor,recipe_title", [(1, "grilled cheese")])
    def test__retrieve_menu_recipe(
        menu,
        mock_recipe_book,
        recipe_with_recipe_title,
        factor,
        recipe_title,
    ):
        row = create_menu_row(
            factor=factor, item=recipe_title, item_type="recipe"
        )
        mock_recipe_book.get_recipe_by_title.return_value = (
            recipe_with_recipe_title
        )
        result = menu._retrieve_menu_recipe(row)
        assert result == MenuRecipe(
            recipe=recipe_with_recipe_title,
            factor=row["factor"],
            from_day=row["weekday"],
            from_recipe=row["item"],
        )
