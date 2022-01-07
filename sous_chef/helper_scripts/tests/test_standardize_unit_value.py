import pytest
from standardize_unit_value import (
    convert_html_to_fraction,
    switch_fraction_to_decimal,
)


@pytest.mark.parametrize(
    "input_line, expected_line",
    [
        ("½ tsp apple juice", "1/2 tsp apple juice"),
        ("⅓ cup milk", "1/3 cup milk"),
        ("⅔ tablespoon white wine", "2/3 tablespoon white wine"),
        ("¼ lemon", "1/4 lemon"),
        ("¾ cup flour", "3/4 cup flour"),
        ("1 ¾ cups flour", "1 3/4 cups flour"),
    ],
)
def test_convert_html_to_fraction(input_line, expected_line):
    assert convert_html_to_fraction(input_line) == expected_line


@pytest.mark.parametrize(
    "input_line, expected_line",
    [
        (
            "1 1/2 cups unsweetened vanilla almond milk",
            "1.5 cups unsweetened vanilla almond milk",
        ),
        ("1/3 frozen banana", "0.33 frozen banana"),
        ("1 scoop vanilla protein", "1 scoop vanilla protein"),
        ("1/2 tsp ground cinnamon", "0.5 tsp ground cinnamon"),
        ("1/4 tsp salt", "0.25 tsp salt"),
        ("2/3 tsp baking powder", "0.67 tsp baking powder"),
    ],
)
def test_switch_fraction_to_decimal(input_line, expected_line):
    assert switch_fraction_to_decimal(input_line) == expected_line
