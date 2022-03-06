import datetime
from pathlib import Path
from typing import Union
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest
from freezegun import freeze_time
from hydra import compose, initialize
from sous_chef.formatter.ingredient.format_ingredient import (
    Ingredient,
    IngredientFormatter,
)
from sous_chef.menu.create_menu import Menu, MenuIngredient, MenuRecipe
from sous_chef.messaging.gsheets_api import GsheetsHelper
from tests.unit_tests.util import assert_equal_dataframe, create_recipe

FROZEN_DATE = "2022-01-14"


def create_menu_row(
    weekday: str = "Friday",
    meal_time: str = "dinner",
    item_type: str = "recipe",
    eat_factor: float = 1.0,
    eat_unit: str = "",
    # gsheets has "", whereas read_csv defaults to np.nans
    freeze_factor: Union[float, str] = "",
    item: str = "dummy",
    grocery_list: str = "Y",
    menu_list: str = "Y",
):
    return pd.Series(
        {
            "weekday": weekday,
            "meal_time": meal_time,
            "eat_factor": eat_factor,
            "eat_unit": eat_unit,
            "freeze_factor": freeze_factor,
            "item": item,
            "type": item_type,
            "grocery_list": grocery_list,
            "menu_list": menu_list,
        }
    )


@pytest.fixture
def menu_default():
    return pd.concat(
        [
            create_menu_row(item="recipe_no_freezing"),
            create_menu_row(item="recipe_with_freezing", freeze_factor=0.5),
            create_menu_row(
                item="manual ingredient",
                item_type="ingredient",
                eat_factor=1,
                eat_unit="pkg",
            ),
        ],
        axis=1,
    ).T


@pytest.fixture
def mock_gsheets():
    with initialize(config_path="../../../config/messaging"):
        config = compose(config_name="gsheets_api")
        with patch.object(GsheetsHelper, "__post_init__"):
            return Mock(GsheetsHelper(config))


@pytest.fixture
def mock_ingredient_formatter():
    with initialize(config_path="../../../config/formatter"):
        config = compose(config_name="format_ingredient")
        return Mock(IngredientFormatter(config, None, None))


@pytest.fixture
def menu_config(tmp_path):
    with initialize(config_path="../../../config"):
        config = compose(config_name="menu").menu
        config.local.file_path = str(tmp_path / "menu-tmp.csv")
        return config


@pytest.fixture
def menu(menu_config, mock_ingredient_formatter, mock_recipe_book):
    return Menu(
        ingredient_formatter=mock_ingredient_formatter,
        config=menu_config,
        recipe_book=mock_recipe_book,
    )


class TestMenu:
    @staticmethod
    def test_finalize_fixed_menu(menu, menu_config, menu_default, mock_gsheets):
        menu_config.fixed.menu_number = 1
        mock_gsheets.get_sheet_as_df.return_value = menu_default
        menu.finalize_fixed_menu(mock_gsheets)
        assert Path(menu_config.local.file_path).exists()

    @staticmethod
    @pytest.mark.parametrize(
        "quantity,unit,item,recipe_title,total_cook_time_str",
        [(1, "cup", "frozen broccoli", "garlic aioli", "5 minutes")],
    )
    def test_get_menu_for_grocery_list(
        menu,
        mock_ingredient_formatter,
        mock_recipe_book,
        quantity,
        unit,
        item,
        recipe_title,
        total_cook_time_str,
    ):
        recipe_with_recipe_title = create_recipe(title=recipe_title)
        recipe = create_menu_row(
            item=recipe_title, item_type="recipe", freeze_factor=0.5
        )
        ingredient = Ingredient(quantity=quantity, unit=unit, item=item)
        menu.dataframe = pd.concat(
            [
                recipe,
                create_menu_row(
                    eat_factor=quantity,
                    eat_unit=unit,
                    item=item,
                    item_type="ingredient",
                ),
            ],
            axis=1,
        ).T
        menu._save_menu()
        mock_ingredient_formatter.format_manual_ingredient.return_value = (
            ingredient
        )
        mock_recipe_book.get_recipe_by_title.return_value = (
            recipe_with_recipe_title
        )

        manual_ingredient_list, recipe_list = menu.get_menu_for_grocery_list()

        assert manual_ingredient_list == [
            MenuIngredient(
                ingredient=ingredient, from_day="Friday", from_recipe="manual"
            )
        ]
        assert recipe_list == [
            MenuRecipe(
                recipe=recipe_with_recipe_title,
                eat_factor=recipe["eat_factor"],
                freeze_factor=recipe["freeze_factor"],
                from_day=recipe["weekday"],
                from_recipe=recipe["item"],
            )
        ]

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
    @pytest.mark.parametrize(
        "recipe_title,total_cook_time_str",
        [("garlic aioli", "5 minutes"), ("banana souffle", "1 hour 4 minutes")],
    )
    def test__check_recipe_and_add_cooking_time(
        menu,
        mock_recipe_book,
        recipe_title,
        total_cook_time_str,
    ):
        recipe_with_total_cook_time = create_recipe(
            title=recipe_title, total_cook_time_str=total_cook_time_str
        )
        row = create_menu_row(item=recipe_title, item_type="recipe")
        mock_recipe_book.get_recipe_by_title.return_value = (
            recipe_with_total_cook_time
        )

        result = menu._check_recipe_and_add_cooking_time(row)

        assert result["item"] == recipe_with_total_cook_time.title
        assert (
            result["total_cook_time"]
            == recipe_with_total_cook_time.total_cook_time
        )

    @staticmethod
    def test__check_recipe_and_add_cooking_time_nat(menu, mock_recipe_book):
        recipe_title = "recipe_without_cooktime"
        recipe_with_total_cook_time = create_recipe(
            title=recipe_title, total_cook_time_str=""
        )
        row = create_menu_row(item=recipe_title, item_type="recipe")
        mock_recipe_book.get_recipe_by_title.return_value = (
            recipe_with_total_cook_time
        )

        result = menu._check_recipe_and_add_cooking_time(row)

        assert result["item"] == recipe_with_total_cook_time.title
        assert result["total_cook_time"] is pd.NaT

    @staticmethod
    @freeze_time(FROZEN_DATE)
    def test__format_task_and_due_date_list(menu):
        row = create_menu_row(
            item="french onion soup", weekday="Friday", meal_time="dinner"
        )
        row["total_cook_time"] = datetime.timedelta(minutes=40)
        assert menu._format_task_and_due_date_list(row) == (
            "french onion soup (x eat: 1.0) [40 min]",
            datetime.datetime(2022, 1, 21, 17, 35),
        )

    @staticmethod
    @freeze_time(FROZEN_DATE)
    def test__format_menu_task_with_freeze_factor(menu):
        row = create_menu_row(
            item="french onion soup",
            weekday="Monday",
            meal_time="dinner",
            freeze_factor=0.5,
        )
        row["total_cook_time"] = ""
        assert menu._format_task_and_due_date_list(row) == (
            "french onion soup (x eat: 1.0, x freeze: 0.5) [20 min]",
            datetime.datetime(2022, 1, 17, 17, 55),
        )

    @staticmethod
    @pytest.mark.parametrize(
        "total_cook_time,expected_result",
        [
            ("", 20),
            (None, 20),
            ("nan", 20),
            (np.Inf, 20),
            (np.nan, 20),
            # expected type from recipe book
            (pd.NaT, 20),
            (datetime.timedelta(seconds=25), 0),
            (datetime.timedelta(minutes=-25), 20),
            (datetime.timedelta(minutes=25), 25),
            (datetime.timedelta(hours=1, minutes=25), 85),
        ],
    )
    def test__get_cooking_time_min_default_time(
        menu, total_cook_time, expected_result
    ):
        assert menu._get_cooking_time_min(total_cook_time) == expected_result

    @staticmethod
    @pytest.mark.parametrize("rating", [0.0])
    def test__inspect_unrated_recipe(
        capsys,
        log,
        menu_config,
        menu,
        rating,
    ):
        menu_config.run_mode.with_inspect_unrated_recipe = True

        menu._inspect_unrated_recipe(create_recipe(rating=rating))
        out, err = capsys.readouterr()

        assert log.events == [
            {
                "event": "[unrated recipe]",
                "level": "warning",
                "action": "print out ingredient_field",
                "recipe_title": "dummy_title",
            }
        ]
        assert out == "1 dummy text\n"
        assert err == ""

    @staticmethod
    def test__load_local_menu(menu, menu_default):
        menu.dataframe = menu_default
        menu._save_menu()
        assert_equal_dataframe(menu._load_local_menu(), menu_default)

    @staticmethod
    @pytest.mark.parametrize(
        "quantity,unit,item", [(1, "cup", "frozen broccoli")]
    )
    def test__retrieve_manual_menu_ingredient(
        menu, mock_ingredient_formatter, quantity, unit, item
    ):
        ingredient = Ingredient(quantity=quantity, unit=unit, item=item)
        row = create_menu_row(
            eat_factor=quantity,
            eat_unit=unit,
            item=item,
            item_type="ingredient",
        )
        mock_ingredient_formatter.format_manual_ingredient.return_value = (
            ingredient
        )
        result = menu._retrieve_manual_menu_ingredient(row)
        assert result == MenuIngredient(
            ingredient=ingredient, from_recipe="manual", from_day=row["weekday"]
        )

    @staticmethod
    @pytest.mark.parametrize(
        "recipe_title",
        [("grilled cheese"), ("garlic aioli")],
    )
    def test__retrieve_menu_recipe(
        menu,
        mock_recipe_book,
        recipe_title,
    ):
        recipe_with_recipe_title = create_recipe(title=recipe_title)
        row = create_menu_row(item=recipe_title, item_type="recipe")
        mock_recipe_book.get_recipe_by_title.return_value = (
            recipe_with_recipe_title
        )

        result = menu._retrieve_menu_recipe(row)

        assert result == MenuRecipe(
            recipe=recipe_with_recipe_title,
            eat_factor=row["eat_factor"],
            freeze_factor=0.0,
            from_day=row["weekday"],
            from_recipe=row["item"],
        )

    @staticmethod
    def test__save_menu(menu, menu_config, menu_default):
        menu.dataframe = menu_default
        menu._save_menu()
        assert Path(menu_config.local.file_path).exists()
