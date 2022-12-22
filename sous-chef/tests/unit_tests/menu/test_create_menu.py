import datetime
from dataclasses import dataclass
from typing import Union
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest
from freezegun import freeze_time
from hydra import compose, initialize
from pandas import DataFrame
from pandera.typing.common import DataFrameBase
from sous_chef.formatter.ingredient.format_ingredient import Ingredient
from sous_chef.menu.create_menu import (
    FinalizedMenuSchema,
    Menu,
    MenuIngredient,
    MenuRecipe,
    MenuSchema,
)
from sous_chef.messaging.gsheets_api import GsheetsHelper
from tests.conftest import FROZEN_DATE
from tests.unit_tests.util import create_recipe
from tests.util import assert_equal_series


@dataclass
class MenuBuilder:
    menu: pd.DataFrame = None

    def add_menu_row(self, row: pd.DataFrame):
        if self.menu is None:
            self.menu = row
        else:
            self.menu = pd.concat([self.menu, row], ignore_index=True)

    def add_menu_list(self, menu_row_list: list[pd.DataFrame]):
        for menu_row in menu_row_list:
            self.add_menu_row(menu_row)
        return self

    @staticmethod
    def create_menu_row(
        prep_day_before: int = 0,
        meal_time: str = "dinner",
        item_type: str = "recipe",
        eat_factor: float = 1.0,
        # gsheets has "", whereas read_csv defaults to np.nans
        eat_unit: str = "",
        freeze_factor: float = 0.0,
        defrost: str = "N",
        item: str = "dummy",
        # template matched with cook_days
        loaded_fixed_menu: bool = True,
        # after recipe/ingredient matched
        post_process_recipe: bool = False,
        rating: float = 3.0,  # np.nan, if unrated
        time_total_str: str = np.nan,
    ) -> Union[
        DataFrame, DataFrameBase[MenuSchema], DataFrameBase[FinalizedMenuSchema]
    ]:
        if item_type == "recipe":
            if time_total_str is np.nan:
                time_total_str = "5 min"

        menu = {
            "weekday": "work_day_2",
            "prep_day_before": prep_day_before,
            "meal_time": meal_time,
            "eat_factor": eat_factor,
            "eat_unit": eat_unit,
            "freeze_factor": freeze_factor,
            "defrost": defrost,
            "item": item,
            "type": item_type,
        }
        if not loaded_fixed_menu:
            return pd.DataFrame(menu, index=[0])
        menu.pop("prep_day_before")
        menu["weekday"] = "Friday"
        menu["eat_day"] = pd.Timestamp(
            year=2022, month=1, day=21, hour=17, minute=45, tz="Europe/Berlin"
        )
        menu["make_day"] = menu["eat_day"] - datetime.timedelta(
            days=prep_day_before
        )
        if not post_process_recipe:
            return MenuSchema.validate(pd.DataFrame(menu, index=[0]))
        menu["rating"] = rating
        menu["time_total"] = time_total_str
        menu["uuid"] = "1666465773100"
        menu_df = pd.DataFrame(menu, index=[0])
        menu_df.time_total = pd.to_timedelta(menu_df.time_total)
        return FinalizedMenuSchema.validate(menu_df)

    def get_menu(self) -> pd.DataFrame:
        return self.menu


@pytest.fixture
def menu_builder():
    return MenuBuilder()


@pytest.fixture
def menu_default(menu_builder):
    menu_builder.add_menu_list(
        [
            menu_builder.create_menu_row(
                item="recipe_no_freezing", freeze_factor=0.0
            ),
            menu_builder.create_menu_row(
                item="recipe_with_freezing", freeze_factor=0.5
            ),
            menu_builder.create_menu_row(
                item="manual ingredient",
                item_type="ingredient",
                eat_factor=1.0,
                eat_unit="pkg",
            ),
        ]
    )
    return menu_builder.get_menu()


@pytest.fixture
def mock_gsheets():
    with initialize(version_base=None, config_path="../../../config/messaging"):
        config = compose(config_name="gsheets_api")
        with patch.object(GsheetsHelper, "__post_init__"):
            return Mock(GsheetsHelper(config))


@pytest.fixture
def menu_config():
    with initialize(version_base=None, config_path="../../../config/menu"):
        return compose(config_name="create_menu").create_menu


@pytest.fixture
@freeze_time(FROZEN_DATE)
def menu(
    menu_config,
    mock_gsheets,
    mock_ingredient_formatter,
    mock_recipe_book,
    frozen_due_datetime_formatter,
):
    menu = Menu(
        config=menu_config,
        due_date_formatter=frozen_due_datetime_formatter,
        gsheets_helper=mock_gsheets,
        ingredient_formatter=mock_ingredient_formatter,
        recipe_book=mock_recipe_book,
    )
    return menu


class TestMenu:
    @staticmethod
    @pytest.mark.parametrize("menu_number", [1, 12])
    def test__check_fixed_menu_number(menu, menu_number):
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
    def test__check_fixed_menu_number_raise_value_error(
        menu, menu_number, error_message
    ):
        with pytest.raises(ValueError) as error:
            menu._check_fixed_menu_number(menu_number)
        assert str(error.value) == error_message

    @staticmethod
    def test__add_recipe_columns_nat(menu, menu_builder, mock_recipe_book):
        recipe_title = "recipe_without_cook_time"
        row = menu_builder.create_menu_row(
            item=recipe_title, item_type="recipe"
        ).squeeze()

        recipe_without_time_total = create_recipe(
            title=recipe_title, time_total_str=""
        )
        mock_recipe_book.get_recipe_by_title.return_value = (
            recipe_without_time_total
        )

        result = menu._add_recipe_columns(
            row.copy(deep=True), recipe_without_time_total
        )

        assert result["item"] == recipe_without_time_total.title
        # assert_equal_series(result["time_total"] is pd.NaT

    @staticmethod
    @freeze_time(FROZEN_DATE)
    def test__format_task_and_due_date_list(menu, menu_builder):
        row = menu_builder.create_menu_row(
            post_process_recipe=True,
            item="french onion soup",
            meal_time="dinner",
            time_total_str=pd.to_timedelta("40 min"),
        ).squeeze()
        assert menu._format_task_and_due_date_list(row) == (
            f"{row['item']} (x eat: {row.eat_factor}) [40 min]",
            pd.Timestamp(
                year=2022,
                month=1,
                day=21,
                hour=17,
                minute=5,
                tz="Europe/Berlin",
            ),
        )

    @staticmethod
    @freeze_time(FROZEN_DATE)
    def test__format_task_and_due_date_list_ingredient(menu, menu_builder):
        row = menu_builder.create_menu_row(
            post_process_recipe=True,
            item="fries",
            item_type="ingredient",
            meal_time="dinner",
        ).squeeze()
        assert menu._format_task_and_due_date_list(row) == (
            f"{row['item']} (x eat: {row.eat_factor}) [20 min]",
            pd.Timestamp(
                year=2022,
                month=1,
                day=21,
                hour=17,
                minute=25,
                tz="Europe/Berlin",
            ),
        )

    @staticmethod
    @freeze_time(FROZEN_DATE)
    def test__format_task_and_due_date_list_with_freeze_factor(
        menu, menu_builder
    ):
        recipe_title = "french onion soup"
        row = menu_builder.create_menu_row(
            post_process_recipe=True,
            item=recipe_title,
            meal_time="dinner",
            freeze_factor=0.5,
        ).squeeze()
        assert menu._format_task_and_due_date_list(row) == (
            "french onion soup (x eat: 1.0, x freeze: 0.5) [5 min]",
            pd.Timestamp(
                year=2022,
                month=1,
                day=21,
                hour=17,
                minute=40,
                tz="Europe/Berlin",
            ),
        )

    @staticmethod
    @pytest.mark.parametrize(
        "cook_day,expected_week_day", [("weekend_1", "Saturday")]
    )
    def test__get_cook_day_as_weekday(menu, cook_day, expected_week_day):
        assert menu._get_cook_day_as_weekday(cook_day) == expected_week_day

    @staticmethod
    @pytest.mark.parametrize("rating", [np.nan])
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
                "action": "print out ingredients",
                "recipe_title": "dummy_title",
            }
        ]
        assert out == "1 dummy ingredient\n"
        assert err == ""

    @staticmethod
    @pytest.mark.parametrize("rating", [np.nan])
    def test__inspect_unrated_recipe_turned_off(
        capsys,
        log,
        menu_config,
        menu,
        rating,
    ):
        menu_config.run_mode.with_inspect_unrated_recipe = False

        menu._inspect_unrated_recipe(create_recipe(rating=rating))
        out, err = capsys.readouterr()

        assert log.events == []
        assert out == ""
        assert err == ""

    @staticmethod
    @pytest.mark.parametrize(
        "recipe_title,time_total_str",
        [("garlic aioli", "5 minutes"), ("banana souffle", "30 minutes")],
    )
    def test__process_menu_recipe(
        menu, menu_builder, mock_recipe_book, recipe_title, time_total_str
    ):
        row = menu_builder.create_menu_row(
            item=recipe_title, item_type="recipe", loaded_fixed_menu=True
        ).squeeze()

        recipe_with_time_total = create_recipe(
            title=recipe_title, time_total_str=time_total_str
        )
        mock_recipe_book.get_recipe_by_title.return_value = (
            recipe_with_time_total
        )

        result = menu._process_menu(row.copy(deep=True))

        assert_equal_series(
            result,
            menu_builder.create_menu_row(
                post_process_recipe=True,
                item=recipe_title,
                item_type="recipe",
                time_total_str=pd.to_timedelta(time_total_str),
            ).squeeze(),
        )

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
        ).squeeze()

        ingredient = Ingredient(quantity=quantity, unit=unit, item=item)
        mock_ingredient_formatter.format_manual_ingredient.return_value = (
            ingredient
        )

        result = menu._process_menu(row.copy(deep=True))
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

        result = menu._process_menu(row.copy(deep=True))

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

    @staticmethod
    @pytest.mark.parametrize(
        "quantity,unit,item", [(1.0, "cup", "frozen broccoli")]
    )
    def test__retrieve_manual_menu_ingredient(
        menu, menu_builder, mock_ingredient_formatter, quantity, unit, item
    ):
        row = menu_builder.create_menu_row(
            eat_factor=quantity,
            eat_unit=unit,
            item=item,
            item_type="ingredient",
        ).squeeze()

        ingredient = Ingredient(quantity=quantity, unit=unit, item=item)
        mock_ingredient_formatter.format_manual_ingredient.return_value = (
            ingredient
        )
        result = menu._retrieve_manual_menu_ingredient(row)
        assert result == MenuIngredient(
            ingredient=ingredient, from_recipe="manual", for_day=row["make_day"]
        )

    @staticmethod
    @pytest.mark.parametrize(
        "recipe_title",
        ["grilled cheese", "garlic aioli"],
    )
    def test__retrieve_menu_recipe(
        menu,
        menu_builder,
        mock_recipe_book,
        recipe_title,
    ):
        row = menu_builder.create_menu_row(
            item=recipe_title, item_type="recipe"
        ).squeeze()
        recipe_with_recipe_title = create_recipe(title=recipe_title)
        mock_recipe_book.get_recipe_by_title.return_value = (
            recipe_with_recipe_title
        )

        result = menu._retrieve_menu_recipe(row)

        assert result == MenuRecipe(
            recipe=recipe_with_recipe_title,
            eat_factor=row["eat_factor"],
            freeze_factor=0.0,
            for_day=row["make_day"],
            from_recipe=row["item"],
        )

    @staticmethod
    def test__validate_menu_schema(menu, menu_builder):
        menu.dataframe = menu_builder.create_menu_row(loaded_fixed_menu=True)
        menu._validate_menu_schema()
