from typing import Union

from pint import Unit


def create_ingredient_line(
    item: str,
    quantity: Union[int, float] = None,
    pint_unit: Union[Unit, None] = None,
):
    line_list = []
    if quantity is not None:
        line_list.append(str(quantity))

    if pint_unit is not None:
        unit = str(pint_unit)
        if unit != "dimensionless":
            line_list.append(unit)

    line_list.append(item)
    return " ".join(line_list)
