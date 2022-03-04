from typing import Union


def create_ingredient_line(
    item: str, quantity: Union[int, float] = None, unit: str = None
):
    line_list = []
    if quantity is not None:
        line_list.append(str(quantity))
    if unit is not None:
        line_list.append(unit)
    line_list.append(item)
    return " ".join(line_list)
