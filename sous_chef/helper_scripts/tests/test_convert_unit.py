import pytest
from convert_unit import (convert_quantity_unit, convert_to_desired_unit,
                          format_significant_quantity,
                          separate_quantity_unit_ingredient)


@pytest.mark.parametrize(
    "quantity, unit, expected_result", [(1, "cup", "1 cup"), (0.25, "tsp", "0.25 tsp")]
)
def test_convert_value_unit_does_not_convert_units(quantity, unit, expected_result):
    assert convert_quantity_unit(quantity, unit) == expected_result


@pytest.mark.parametrize("quantity, unit, expected_result", [(1, "pound", "450 g")])
def test_convert_value_unit_converts_units(quantity, unit, expected_result):
    assert convert_quantity_unit(quantity, unit) == expected_result


@pytest.mark.parametrize(
    "input_quantity, expected_quantity",
    [(1.0, 1), (454.356, 450), (0.25, 0.25), (1.25, 1.25)],
)
def test_format_significant_quantity(input_quantity, expected_quantity):
    assert format_significant_quantity(input_quantity) == expected_quantity


@pytest.mark.parametrize(
    "input_unit,expected_unit",
    [
        ("1 cup milk", (1.0, "cup", "milk")),
        ("1 pound chicken", (1.0, "pound-mass", "chicken")),
        ("2 lbs chicken", (2.0, "pound-mass", "chicken")),
        ("1 orange", (1.0, "", "orange")),
        ("4 russet potatoes", (None, "", "4 russet potatoes")),
    ],
)
def test_separate_quantity_unit_ingredient(input_unit, expected_unit):
    assert separate_quantity_unit_ingredient(input_unit) == expected_unit


@pytest.mark.parametrize(
    "input_unit,expected_unit",
    [
        ("1 cup milk", "1 cup milk"),
        ("1 pound chicken", "450 g chicken"),
        ("2 lbs chicken", "910 g chicken"),
        ("1 orange", "1 orange"),
        ("Ice", "Ice"),
        ("a pinch cayenne pepper", "1 pinch cayenne pepper"),
        ("16 drops essential oil", "16 drops essential oil"),
        ("1c GF flour", "1 cup GF flour"),
        ("1 pound (500 grams) baby potatoes", "450 g (500 grams) baby potatoes"),
        ("4 russet potatoes", "4 russet potatoes"),
        ("4 plum tomatoes, chopped", "4 plum tomatoes, chopped"),
        ("10 empanada disks", "10 empanada disks"),
        ("2 tuna steaks", "2 tuna steaks"),
        (
            "1 inch piece of ginger peeled and chopped",
            "1 inch of ginger peeled and chopped",
        ),
        ('1" ginger, minced', "1 inch ginger, minced"),
        ("1/2 cup maple syrup", "0.5 cup maple syrup"),
        (
            "1/2 ciabatta loaf (120g | 4oz), sliced",
            "1/2 ciabatta loaf (120g | 4oz), sliced",
        ),
        ("24 wonton wrappers", "24 wonton wrappers"),
        ("2 T granulated sweetener of choice", "2 tbsp granulated sweetener of choice"),
    ],
)
def test_convert_to_desired_unit(input_unit, expected_unit):
    assert convert_to_desired_unit(input_unit) == expected_unit
