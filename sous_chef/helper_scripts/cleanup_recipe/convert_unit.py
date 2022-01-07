from pint import UnitRegistry
from quantulum3 import parser

ureg = UnitRegistry()
ureg.default_format = ".2f"
ureg.define("drop = 0.05 ml = drop")
ureg.define("pinch = 0.25 tsp = pinch")

DESIRED_UNITS = {"g": ["pound", "ounce"]}
QUANTULUM_TO_KNOWN = {
    "pound-mass": "pound",
    "pound sterling": "pound",
    "penny inch": "pinch",
    "speed of light": "cup",  # c
    "inch set": "inch",  # inch
    "second of arc": "inch",  # "
    "tesla": "tablespoon",  # T
    "tesla litre": "tablespoon",  # TL
    "tonne litre": "teaspoon",  # tl
    "gram second": "gram",  # gms
    "coulomb": "cup",  # C,
    "teaspoon second": "teaspoon",  # tsps
    "cubic centimetre second": "ml",  # mls
    "tablespoon second": "tbsp",  # tbsps
}

REAL_UNITS = [
    "centimetre",
    "cubic centimetre",
    "cup",
    "dimensionless",
    "drop",
    "gallon",
    "gram",
    "inch",
    "kilogram",
    "litre",
    "ounce",
    "pint",
    "pound-mass",
    "quart",
    "tablespoon",
    "teaspoon",
]
ALLOWED_QUANTULUM = [
    "coulomb",
    "cubic centimetre second",
    "gram second",
    "inch set",
    "penny inch",
    "pound sterling",
    "second of arc",
    "speed of light",
    "tablespoon second",
    "teaspoon second",
    "tesla",
    "tesla litre",
    "tonne litre",
] + REAL_UNITS
DO_NOT_ABBREVIATE = ["cup", "drop", "inch"]


def find_desired_unit(unit):
    for desired_unit, undesired_units in DESIRED_UNITS.items():
        if unit in undesired_units:
            return desired_unit
    return unit


def format_significant_quantity(quantity):
    if (
        isinstance(quantity, int)
        or (isinstance(quantity, float) and quantity.is_integer())
        or quantity >= 10
    ):
        return int(float("{:.2g}".format(quantity)))
    return float("{:.3g}".format(quantity))


def give_desired_unit(unit, quantity):
    converted_unit = "{!s}".format(unit)
    if converted_unit not in DO_NOT_ABBREVIATE:
        return "{:~}".format(unit)
    if quantity > 1:
        return converted_unit + "s"
    return converted_unit


def convert_quantity_unit(quantity, unit):
    original_value = ureg.Quantity(quantity, unit)
    # conversion
    desired_unit = find_desired_unit(unit)
    converted_value = original_value.to(desired_unit)
    # desired format
    significant_magnitude = format_significant_quantity(
        converted_value.magnitude
    )
    converted_unit = give_desired_unit(
        converted_value.units, significant_magnitude
    )
    return "{!s} {!s}".format(significant_magnitude, converted_unit)


def separate_quantity_unit_ingredient(ingredient_line):
    unit = parser.parse(ingredient_line)
    if len(unit) > 0:
        if unit[0].unit.name in ALLOWED_QUANTULUM:
            unit_end = unit[0].span[1]
            unit_name = unit[0].unit.name
            return (
                unit[0].value,
                unit_name if unit_name != "dimensionless" else "",
                ingredient_line[unit_end:].strip(),
            )
        else:
            print(unit[0].unit.name, ingredient_line)

    return None, "", ingredient_line.strip()


def convert_to_desired_unit(ingredient_line):
    quantity, unit, ingredient = separate_quantity_unit_ingredient(
        ingredient_line
    )
    if unit in QUANTULUM_TO_KNOWN.keys():
        unit = QUANTULUM_TO_KNOWN[unit]
    if unit != "":
        converted_quantity_unit = convert_quantity_unit(quantity, unit)
        return "{!s} {!s}".format(converted_quantity_unit, ingredient)
    if quantity is not None:
        return "{!s} {!s}".format(
            format_significant_quantity(quantity), ingredient
        )
    return ingredient
