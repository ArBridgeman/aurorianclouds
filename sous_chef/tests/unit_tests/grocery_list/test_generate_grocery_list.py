from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from hydra import compose, initialize
from pint import Unit
from sous_chef.formatter.format_unit import UnitFormatter, unit_registry
from sous_chef.formatter.ingredient.format_ingredient import Ingredient
from sous_chef.formatter.ingredient.format_ingredient_field import (
    IngredientFieldFormatter,
)
from sous_chef.grocery_list.generate_grocery_list import GroceryList
from sous_chef.menu.create_menu import MenuRecipe
from tests.unit_tests.util import (
    assert_equal_dataframe,
    assert_equal_series,
    create_recipe,
)


def create_grocery_list_row(
    item: str = "dummy ingredient",
    unit: str = None,
    pint_unit: Unit = None,
    is_optional: bool = False,
    quantity: float = 1.0,
    is_staple: bool = False,
    food_group: str = "Vegetables",
    store: str = "grocery store",
    plural_ending: str = "s",
    from_recipe: str = "dummy recipe",
    from_day: str = "Friday",
    aisle_group: str = None,
):
    return pd.Series(
        {
            "item": item,
            "unit": unit,
            "pint_unit": pint_unit,
            "is_optional": is_optional,
            "quantity": quantity,
            "is_staple": is_staple,
            "food_group": food_group,
            "store": store,
            "item_plural": item + plural_ending,
            "from_recipe": from_recipe,
            "from_day": from_day,
            "aisle_group": aisle_group,
        }
    )


def create_ingredient_and_grocery_entry_raw(
    item: str = "zucchini",
    quantity: float = 1.0,
    factor: float = 1.0,
    is_optional: bool = False,
    is_staple: bool = False,
    pint_unit: Unit = None,
    group: str = "Vegetables",
    plural_ending: str = "s",
    store: str = "grocery store",
    should_skip: bool = False,
    recipe_factor: float = 1.0,
    from_recipe: str = "dummy recipe",
    from_day: str = "Friday",
) -> (Ingredient, pd.DataFrame):
    unit = None
    if pint_unit is not None:
        unit = UnitFormatter._get_unit_as_abbreviated_str(pint_unit)

    ingredient = Ingredient(
        quantity=quantity,
        unit=unit,
        pint_unit=pint_unit,
        item=item,
        factor=factor,
        is_optional=is_optional,
        is_staple=is_staple,
        group=group,
        item_plural=item + plural_ending,
        store=store,
        should_skip=should_skip,
    )
    grocery_list_raw = pd.DataFrame(
        {
            "quantity": quantity * recipe_factor,
            "unit": unit,
            "pint_unit": pint_unit,
            "dimension": None,
            "item": item,
            "is_staple": is_staple,
            "is_optional": is_optional,
            "food_group": group,
            "store": store,
            "item_plural": item + plural_ending,
            "from_recipe": from_recipe,
            "from_day": from_day,
        },
        index=[0],
    )
    return ingredient, grocery_list_raw


def create_menu_recipe(
    from_recipe: str = "dummy recipe",
    eat_factor: float = 1.0,
    freeze_factor: float = 0.0,
    from_day="Friday",
    recipe=None,
):
    this_recipe = create_recipe(title=from_recipe)
    if recipe is not None:
        this_recipe = recipe
    return MenuRecipe(
        recipe=this_recipe,
        eat_factor=eat_factor,
        freeze_factor=freeze_factor,
        from_day=from_day,
        from_recipe=from_recipe,
    )


@pytest.fixture
def mock_ingredient_field_formatter():
    with initialize(config_path="../../../config/formatter"):
        config = compose(config_name="format_ingredient_field")
        return Mock(IngredientFieldFormatter(config, None, None))


@pytest.fixture
def config_grocery_list():
    with initialize(config_path="../../../config"):
        return compose(config_name="grocery_list").grocery_list


@pytest.fixture
def grocery_list(
    config_grocery_list, unit_formatter, mock_ingredient_field_formatter
):
    return GroceryList(
        config=config_grocery_list,
        unit_formatter=unit_formatter,
        ingredient_field_formatter=mock_ingredient_field_formatter,
    )


class TestGroceryList:
    @staticmethod
    def test_get_grocery_list_from_menu(
        grocery_list, mock_ingredient_field_formatter
    ):
        # TODO test 3 different scenarios
        menu_recipe = create_menu_recipe()
        ingredient, grocery_raw = create_ingredient_and_grocery_entry_raw()
        mock_ingredient_field_formatter.parse_ingredient_field.return_value = (
            [],
            [ingredient],
        )

        grocery_list.get_grocery_list_from_menu([], [menu_recipe])
        assert_equal_dataframe(grocery_list.grocery_list_raw, grocery_raw)

        result_grocery_list = grocery_list.grocery_list
        expected_grocery_list = grocery_raw.copy()
        expected_grocery_list["aisle_group"] = "Farmland pride"
        expected_grocery_list["from_recipe"] = [["dummy recipe"]]
        expected_grocery_list["from_day"] = [["Friday"]]
        assert_equal_dataframe(
            result_grocery_list,
            expected_grocery_list[result_grocery_list.columns],
        )

    @staticmethod
    def test__add_referenced_recipe_to_queue(grocery_list):
        # TODO implement
        pass

    @staticmethod
    def test__aggregate_grocery_list_by_item_and_dimension(grocery_list):
        # TODO implement
        pass

    @staticmethod
    def test__aggregate_group_to_grocery_list(grocery_list):
        # TODO implement
        pass

    @staticmethod
    @pytest.mark.parametrize(
        "number_can_to_freeze, freeze_text", [(1, "1 can"), (2, "2 cans")]
    )
    def test__format_bean_prep_task_str(
        grocery_list, number_can_to_freeze, freeze_text
    ):
        bean_item = {
            "group": pd.Series(
                {
                    "quantity": 210,
                    "pint_unit": unit_registry.gram,
                    "item": "black beans",
                    "is_optional": False,
                    "item_plural": "black beans",
                }
            ),
            "number_can_to_freeze": number_can_to_freeze,
        }
        assert (
            grocery_list._format_bean_prep_task_str(bean_item)
            == f"BEAN PREP: black beans, 210 g (freeze: {freeze_text})"
        )

    @staticmethod
    @pytest.mark.parametrize(
        "quantity,pint_unit,item,is_optional,plural_ending,expected_result",
        [
            (1, None, "zucchini", False, "s", "zucchini, 1"),
            (1, unit_registry.cup, "rice", False, "", "rice, 1 cup"),
            (1, None, "zucchini", True, "s", "zucchini, 1 (optional)"),
            (1, unit_registry.cup, "rice", True, "", "rice, 1 cup (optional)"),
            (2, None, "zucchini", False, "s", "zucchinis, 2"),
            (2, unit_registry.cup, "rice", False, "", "rice, 2 cups"),
        ],
    )
    def test__format_ingredient_str(
        grocery_list,
        quantity,
        pint_unit,
        item,
        is_optional,
        plural_ending,
        expected_result,
    ):
        ingredient = pd.Series(
            {
                "quantity": quantity,
                "pint_unit": pint_unit,
                "item": item,
                "is_optional": is_optional,
                "item_plural": item + plural_ending,
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
                "unit": ["dummy", "dummy"],
                "pint_unit": [larger_pint_unit, second_pint_unit],
            }
        )

        larger_pint_unit_str = UnitFormatter()._get_unit_as_abbreviated_str(
            larger_pint_unit
        )

        result = grocery_list._get_group_in_same_pint_unit(group)
        assert np.all(result.quantity.values == expected_quantity)
        assert np.all(result.pint_unit.values == [larger_pint_unit] * 2)
        assert np.all(result.unit.values == [larger_pint_unit_str] * 2)

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
            unit="can",
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
                unit="g",
                pint_unit=unit_registry.g,
                plural_ending="",
            ),
        )

    @staticmethod
    @pytest.mark.parametrize(
        "item,unit,pint_unit",
        [
            ("black beans", "g", unit_registry.g),
            ("whole tomatoes", "can", unit_registry.can),
        ],
    )
    def test__override_can_to_dried_bean_skip_not_bean_can(
        grocery_list, item, unit, pint_unit
    ):
        row = create_grocery_list_row(item=item, unit=unit, pint_unit=pint_unit)
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
    def test__process_recipe_queue(
        grocery_list, mock_ingredient_field_formatter, log
    ):
        menu_recipe = create_menu_recipe()
        ingredient, grocery_raw = create_ingredient_and_grocery_entry_raw()
        grocery_list.queue_menu_recipe = [menu_recipe]
        mock_ingredient_field_formatter.parse_ingredient_field.return_value = (
            [],
            [ingredient],
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
        grocery_list, mock_ingredient_field_formatter
    ):
        menu_recipe = create_menu_recipe()
        ingredient, grocery_raw = create_ingredient_and_grocery_entry_raw()
        recipe = create_recipe(title="dummy recipe 2")
        mock_ingredient_field_formatter.parse_ingredient_field.return_value = (
            [recipe],
            [ingredient],
        )

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
        grocery_list,
    ):
        config_grocery_list.food_group_to_aisle_map = {}
        assert (
            grocery_list._transform_food_to_aisle_group("asdfjl") == "Unknown"
        )
