import builtins
import datetime
from typing import Optional
from unittest import mock
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from pint import Unit
from pytz import timezone
from sous_chef.formatter.format_unit import UnitFormatter, unit_registry
from sous_chef.formatter.ingredient.format_ingredient import Ingredient
from sous_chef.grocery_list.generate_grocery_list.generate_grocery_list import (
    GroceryListIncompleteError,
)
from sous_chef.menu.create_menu._for_grocery_list import MenuRecipe
from sous_chef.recipe_book.recipe_util import RecipeSchema
from tests.unit_tests.util import create_recipe

from utilities.testing.pandas_util import (
    assert_equal_dataframe,
    assert_equal_series,
)


def create_grocery_list_row(
    item: str = "dummy ingredient",
    pint_unit: Unit = None,
    is_optional: bool = False,
    quantity: float = 1.0,
    is_staple: bool = False,
    food_group: str = "Vegetables",
    store: str = "grocery store",
    plural_ending: str = "s",
    from_recipe: str = "dummy recipe",
    for_day: datetime = datetime.datetime(
        year=2022, month=1, day=20, tzinfo=timezone("UTC")
    ),
    aisle_group: str = None,
):
    return pd.Series(
        {
            "item": item,
            "pint_unit": pint_unit,
            "is_optional": is_optional,
            "quantity": quantity,
            "is_staple": is_staple,
            "food_group": food_group,
            "store": store,
            "item_plural": item + plural_ending,
            "from_recipe": from_recipe,
            "for_day": for_day,
            "aisle_group": aisle_group,
        }
    )


def create_ingredient_and_grocery_entry_raw(
    item: str = "zucchini",
    quantity: float = 1.0,
    factor: float = 1.0,
    is_optional: bool = False,
    is_staple: bool = False,
    pint_unit: Unit = unit_registry.dimensionless,
    group: str = "Vegetables",
    plural_ending: str = "s",
    store: str = "grocery store",
    barcode: str = "4002015511713",
    recipe_factor: float = 1.0,
    from_recipe: str = "dummy recipe",
    for_day: datetime.datetime = datetime.datetime(
        year=2022, month=1, day=27, tzinfo=timezone("UTC")
    ),
    for_day_str: str = "Thu",
    # frozen anchor date is Friday & second group includes vegetables
    shopping_date: datetime.date = datetime.date(year=2022, month=1, day=24),
) -> (Ingredient, pd.DataFrame):
    UnitFormatter.get_unit_as_abbreviated_str(pint_unit)

    ingredient = Ingredient(
        quantity=quantity,
        pint_unit=pint_unit,
        item=item,
        factor=factor,
        is_optional=is_optional,
        is_staple=is_staple,
        group=group,
        item_plural=item + plural_ending,
        store=store,
        barcode=barcode,
    )
    grocery_list_raw = pd.DataFrame(
        {
            "quantity": quantity * recipe_factor,
            "pint_unit": pint_unit,
            "item": item,
            "is_staple": is_staple,
            "is_optional": is_optional,
            "food_group": group,
            "item_plural": item + plural_ending,
            "store": store,
            "barcode": barcode,
            "from_recipe": from_recipe,
            "for_day": for_day,
            "for_day_str": for_day_str,
            "shopping_date": shopping_date,
        },
        index=[0],
    )
    return ingredient, grocery_list_raw


def create_menu_recipe(
    recipe: Optional[RecipeSchema] = None,
    from_recipe: str = "dummy recipe",
    eat_factor: float = 1.0,
    freeze_factor: float = 0.0,
    for_day=datetime.datetime(
        year=2022, month=1, day=27, tzinfo=timezone("UTC")
    ),
):
    if recipe is None:
        recipe = create_recipe(title=from_recipe)
    return MenuRecipe(
        recipe=recipe,
        eat_factor=eat_factor,
        freeze_factor=freeze_factor,
        for_day=for_day,
        from_recipe=from_recipe,
    )


class TestGroceryList:
    @staticmethod
    def test_upload_grocery_list_to_todoist(grocery_list, mock_todoist_helper):
        grocery_list.has_errors = ["[Dummy Error] Something happened"]
        with pytest.raises(GroceryListIncompleteError) as error:
            grocery_list.upload_grocery_list_to_todoist(
                todoist_helper=mock_todoist_helper
            )
        assert (
            str(error.value)
            == "[grocery list had errors] will not send to ToDoist until fixed"
        )

    @staticmethod
    @pytest.mark.parametrize(
        "number_can_to_freeze, freeze_text", [(1, "1 can"), (2, "2 cans")]
    )
    def test__format_bean_prep_task_str(
        grocery_list, number_can_to_freeze, freeze_text
    ):
        row = pd.Series(
            {
                "quantity": 210,
                "pint_unit": unit_registry.gram,
                "item": "black beans",
                "is_optional": False,
                "item_plural": "black beans",
            }
        )
        assert (
            grocery_list._format_bean_prep_task_str(row, number_can_to_freeze)
            == f"[BEAN PREP] black beans, 210 g (freeze: {freeze_text})"
        )

    @staticmethod
    def test__format_bean_soak_task_str(grocery_list):
        row = pd.Series(
            {
                "quantity": 210,
                "pint_unit": unit_registry.gram,
                "item": "black beans",
                "is_optional": False,
                "item_plural": "black beans",
            }
        )
        assert (
            grocery_list._format_bean_soak_task_str(row)
            == "[BEAN SOAK] black beans, 210 g"
        )

    @staticmethod
    @pytest.mark.parametrize(
        "quantity,pint_unit,item,is_optional,"
        "plural_ending,aisle_group,expected_result",
        [
            (1, None, "zucchini", False, "s", "grocery store", "zucchini, 1"),
            (
                1,
                unit_registry.cup,
                "rice",
                False,
                "",
                "grocery store",
                "rice, 1 cup",
            ),
            (
                1,
                unit_registry.cup,
                "zucchini",
                True,
                "s",
                "grocery store",
                "zucchinis, 1 cup (optional)",
            ),
            (
                1,
                unit_registry.cup,
                "rice",
                True,
                "",
                "grocery store",
                "rice, 1 cup (optional)",
            ),
            (2, None, "zucchini", False, "s", "grocery store", "zucchinis, 2"),
            (
                2,
                unit_registry.cup,
                "rice",
                False,
                "",
                "grocery store",
                "rice, 2 cups",
            ),
            (
                1,
                None,
                "baguette",
                False,
                "s",
                "Lillehus",
                "[Lillehus] baguette, 1",
            ),
        ],
    )
    def test__format_ingredient_str(
        grocery_list,
        quantity,
        pint_unit,
        item,
        is_optional,
        plural_ending,
        aisle_group,
        expected_result,
    ):
        ingredient = pd.Series(
            {
                "quantity": quantity,
                "pint_unit": pint_unit,
                "item": item,
                "is_optional": is_optional,
                "item_plural": item + plural_ending,
                "aisle_group": aisle_group,
            }
        )
        assert (
            grocery_list._format_ingredient_str(ingredient) == expected_result
        )

    @staticmethod
    @pytest.mark.parametrize(
        "larger_pint_unit,second_pint_unit,expected_quantity",
        [
            (unit_registry.cup, unit_registry.tbsp, [1.0, 0.06]),
            (unit_registry.kg, unit_registry.oz, [1.0, 0.03]),
        ],
    )
    def test__get_group_in_same_pint_unit(
        grocery_list, larger_pint_unit, second_pint_unit, expected_quantity
    ):
        group = pd.DataFrame(
            {
                "quantity": [1.0, 1.0],
                "pint_unit": [larger_pint_unit, second_pint_unit],
            }
        )

        result = grocery_list._get_group_in_same_pint_unit(group)
        assert np.all(result.quantity.values == expected_quantity)
        assert np.all(result.pint_unit.values == [larger_pint_unit] * 2)

    @staticmethod
    @pytest.mark.parametrize(
        "for_day, food_group, expected_result",
        [
            (  # Monday
                datetime.datetime(
                    year=2022, month=1, day=24, tzinfo=timezone("UTC")
                ),
                "vegetables",
                datetime.date(year=2022, month=1, day=20),
            ),
            (
                datetime.datetime(
                    year=2022, month=1, day=21, tzinfo=timezone("UTC")
                ),
                "vegetables",
                datetime.date(year=2022, month=1, day=20),
            ),  # Friday
            (
                datetime.datetime(
                    year=2022, month=1, day=27, tzinfo=timezone("UTC")
                ),
                "Vegetables",
                datetime.date(year=2022, month=1, day=27),
            ),  # Thursday
            (
                datetime.datetime(
                    year=2022, month=1, day=27, tzinfo=timezone("UTC")
                ),
                "Fruits",
                datetime.date(year=2022, month=1, day=20),
            ),  # Thursday
        ],
    )
    def test__get_on_second_shopping_day(
        grocery_list,
        for_day,
        food_group,
        expected_result,
        frozen_due_datetime_formatter,
    ):
        grocery_list.secondary_shopping_date = datetime.date(
            year=2022, month=1, day=27
        )
        grocery_list.primary_shopping_date = datetime.date(
            year=2022, month=1, day=20
        )
        # only vegetable entries on Fri., Sat., Sun. should be true
        assert (
            # 2022-01-27
            grocery_list._get_shopping_day(for_day, food_group)
            == expected_result
        )

    @staticmethod
    @pytest.mark.parametrize(
        "item",
        [
            "black beans",
            "butter beans",
            "chickpeas",
            "kidney beans",
            "white beans",
        ],
    )
    def test__override_can_to_dried_bean_all_bean(
        grocery_list, config_grocery_list, item
    ):
        config = config_grocery_list.ingredient_replacement.can_to_dried_bean
        row = create_grocery_list_row(
            quantity=1,
            item=item,
            pint_unit=unit_registry.can,
            plural_ending="",
        )

        assert config.g_per_can == 105
        assert_equal_series(
            grocery_list._override_can_to_dried_bean(row),
            create_grocery_list_row(
                quantity=(1 + 1) * 105,
                item=f"dried {item}",
                food_group="Beans",
                pint_unit=unit_registry.g,
                plural_ending="",
            ),
        )

    @staticmethod
    @pytest.mark.parametrize(
        "item,unit,pint_unit",
        [
            ("black beans", "g", unit_registry.g),
            ("black beans", "can", unit_registry.g),
            ("whole tomatoes", "can", unit_registry.can),
        ],
    )
    def test__override_can_to_dried_bean_skip_not_bean_can(
        grocery_list, item, unit, pint_unit
    ):
        row = create_grocery_list_row(item=item, pint_unit=pint_unit)
        assert_equal_series(grocery_list._override_can_to_dried_bean(row), row)

    @staticmethod
    @pytest.mark.parametrize(
        "aisle_group,store,expected_value",
        [
            ("Vegetables", "grocery store", "Vegetables"),
            ("Vegetables", "Asian store", "Asian store"),
            ("Fruits", "grocery store", "Fruits"),
            ("Fruits", "Asian store", "Asian store"),
        ],
    )
    def test__override_aisle_group_when_not_default_store(
        grocery_list, config_grocery_list, aisle_group, store, expected_value
    ):
        config_grocery_list.default_store = "grocery store"
        row = create_grocery_list_row(aisle_group=aisle_group, store=store)

        assert (
            grocery_list._override_aisle_group_when_not_default_store(row)
            == expected_value
        )

    @staticmethod
    def test__process_recipe_queue(grocery_list, mock_ingredient_field, log):
        menu_recipe = create_menu_recipe()
        ingredient, grocery_raw = create_ingredient_and_grocery_entry_raw()
        grocery_list.queue_menu_recipe = [menu_recipe]
        mock_ingredient_field.parse_ingredient_field.return_value = (
            [],
            [ingredient],
            [],
        )

        grocery_list._process_recipe_queue()
        assert log.events[0] == {
            "event": "[grocery list]",
            "level": "info",
            "action": "processing",
            "recipe": "dummy recipe",
        }
        assert grocery_list.queue_menu_recipe == []
        assert_equal_dataframe(grocery_list.grocery_list_raw, grocery_raw)

    @staticmethod
    def test__parse_ingredient_from_recipe(
        grocery_list, config_grocery_list, mock_ingredient_field
    ):
        menu_recipe = create_menu_recipe()
        ingredient, grocery_raw = create_ingredient_and_grocery_entry_raw()
        recipe = create_recipe(title="dummy recipe 2")
        mock_ingredient_field.parse_ingredient_field.return_value = (
            [recipe],
            [ingredient],
            [],
        )
        config_grocery_list.run_mode.with_todoist = True

        with mock.patch.object(builtins, "input", lambda _: "P"):
            grocery_list._parse_ingredient_from_recipe(menu_recipe)

        expected_menu_recipe = create_menu_recipe(
            recipe=recipe, from_recipe="dummy recipe 2_dummy recipe"
        )
        assert grocery_list.queue_menu_recipe == [expected_menu_recipe]
        assert_equal_dataframe(grocery_list.grocery_list_raw, grocery_raw)

    @staticmethod
    def test__process_ingredient_list(grocery_list):
        menu_recipe = create_menu_recipe(eat_factor=0.5, freeze_factor=1)
        ingredient, grocery_entry_raw = create_ingredient_and_grocery_entry_raw(
            recipe_factor=(menu_recipe.eat_factor + menu_recipe.freeze_factor)
        )

        grocery_list._process_ingredient_list(menu_recipe, [ingredient])
        assert_equal_dataframe(grocery_list.grocery_list_raw, grocery_entry_raw)

    @staticmethod
    @pytest.mark.parametrize(
        "food_group,aisle_group",
        [
            ("baking", "Sweet carolina"),
            ("beans", "Canned stuff"),
            ("beverages", "Juices and beverages"),
        ],
    )
    def test__transform_food_to_aisle_group(
        grocery_list, config_grocery_list, food_group, aisle_group
    ):
        config_grocery_list.food_group_to_aisle_map = {food_group: aisle_group}
        assert (
            grocery_list._transform_food_to_aisle_group(food_group)
            == aisle_group
        )

    @staticmethod
    def test__transform_food_to_aisle_group_for_undefined_food_group(
        grocery_list, config_grocery_list
    ):
        config_grocery_list.food_group_to_aisle_map = {}
        assert (
            grocery_list._transform_food_to_aisle_group("asdfjl") == "Unknown"
        )


class TestAddReferencedRecipeToQueue:
    menu_recipe_base = create_menu_recipe(
        recipe=create_recipe(title="recipe_base")
    )
    menu_recipe_ref = create_recipe(
        title="referenced",
        factor=1.0,
        amount="1 cup referenced",
        time_total_str="20 minutes",
    )

    def _get_added_recipe(self):
        return MenuRecipe(
            from_recipe=f"{self.menu_recipe_ref.title}_"
            f"{self.menu_recipe_base.recipe.title}",
            for_day=self.menu_recipe_base.for_day,
            eat_factor=self.menu_recipe_base.eat_factor
            * self.menu_recipe_ref.factor,
            freeze_factor=self.menu_recipe_base.freeze_factor
            * self.menu_recipe_ref.factor,
            recipe=self.menu_recipe_ref,
        )

    def _get_preparation_queue(
        self, task_str: str, due_date: datetime.datetime
    ) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "task": [task_str],
                "due_date": [due_date],
                "from_recipe": [
                    [
                        f"{self.menu_recipe_ref.title}_"
                        f"{self.menu_recipe_base.recipe.title}"
                    ]
                ],
                "for_day_str": [["Thu"]],
            }
        )

    def test__make_yes_schedule_separately_no(
        self, grocery_list, config_grocery_list
    ):
        config_grocery_list.run_mode.with_todoist = True

        with patch("builtins.input", side_effect=["p", "n"]):
            grocery_list._add_referenced_recipe_to_queue(
                self.menu_recipe_base, [self.menu_recipe_ref]
            )

        result = grocery_list.queue_menu_recipe[0]

        added_recipe = self._get_added_recipe()
        assert result.eat_factor == added_recipe.eat_factor
        assert result.for_day == added_recipe.for_day
        assert result.freeze_factor == added_recipe.freeze_factor
        assert result.from_recipe == added_recipe.from_recipe
        assert_equal_series(result.recipe, added_recipe.recipe)

        assert_equal_dataframe(
            grocery_list.queue_preparation,
            self._get_preparation_queue(
                task_str=f"[PREP] {self.menu_recipe_ref.amount}",
                due_date=datetime.datetime(
                    year=2022,
                    month=1,
                    day=26,
                    hour=23,
                    minute=40,
                    tzinfo=timezone("UTC"),
                ),
            ),
        )

    def test__make_yes_schedule_separately_yes(
        self, grocery_list, config_grocery_list
    ):
        config_grocery_list.run_mode.with_todoist = True

        with patch("builtins.input", side_effect=["p", "y", "1", "1"]):
            grocery_list._add_referenced_recipe_to_queue(
                self.menu_recipe_base, [self.menu_recipe_ref]
            )

        result = grocery_list.queue_menu_recipe[0]

        added_recipe = self._get_added_recipe()
        assert result.eat_factor == added_recipe.eat_factor
        assert result.for_day == added_recipe.for_day
        assert result.freeze_factor == added_recipe.freeze_factor
        assert result.from_recipe == added_recipe.from_recipe
        assert_equal_series(result.recipe, added_recipe.recipe)

        assert_equal_dataframe(
            grocery_list.queue_preparation,
            self._get_preparation_queue(
                task_str=f"[PREP] {self.menu_recipe_ref.amount}",
                due_date=datetime.datetime(
                    year=2022, month=1, day=25, hour=12, tzinfo=timezone("UTC")
                ),
            ),
        )

    def test__defrost(self, grocery_list, config_grocery_list):
        config_grocery_list.run_mode.with_todoist = True

        with mock.patch.object(builtins, "input", lambda _: "d"):
            grocery_list._add_referenced_recipe_to_queue(
                self.menu_recipe_base, [self.menu_recipe_ref]
            )

        assert grocery_list.queue_menu_recipe is None

        assert_equal_dataframe(
            grocery_list.queue_preparation,
            self._get_preparation_queue(
                task_str=f"[DEFROST] {self.menu_recipe_ref.amount}",
                due_date=datetime.datetime(
                    year=2022, month=1, day=26, tzinfo=timezone("UTC")
                ),
            ),
        )

    def test__skip(self, grocery_list, config_grocery_list):
        config_grocery_list.run_mode.with_todoist = True

        with mock.patch.object(builtins, "input", lambda _: "s"):
            grocery_list._add_referenced_recipe_to_queue(
                self.menu_recipe_base, [self.menu_recipe_ref]
            )

        assert grocery_list.queue_menu_recipe is None
        assert grocery_list.queue_preparation is None
