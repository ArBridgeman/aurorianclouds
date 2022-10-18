import datetime
from dataclasses import dataclass
from pathlib import Path
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
from sous_chef.menu.create_menu import (
    FinalizedMenuSchema,
    Menu,
    MenuIngredient,
    MenuRecipe,
)
from sous_chef.messaging.gsheets_api import GsheetsHelper
from tests.conftest import FROZEN_DATE
from tests.unit_tests.util import create_recipe
from tests.util import assert_equal_dataframe_backup, assert_equal_series


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
        weekday: str = "work_day_2",
        meal_time: str = "dinner",
        item_type: str = "recipe",
        eat_factor: float = 1.0,
        # gsheets has "", whereas read_csv defaults to np.nans
        eat_unit: str = "",
        freeze_factor: float = 0.0,
        item: str = "dummy",
        # template matched with cook_days
        loaded_fixed_menu: bool = True,
        # after recipe/ingredient matched
        post_process_recipe: bool = False,
        rating: float = np.nan,
        total_cook_time_str: str = np.nan,
    ) -> pd.DataFrame:
        if item_type == "recipe":
            if total_cook_time_str is np.nan:
                total_cook_time_str = "5 min"
            if rating is np.nan:
                rating = 0.0

        menu = {
            "weekday": weekday,
            "meal_time": meal_time,
            "eat_factor": eat_factor,
            "eat_unit": eat_unit,
            "freeze_factor": freeze_factor,
            "item": item,
            "type": item_type,
        }
        if not loaded_fixed_menu:
            return pd.DataFrame(menu, index=[0])
        menu["weekday"] = "Friday"
        if not post_process_recipe:
            return pd.DataFrame(menu, index=[0])
        menu["rating"] = rating
        menu["total_cook_time"] = total_cook_time_str
        menu_df = pd.DataFrame(menu, index=[0])
        menu_df.total_cook_time = pd.to_timedelta(menu_df.total_cook_time)
        FinalizedMenuSchema.validate(menu_df)
        return menu_df

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
def mock_ingredient_formatter():
    with initialize(version_base=None, config_path="../../../config/formatter"):
        config = compose(config_name="format_ingredient")
        return Mock(IngredientFormatter(config, None, None))


@pytest.fixture
def menu_config(tmp_path):
    with initialize(version_base=None, config_path="../../../config/menu"):
        config = compose(config_name="create_menu").create_menu
        config.local.file_path = str(tmp_path / "menu-tmp.csv")
        return config


@pytest.fixture
@freeze_time(FROZEN_DATE)
def menu(
    menu_config,
    mock_ingredient_formatter,
    mock_recipe_book,
    frozen_due_datetime_formatter,
):
    menu = Menu(
        ingredient_formatter=mock_ingredient_formatter,
        config=menu_config,
        recipe_book=mock_recipe_book,
    )
    menu.due_date_formatter = frozen_due_datetime_formatter
    return menu


class TestMenu:
    @staticmethod
    def test_finalize_fixed_menu(
        menu, menu_config, menu_builder, mock_gsheets, mock_recipe_book
    ):
        menu_config.fixed.menu_number = 1
        mock_recipe_book.get_recipe_by_title.return_value = create_recipe()
        mock_gsheets.get_worksheet.return_value = menu_builder.create_menu_row(
            loaded_fixed_menu=False
        )
        menu.finalize_fixed_menu(mock_gsheets)
        assert Path(menu_config.local.file_path).exists()

    @staticmethod
    def test_load_local_menu(menu, menu_builder):
        fake_menu = menu_builder.create_menu_row(post_process_recipe=True)
        menu.dataframe = fake_menu
        menu._save_menu()
        menu.load_local_menu()
        assert_equal_dataframe_backup(menu.dataframe, fake_menu)

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
    def test__add_recipe_cook_time_and_rating_nat(
        menu, menu_builder, mock_recipe_book
    ):
        recipe_title = "recipe_without_cook_time"
        row = menu_builder.create_menu_row(
            item=recipe_title, item_type="recipe"
        ).squeeze()

        recipe_without_total_cook_time = create_recipe(
            title=recipe_title, total_cook_time_str=""
        )
        mock_recipe_book.get_recipe_by_title.return_value = (
            recipe_without_total_cook_time
        )

        result = menu._add_recipe_cook_time_and_rating(row.copy(deep=True))

        assert result["item"] == recipe_without_total_cook_time.title
        assert result["total_cook_time"] is pd.NaT

    @staticmethod
    @freeze_time(FROZEN_DATE)
    def test__format_task_and_due_date_list(menu, menu_builder):
        row = menu_builder.create_menu_row(
            post_process_recipe=True,
            item="french onion soup",
            weekday="Friday",
            meal_time="dinner",
            total_cook_time_str=pd.to_timedelta("40 min"),
        ).squeeze()
        assert menu._format_task_and_due_date_list(row) == (
            f"{row['item']} (x eat: {row.eat_factor}) [40 min]",
            datetime.datetime(2022, 1, 21, 17, 35),
        )

    @staticmethod
    @freeze_time(FROZEN_DATE)
    def test__format_task_and_due_date_list_ingredient(menu, menu_builder):
        row = menu_builder.create_menu_row(
            post_process_recipe=True,
            item="fries",
            item_type="ingredient",
            weekday="Friday",
            meal_time="dinner",
        ).squeeze()
        assert menu._format_task_and_due_date_list(row) == (
            f"{row['item']} (x eat: {row.eat_factor}) [20 min]",
            datetime.datetime(2022, 1, 21, 17, 55),
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
            weekday="Friday",
            meal_time="dinner",
            freeze_factor=0.5,
        ).squeeze()
        assert menu._format_task_and_due_date_list(row) == (
            "french onion soup (x eat: 1.0, x freeze: 0.5) [5 min]",
            datetime.datetime(2022, 1, 21, 18, 10),
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
    @pytest.mark.parametrize(
        "cook_day,expected_week_day", [("weekend_1", "Saturday")]
    )
    def test__get_cook_day_as_weekday(menu, cook_day, expected_week_day):
        assert menu._get_cook_day_as_weekday(cook_day) == expected_week_day

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
    @pytest.mark.parametrize("rating", [0.0])
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
        "recipe_title,total_cook_time_str",
        [("garlic aioli", "5 minutes"), ("banana souffle", "1 hour 4 minutes")],
    )
    def test__process_menu_recipe(
        menu, menu_builder, mock_recipe_book, recipe_title, total_cook_time_str
    ):
        row = menu_builder.create_menu_row(
            item=recipe_title, item_type="recipe", loaded_fixed_menu=True
        ).squeeze()

        recipe_with_total_cook_time = create_recipe(
            title=recipe_title, total_cook_time_str=total_cook_time_str
        )
        mock_recipe_book.get_recipe_by_title.return_value = (
            recipe_with_total_cook_time
        )

        result = menu._process_menu(row.copy(deep=True))

        assert_equal_series(
            result,
            menu_builder.create_menu_row(
                post_process_recipe=True,
                item=recipe_title,
                item_type="recipe",
                total_cook_time_str=pd.to_timedelta(total_cook_time_str),
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
                total_cook_time_str=recipe.total_cook_time,
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
            {
                "event": "[unrated recipe]",
                "level": "warning",
                "action": "print out ingredient_field",
                "recipe_title": "dummy_recipe",
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
            ingredient=ingredient, from_recipe="manual", from_day=row["weekday"]
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
            from_day=row["weekday"],
            from_recipe=row["item"],
        )

    @staticmethod
    def test__save_menu(menu, menu_builder, menu_config):
        menu.dataframe = menu_builder.create_menu_row(post_process_recipe=True)
        menu._save_menu()
        assert Path(menu_config.local.file_path).exists()

    @staticmethod
    def test__validate_menu_schema(menu, menu_builder):
        menu.dataframe = menu_builder.create_menu_row(loaded_fixed_menu=True)
        menu._validate_menu_schema()
