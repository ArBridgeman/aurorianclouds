import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from pint import UnitRegistry
from quantulum3 import parser

# TODO implement method to scale recipe to desired servings
# TODO implement method to mark ingredients that can only be bought the day before + need day
ureg = UnitRegistry()
ureg.default_format = '.2f'


def retrieve_staple_ingredients(config):
    with open(Path(config.grocery_list_path, config.staple_ingredients_file)) as file:
        weekly_template = yaml.load(file, Loader=yaml.FullLoader)
    return weekly_template


def remove_instruction(ingredient):
    return ingredient.split(",")[0]


def separate_unit_from_ingredient(ingredient):
    unit = parser.parse(ingredient)
    # TODO remove if-statement once all empty strings handled
    if len(unit) > 0:
        unit_end = unit[0].span[1]
        unit_name = unit[0].unit.name
        return unit[0].value, unit_name if unit_name != "dimensionless" else "", ingredient[
                                                                                 unit_end:].strip()
    return None, "", ingredient.strip()


def ignore_ingredient(ignored_ingredients, ingredient):
    # TODO make more robust as matches many things
    return any(
        ignored_ingredient == ingredient.lower() for ignored_ingredient in ignored_ingredients)


def is_staple_ingredient(staple_ingredients, ingredient):
    staples = np.concatenate(list(staple_ingredients.values()))
    return any(staple == ingredient.lower() for staple in staples)


def assume_quantity(recipe_title, quantity, ingredient):
    # TODO ignore when quantity not given for certain things? e.g. rice, oil
    # needed for aggregation purposes
    # TODO give warning per recipe?
    if not isinstance(quantity, float):
        print(f"[WARNING] unknown quantity of {ingredient} for {recipe_title}")
        return 1.0
    else:
        return quantity


def separate_ingredients_for_grocery_list(grocery_list, staple_ingredients, recipe_title,
                                          ingredients):
    for line in ingredients.split("\n"):
        stripped_line = line.strip()
        if stripped_line == "[Recommended Sides]":
            break
            # TODO do return here
        # TODO check that all empty strings are being ignored
        # Doesn't seem to based on addition if to separate_unit_from_ingredient
        elif not stripped_line or "[" in line:
            continue

        ingredient = remove_instruction(stripped_line)
        quantity, unit, ingredient = separate_unit_from_ingredient(ingredient)

        if ignore_ingredient(staple_ingredients["Always_ignore"], ingredient):
            continue

        quantity = assume_quantity(recipe_title, quantity, ingredient)

        grocery_list = grocery_list.append(
            {"quantity": quantity, "unit": unit, "ingredient": ingredient,
             "is_staple": is_staple_ingredient(staple_ingredients, ingredient)},
            ignore_index=True)
    return grocery_list


def find_largest_unit(units):
    return max([ureg.parse_expression(unit) for unit in units]).units


def convert_values(row, desired_unit):
    original_value = ureg.Quantity(row["quantity"], ureg.parse_expression(row["unit"]))
    converted_value = original_value.to(desired_unit)
    return round(converted_value.magnitude, 2), converted_value.units


def aggregate_like_ingredient(grocery_list):
    grouped = grocery_list.groupby('ingredient')

    aggregate_grocery_list = pd.DataFrame(columns=grocery_list.columns)
    # TODO fix aggregation for items where +s (e.g. egg + eggs); separately done currently
    for name, group in grouped:
        if group.shape[0] > 1:
            units = group.unit.unique()
            if len(units) > 1:
                largest_unit = find_largest_unit(units)
                group["quantity"], group["unit"] = zip(
                    *group.apply(lambda row: convert_values(row, largest_unit),
                                 axis=1))

        # TODO ensure all types or lack of unit works here & not losing due to none values
        aggregate = group.groupby(["unit", "ingredient"], as_index=False).agg({"quantity": ["sum"],
                                                                               "is_staple": [
                                                                                   "first"]})
        aggregate.columns = aggregate.columns.droplevel(1)
        aggregate_grocery_list = aggregate_grocery_list.append(aggregate[grocery_list.columns])
    return aggregate_grocery_list.reset_index()


def generate_grocery_list(config, recipes):
    filepath = Path(config.menu_path, config.menu_file)
    staple_ingredients = retrieve_staple_ingredients(config)
    with open(filepath) as f:
        menu = json.load(f)

    # TODO how to handle or options (e.g. lettuce or tortillas?) -> special type in ingredient list?
    grocery_list = pd.DataFrame(columns=["quantity", "unit", "ingredient", "is_staple"])
    for day in menu.keys():
        for entry in menu[day].keys():
            if len(menu[day][entry].keys()) > 0:
                mask_entry = recipes.uuid == menu[day][entry]["uuid"]
                selected_recipe = recipes[mask_entry].iloc[0]
                recipe_title = selected_recipe.title
                ingredients = selected_recipe.ingredients
                grocery_list = separate_ingredients_for_grocery_list(grocery_list, staple_ingredients,
                                                                     recipe_title,
                                                                     ingredients)

    grocery_list = aggregate_like_ingredient(grocery_list)
    # TODO convert all masses to grams
    print(grocery_list.sort_values(by=["is_staple", "ingredient"]))
