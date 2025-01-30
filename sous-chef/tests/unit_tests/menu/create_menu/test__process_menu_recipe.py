import numpy as np
import pandas as pd
import pytest
from sous_chef.date.get_due_date import Weekday
from sous_chef.formatter.units import unit_registry
from sous_chef.menu.create_menu.exceptions import (
    MenuFutureError,
    MenuQualityError,
)
from sous_chef.menu.create_menu.models import Type, YesNo
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


class TestMenuRecipeProcessor:
    @staticmethod
    def test__get_cook_prep_datetime_nat(menu_recipe_processor, menu_builder):
        recipe_title = "recipe_without_cook_time"
        row = menu_builder.create_loaded_menu_row(
            item=recipe_title, item_type=Type.recipe.value
        ).squeeze()

        recipe_without_time_total = create_recipe(
            title=recipe_title, time_total_str=""
        )

        result = menu_recipe_processor._get_cook_prep_datetime(
            row.copy(deep=True), recipe_without_time_total
        )
        assert result == (pd.NaT, pd.NaT)

    @staticmethod
    @pytest.mark.parametrize("weekday", WEEKDAY)
    def test__check_menu_quality(menu_recipe_processor, menu_config, weekday):
        menu_config.quality_check.recipe_rating_min = 3.0
        menu_config.quality_check.workday.recipe_unrated_allowed = True
        menu_recipe_processor._check_menu_quality(
            weekday_index=weekday.index, recipe=create_recipe(rating=np.nan)
        )
        menu_config.quality_check.workday.recipe_unrated_allowed = False
        menu_recipe_processor._check_menu_quality(
            weekday_index=weekday.index,
            recipe=create_recipe(rating=3.0, time_inactive_str="1 min"),
        )

    @staticmethod
    @pytest.mark.parametrize("weekday", WEEKDAY)
    def test__check_menu_quality_ensure_rating_exceed_min(
        menu_recipe_processor, menu_config, weekday
    ):
        menu_config.quality_check.recipe_rating_min = 3.0
        with pytest.raises(MenuQualityError) as error:
            menu_recipe_processor._check_menu_quality(
                weekday_index=weekday, recipe=create_recipe(rating=2.5)
            )
        assert (
            str(error.value)
            == "[menu quality] recipe=dummy_title error=rating=2.5 < 3.0"
        )

    @staticmethod
    @pytest.mark.parametrize("weekday", WEEKDAY)
    def test__check_menu_quality_ensure_workday_not_unrated_recipe(
        menu_recipe_processor, menu_config, weekday
    ):
        day_type = weekday.day_type

        menu_config.quality_check[day_type].recipe_unrated_allowed = False
        with pytest.raises(MenuQualityError) as error:
            menu_recipe_processor._check_menu_quality(
                weekday_index=weekday.index, recipe=create_recipe(rating=np.nan)
            )
        assert str(error.value) == (
            "[menu quality] recipe=dummy_title "
            f"error=(on {day_type}) unrated recipe"
        )

    @staticmethod
    @pytest.mark.parametrize("weekday", WEEKDAY)
    def test__check_menu_quality_ensure_workday_not_exceed_active_cook_time(
        menu_recipe_processor, menu_config, weekday
    ):
        day_type = weekday.day_type

        menu_config.quality_check[day_type].cook_active_minutes_max = 10
        with pytest.raises(MenuQualityError) as error:
            menu_recipe_processor._check_menu_quality(
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
        menu_recipe_processor,
        rating,
    ):
        menu_config.run_mode.with_inspect_unrated_recipe = True

        menu_recipe_processor._inspect_unrated_recipe(
            create_recipe(rating=rating)
        )
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
        menu_recipe_processor,
        rating,
    ):
        menu_config.run_mode.with_inspect_unrated_recipe = False

        menu_recipe_processor._inspect_unrated_recipe(
            create_recipe(rating=rating)
        )

        assert log.events == []
        assert capsys.readouterr() == ("", "")


class TestRetrieveRecipe:
    @staticmethod
    def test_passes_through_if_override_active(
        menu_recipe_processor, default_menu_row_recipe_pair
    ):
        menu_row, recipe = default_menu_row_recipe_pair
        menu_row.override_check = YesNo.yes.value
        list_used_uuids = [recipe.uuid]

        menu_recipe_processor.menu_history_uuids = tuple(list_used_uuids)
        menu_recipe_processor.future_menu_uuids = tuple(list_used_uuids)
        menu_recipe_processor.processed_uuids = list_used_uuids

        entry = menu_recipe_processor.retrieve_recipe(row=menu_row)

        assert entry.shape == (1, 13)

    @staticmethod
    def test_when_recipe_in_processed_uuid_list_toss_error(
        menu_recipe_processor, default_menu_row_recipe_pair
    ):
        menu_row, recipe = default_menu_row_recipe_pair

        menu_recipe_processor.processed_uuids = [recipe.uuid]

        with pytest.raises(MenuQualityError) as error:
            menu_recipe_processor.retrieve_recipe(row=menu_row)

        assert "recipe already processed in menu" in str(error.value)

    @staticmethod
    def test_when_recipe_in_menu_history_uuids_toss_error(
        menu_recipe_processor, default_menu_row_recipe_pair
    ):
        menu_row, recipe = default_menu_row_recipe_pair
        menu_recipe_processor.menu_history_uuids = tuple([recipe.uuid])

        with pytest.raises(Exception) as error:
            menu_recipe_processor.retrieve_recipe(row=menu_row)

        assert "[in recent menu history]" in str(error.value)

    @staticmethod
    def test_when_recipe_in_future_uuids_toss_error(
        menu_recipe_processor, default_menu_row_recipe_pair
    ):
        menu_row, recipe = default_menu_row_recipe_pair
        menu_recipe_processor.future_menu_uuids = tuple([recipe.uuid])

        with pytest.raises(MenuFutureError) as error:
            menu_recipe_processor.retrieve_recipe(row=menu_row)

        assert "[future menu]" in str(error.value)
