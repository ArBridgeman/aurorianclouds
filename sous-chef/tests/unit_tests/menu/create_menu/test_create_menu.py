import numpy as np
import pandas as pd
import pytest
from sous_chef.date.get_due_date import Weekday
from sous_chef.formatter.units import unit_registry
from sous_chef.menu.create_menu._menu_basic import get_weekday_from_short
from tests.unit_tests.util import create_recipe

WEEKDAY = [pytest.param(member, id=member.name) for member in Weekday]


@pytest.fixture
def menu_default(menu_builder):
    menu_builder.add_menu_list(
        [
            menu_builder.create_all_menu_row(
                item="recipe_no_freezing", freeze_factor=0.0
            ),
            menu_builder.create_all_menu_row(
                item="recipe_with_freezing", freeze_factor=0.5
            ),
            menu_builder.create_all_menu_row(
                item="manual ingredient",
                item_type="ingredient",
                eat_factor=1.0,
                eat_unit=unit_registry.package,
            ),
        ]
    )
    return menu_builder.get_menu()


class TestMenu:
    @staticmethod
    def test__add_recipe_columns_nat(menu, menu_builder, mock_recipe_book):
        recipe_title = "recipe_without_cook_time"
        row = menu_builder.create_loaded_menu_row(
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
        assert result["time_total"] is pd.NaT

    @staticmethod
    @pytest.mark.parametrize("weekday", WEEKDAY)
    def test__check_menu_quality(menu, menu_config, weekday):
        menu_config.quality_check.recipe_rating_min = 3.0
        menu_config.quality_check.workday.recipe_unrated_allowed = True
        menu._check_menu_quality(
            weekday_index=weekday.index, recipe=create_recipe(rating=np.nan)
        )
        menu_config.quality_check.workday.recipe_unrated_allowed = False
        menu._check_menu_quality(
            weekday_index=weekday.index,
            recipe=create_recipe(rating=3.0, time_inactive_str="1 min"),
        )

    @staticmethod
    @pytest.mark.parametrize("weekday", WEEKDAY)
    def test__check_menu_quality_ensure_rating_exceed_min(
        menu, menu_config, weekday
    ):
        menu_config.quality_check.recipe_rating_min = 3.0
        # derived exception MenuQualityError
        with pytest.raises(Exception) as error:
            menu._check_menu_quality(
                weekday_index=weekday, recipe=create_recipe(rating=2.5)
            )
        assert (
            str(error.value)
            == "[menu quality] recipe=dummy_title error=rating=2.5 < 3.0"
        )

    @staticmethod
    @pytest.mark.parametrize("weekday", WEEKDAY)
    def test__check_menu_quality_ensure_workday_not_unrated_recipe(
        menu, menu_config, weekday
    ):
        day_type = weekday.day_type

        menu_config.quality_check[day_type].recipe_unrated_allowed = False
        # derived exception MenuQualityError
        with pytest.raises(Exception) as error:
            menu._check_menu_quality(
                weekday_index=weekday.index, recipe=create_recipe(rating=np.nan)
            )
        assert str(error.value) == (
            "[menu quality] recipe=dummy_title "
            f"error=(on {day_type}) unrated recipe"
        )

    @staticmethod
    @pytest.mark.parametrize("weekday", WEEKDAY)
    def test__check_menu_quality_ensure_workday_not_exceed_active_cook_time(
        menu, menu_config, weekday
    ):
        day_type = weekday.day_type

        menu_config.quality_check[day_type].cook_active_minutes_max = 10
        # derived exception MenuQualityError
        with pytest.raises(Exception) as error:
            menu._check_menu_quality(
                weekday_index=weekday.index,
                recipe=create_recipe(time_total_str="15 minutes"),
            )
        assert str(error.value) == (
            "[menu quality] recipe=dummy_title "
            f"error=(on {day_type}) cook_active_minutes=15.0 > 10.0"
        )

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


class TestGetWeekdayFromShort:
    @staticmethod
    @pytest.mark.parametrize(
        "short_day,expected_week_day",
        [("sat", "Saturday"), ("Mon", "Monday"), ("THU", "Thursday")],
    )
    def test_expected_values_succeed(short_day, expected_week_day):
        assert get_weekday_from_short(short_day) == expected_week_day

    @staticmethod
    def test__unknown_date_raise_error():
        # derived exception MenuConfigError
        with pytest.raises(Exception) as error:
            get_weekday_from_short("not-a-day")
        assert str(error.value) == "[menu config error] not-a-day unknown day!"
