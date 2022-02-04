import pytest
from hydra import compose, initialize
from sous_chef.formatter.format_unit import (
    UnitExtractionError,
    UnitFormatter,
    convert_quantity_to_desired_unit,
    get_pint_unit,
    get_unit_as_abbreviated_str,
    unit_registry,
)


@pytest.fixture
def unit_formatter():
    with initialize(config_path="../../../config/formatter"):
        config = compose(config_name="format_unit")
        return UnitFormatter(config.format_unit)


def test_unit_formatter_post_init(unit_formatter):
    assert unit_formatter.standard_unit_list == [
        "m",
        "l",
        "g",
        "dam",
        "dal",
        "dag",
        "hm",
        "hl",
        "hg",
        "km",
        "kl",
        "kg",
        "Mm",
        "Ml",
        "Mg",
        "dm",
        "dl",
        "dg",
        "cm",
        "cl",
        "cg",
        "mm",
        "ml",
        "mg",
        "inch",
        "cup",
        "lb",
        "ounce",
        "pint",
        "quart",
        "tbsp",
        "tsp",
    ]
    assert unit_formatter.dimensionless_list == [
        "ball",
        "can",
        "cans",
        "cube",
        "drop",
        "head",
        "jar",
        "package",
        "pinch",
        "pkg",
        "pack",
        "packet",
        "slice",
    ]


@pytest.mark.parametrize(
    "text,expected_unit,expected_pint_unit",
    [("cup rice", "cup", unit_registry.cup)],
)
def test_unit_formatter_extract_unit_from_text(
    unit_formatter, text, expected_unit, expected_pint_unit
):
    assert unit_formatter.extract_unit_from_text(text) == (
        expected_unit,
        expected_pint_unit,
    )


@pytest.mark.parametrize(
    "text,expected_unit,expected_pint_unit",
    [
        ("ball mozzarella", "ball", None),
        ("can beans", "can", None),
        ("cube bullion", "cube", None),
    ],
)
def test_unit_formatter_extract_dimensionless_unit_from_text(
    unit_formatter, text, expected_unit, expected_pint_unit
):
    assert unit_formatter.extract_unit_from_text(text) == (
        expected_unit,
        expected_pint_unit,
    )


def test_unit_formatter_raise_error_when_text_without_unit(unit_formatter):
    text_without_unit = "without unit"
    error_message = rf"text={text_without_unit}"
    with pytest.raises(UnitExtractionError, match=error_message):
        unit_formatter.extract_unit_from_text(text_without_unit)


@pytest.mark.parametrize(
    "text_unit,expected_unit",
    [
        ("cm", unit_registry.centimeter),
        ("g", unit_registry.gram),
        ("in", unit_registry.inch),
        ("l", unit_registry.liter),
        ("oz", unit_registry.ounce),
        ("pt", unit_registry.pint),
        ("lb", unit_registry.pound),
        (
            "qt",
            unit_registry.quart,
        ),
        (
            "tsp",
            unit_registry.teaspoon,
        ),
        ("tbsp", unit_registry.tablespoon),
    ],
)
def test_get_pint_unit_parses_abbreviated_unit(text_unit, expected_unit):
    assert get_pint_unit(text_unit) == expected_unit


@pytest.mark.parametrize(
    "text_unit,expected_unit",
    [
        ("centimeter", unit_registry.centimeter),
        ("cup", unit_registry.cup),
        ("gram", unit_registry.gram),
        ("inch", unit_registry.inch),
        ("liter", unit_registry.liter),
        ("ounce", unit_registry.ounce),
        ("pint", unit_registry.pint),
        ("pound", unit_registry.pound),
        (
            "quart",
            unit_registry.quart,
        ),
        (
            "teaspoon",
            unit_registry.teaspoon,
        ),
        ("tablespoon", unit_registry.tablespoon),
    ],
)
def test_get_pint_unit_parses_singular_unit(text_unit, expected_unit):
    assert get_pint_unit(text_unit) == expected_unit


@pytest.mark.parametrize(
    "text_unit,expected_unit",
    [
        ("centimeters", unit_registry.centimeter),
        ("tablespoons", unit_registry.tablespoon),
    ],
)
def test_get_pint_unit_parses_plural_unit(text_unit, expected_unit):
    assert get_pint_unit(text_unit) == expected_unit


@pytest.mark.parametrize(
    "quantity,unit,desired_unit,expected_quantity",
    [
        (3, unit_registry.tsp, unit_registry.tbsp, 1),
        (4, unit_registry.tbsp, unit_registry.cup, 0.25),
        (400, unit_registry.gram, unit_registry.kg, 0.4),
        (16, unit_registry.ounce, unit_registry.g, 453.59),
    ],
)
def test_convert_quantity_to_desired_unit(
    quantity, unit, desired_unit, expected_quantity
):
    result = convert_quantity_to_desired_unit(quantity, unit, desired_unit)
    assert result == (expected_quantity, desired_unit)


@pytest.mark.parametrize(
    "unit, expected_result",
    [
        (unit_registry.centimeter, "cm"),
        (unit_registry.cup, "cup"),
        (unit_registry.gram, "g"),
        (unit_registry.inch, "in"),
        (unit_registry.liter, "l"),
        (unit_registry.ounce, "oz"),
        (unit_registry.pint, "pt"),
        (unit_registry.pound, "lb"),
        (unit_registry.quart, "qt"),
        (unit_registry.teaspoon, "tsp"),
        (unit_registry.tablespoon, "tbsp"),
    ],
)
def test_get_unit_as_abbreviated_str(unit, expected_result):
    assert get_unit_as_abbreviated_str(unit) == expected_result
