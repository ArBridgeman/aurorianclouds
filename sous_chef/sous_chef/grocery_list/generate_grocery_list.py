import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from pint import UnitRegistry
from quantulum3 import parser

from grocery_list.grocery_matching_mapping import (IngredientsHelper,
                                                   get_fuzzy_match,
                                                   relevant_macro_groups,
                                                   todoist_mapping)
from definitions import ALLOWED_UNITS
from messaging.todoist_api import TodoistHelper

# TODO implement method to scale recipe to desired servings
# TODO implement method to mark ingredients that can only be bought the day before + need day
ureg = UnitRegistry()
ureg.default_format = ".2f"


def retrieve_staple_ingredients(config):
    with open(Path(config.grocery_list_path, config.staple_ingredients_file)) as file:
        weekly_template = yaml.load(file, Loader=yaml.FullLoader)
    return weekly_template


def remove_instruction(ingredient):
    return (
        ingredient.replace(", chopped", "")
            .replace(", minced", "")
            .replace(", diced", "")
    )


def separate_unit_from_ingredient(ingredient):
    unit = parser.parse(ingredient)
    # TODO remove if-statement once all empty strings handled
    if len(unit) > 0:
        unit_end = unit[0].span[1]
        unit_name = unit[0].unit.name
        return (
            unit[0].value,
            unit_name if unit_name != "dimensionless" else "",
            ingredient[unit_end:].strip(),
        )
    return None, "", ingredient.strip()


def ignore_ingredient(ignored_ingredients, ingredient):
    # TODO make more robust as matches many things
    return any(
        ignored_ingredient == ingredient.lower()
        for ignored_ingredient in ignored_ingredients
    )


def is_staple_ingredient(staple_ingredients, ingredient):
    staples = np.concatenate(list(staple_ingredients.values()))
    return any(staple == ingredient.lower() for staple in staples)


def assume_quantity(recipe_title, quantity, ingredient):
    # TODO ignore when quantity not given for certain things? e.g. rice, oil
    # needed for aggregation purposes
    # TODO give warning per recipe?
    if not isinstance(quantity, (int, float)):
        print(f"[WARNING] unknown quantity of {ingredient} for {recipe_title}")
        return 1.0
    else:
        return float(quantity)


def naive_unit_extraction(ingredient):
    # TODO: this makes assumptions about our specific ingredient format and should be generalized
    # TODO: mapping from long to abbreviated forms is missing
    detected = ""
    for unit in ALLOWED_UNITS:
        if re.match("^{:s}s?\s".format(unit), ingredient):
            detected = unit
            break

    if detected != "":
        ingredient = re.sub("^{:s}s?\s".format(detected), " ", ingredient)

    return ingredient, detected


def regex_split_ingredient(ingredient,
                           pattern="^(\d+[\.\,]?\d*)?\s([\s\-\_\w]+)(\s?\(\w+\))?"):
    # TODO: this should be updated with crf model in the future to be MUCH more robust
    # especially once we start cleaning other recipes that haven't been preprocessed
    instruction = ""
    ingredient = re.sub("\s+", " ", ingredient.strip())

    re_match = re.match(pattern, ingredient)
    if re_match:
        quantity = float(re_match.group(1))
        ingredient = re_match.group(2).strip()
        if re_match.group(3) is not None and re_match.group(3) != "":
            instruction = re_match.group(3)[1:-1]
    else:
        quantity = 1

    ingredient, unit = naive_unit_extraction(ingredient)
    return quantity, unit, ingredient, instruction


def separate_ingredients_for_grocery_list(grocery_list, staple_ingredients,
                                          recipe_title, ingredients, day,
                                          mult_factor=1.,
                                          regex_match=True):
    for line in ingredients.split("\n"):
        is_optional = False
        stripped_line = re.sub("\s+", " ", line.strip())

        if stripped_line.lower() in ["[recommended sides]", "[sides]",
                                     "[optional]", "[garnish]"]:
            break

        # TODO check that all empty strings are being ignored
        # Doesn't seem to based on addition if to separate_unit_from_ingredient
        if not stripped_line or "[" in line:
            continue

        # nothing relevant is that short
        if len(stripped_line) < 3:
            continue

        if "optional" in stripped_line.lower():
            is_optional = True
            stripped_line = stripped_line.replace("Optional", "").replace(
                "optional", ""
            )

        if ":" in stripped_line:
            # take only things after ":"
            stripped_line = stripped_line.split(":")[1]

        ingredient = remove_instruction(stripped_line)

        grocery_list = parse_add_ingredient_entry_to_grocery_list(ingredient,
                                                                  grocery_list,
                                                                  staple_ingredients,
                                                                  factor=mult_factor,
                                                                  from_recipe=recipe_title,
                                                                  from_day=day,
                                                                  use_regex=regex_match,
                                                                  manual_entry=False,
                                                                  is_optional=is_optional
                                                                  )

    return grocery_list


def find_largest_unit(units):
    all_units = []
    for unit in units:
        if unit.strip() == "":
            continue
        try:
            all_units.append(ureg.parse_expression(unit))
        except Exception as e:
            print(e)
            print("Error while parsing unit {:s}! Ignoring!".format(unit))
    return max(all_units).units


def convert_values(row, desired_unit):
    try:
        original_value = ureg.Quantity(
            row["quantity"], ureg.parse_expression(row["unit"])
        )
        if row["unit"] == "":
            return round(original_value.magnitude, 2), ""
        converted_value = original_value.to(desired_unit)
        return round(converted_value.magnitude, 2), converted_value.units
    except Exception as e:
        print(e)
        return row["quantity"], row["unit"]


def aggregate_like_ingredient(grocery_list, convert_units=False):
    grouped = grocery_list.groupby("ingredient")

    aggregate_grocery_list = pd.DataFrame(columns=grocery_list.columns)
    # TODO fix aggregation for items where +s (e.g. egg + eggs); separately done currently
    for name, group in grouped:
        if group.shape[0] > 1:
            if convert_units:
                units = group.unit.unique()
                if len(units) > 1:
                    largest_unit = find_largest_unit(units)
                    group["quantity"], group["unit"] = zip(
                        *group.apply(lambda row: convert_values(row, largest_unit), axis=1)
                    )

        # TODO ensure all types or lack of unit works here & not losing due to none values
        aggregate = group.groupby(["unit", "ingredient", "manual_ingredient", "is_optional"], as_index=False).agg(
            {
                "quantity": ["sum"],
                "is_staple": ["first"],
                "from_recipe": lambda x: list(set(x)),
                "from_day": lambda x: list(set(x)),
                "instruction": lambda x: list(set(x))
            }
        )
        aggregate.columns = aggregate.columns.droplevel(1)
        aggregate_grocery_list = aggregate_grocery_list.append(
            aggregate[grocery_list.columns]
        )
    return aggregate_grocery_list.reset_index()


def get_food_categories(grocery_list, config):
    master_file = None
    try:
        master_file = pd.read_csv(config.master_list_file, header=0)
    except Exception as e:
        print("Error while trying to read master ingredient list!")
        print(e)

    # some cleaning before matching
    grocery_list["ingredient"] = grocery_list["ingredient"].apply(
        lambda x: re.sub("[^A-Za-z0-9üäö\-_\s]+", "", x).strip()
    )

    grocery_list_matched = None
    if master_file is not None:
        match_helper = lambda item: get_fuzzy_match(
            item, master_file.ingredient.values, warn=True, limit=1, reject=80
        )[0]
        grocery_list["best_match"] = (
            grocery_list["ingredient"].apply(match_helper)
        )
        grocery_list["match_quality"] = grocery_list["best_match"].str[1]
        grocery_list["best_match"] = grocery_list["best_match"].str[0]

        grocery_list = pd.merge(
            grocery_list[[col for col in grocery_list.columns if col not in ["group"]]],
            master_file[["ingredient", "group"]].rename(
                columns={"ingredient": "master_ingredient"}
            ),
            left_on="best_match",
            right_on="master_ingredient",
            how="left",
        ).drop(columns=["master_ingredient"])

        unmatched_mask = (
                grocery_list.group.isnull()
                | pd.isna(grocery_list.group)
                | (grocery_list.group == "Unknown")
        )

        print(
            "There are {:d} unmatched grocery ingredients after using master list!".format(
                unmatched_mask.sum()
            )
        )
        grocery_list_matched = grocery_list[~unmatched_mask]
        grocery_list = grocery_list[unmatched_mask]

    # try to estimate missing or unknown groups
    ingredient_helper = IngredientsHelper(config.food_items_file)
    grocery_list["group"] = grocery_list.ingredient.apply(
        ingredient_helper.get_food_group
    )

    grocery_list = pd.concat([grocery_list, grocery_list_matched])
    grocery_list = grocery_list.sort_values("manual_ingredient", ascending=False)

    one_change = False
    if config.interactive_grouping:
        print("Will query for user input to improve food grouping of selected recipes!")
        for _, item in grocery_list.iterrows():
            if item.group == "Unknown" or (item.manual_ingredient and (item.match_quality < 98)):
                if not item.manual_ingredient:
                    print("\nGroup unknown for ingredient: {:s}".format(item.ingredient))
                else:
                    print("\nManual ingredient {:s} not in the list, please provide input to add it!".format(
                        item.ingredient))
                print("Please select the appropriate group: ")
                for i_group, group in enumerate(relevant_macro_groups):
                    print("{}: {:d}".format(group, i_group))
                while True:
                    try:
                        user_input = input(
                            "Please select: (0 - {:d}) >> ".format(
                                len(relevant_macro_groups) - 1
                            )
                        )
                        group_update = relevant_macro_groups[int(user_input)]
                        grocery_list.loc[
                            grocery_list.ingredient == item.ingredient, "group"
                        ] = group_update
                        print("Updated to {}".format(group_update))
                        master_file = master_file.append(
                            {
                                "ingredient": item.ingredient,
                                "is_staple": False,
                                "group": group_update
                            },
                            ignore_index=True,
                        )
                        one_change = True
                        break
                    except Exception as e:
                        print(
                            "Error while updating group, please check input and retry!"
                        )
                        print(e)
        if one_change:
            print("All uncertain groups have been updated!")
            print("Updating master file with added ingredients and groups!")
            master_file.to_csv(config.master_list_file, index=False, header=True)
            print("Written to {:s}".format(config.master_list_file.as_posix()))

    return grocery_list


def upload_groceries_to_todoist(
        groceries,
        project_name="Groceries",
        clean=False,
        dry_mode=False,
        todoist_token_file_path="todoist_token.txt",
):
    todoist_helper = TodoistHelper(todoist_token_file_path)

    groceries["group"] = groceries["group"].map(todoist_mapping)

    if clean:
        print("Cleaning previous items/tasks in project {:s}".format(project_name))
        if not dry_mode:
            todoist_helper.delete_all_items_in_project(project_name)

    if dry_mode:
        print("Dry mode! Will only simulate actions but not upload to todoist!")

    for _, item in groceries.iterrows():
        formatted_item = "{}, {} {}{}".format(item.ingredient, item.quantity,
                                              item.unit, " (optional)" if item.is_optional else "")
        formatted_item = re.sub("\s+", " ", formatted_item).strip()
        print("Adding item {:s} from group {:s} to "
              "todoist (recipe source(s): {})".format(formatted_item, item.group, repr(item.from_recipe)))
        if not dry_mode:
            all_labels = item.from_recipe + item.from_day
            if item.is_optional:
                all_labels.append(["Optional"])
            todoist_helper.add_item_to_project(
                formatted_item, project_name, section=item.group,
                labels=all_labels
            )


# TODO: further generalize and improve this function (staple detection, other fields etc.)
def parse_add_ingredient_entry_to_grocery_list(ingredient_line,
                                               grocery_list, staple_list,
                                               manual_entry=True, factor=1.,
                                               is_staple=False, is_optional=False,
                                               use_regex=True, from_recipe="",
                                               from_day=""):
    ingredient_line = str(ingredient_line.strip())
    instruction = ""
    if use_regex:
        quantity, unit, ingredient, instruction = regex_split_ingredient(ingredient_line)
    else:
        quantity, unit, ingredient = separate_unit_from_ingredient(ingredient_line)

    quantity = assume_quantity("", quantity, ingredient)

    if ignore_ingredient(staple_list["Always_ignore"], ingredient):
        return grocery_list

    grocery_list = grocery_list.append(
        {
            "quantity": factor * quantity,
            "unit": unit,
            "ingredient": ingredient,
            "is_staple": is_staple_ingredient(staple_list, ingredient) or is_staple,
            "is_optional": is_optional,
            "manual_ingredient": manual_entry,
            "from_recipe": from_recipe,
            "from_day": from_day,
            "instruction": instruction,
        },
        ignore_index=True,
    )
    return grocery_list


def get_empty_grocery_df():
    grocery_list = pd.DataFrame(
        columns=["quantity", "unit", "ingredient", "is_staple", "is_optional",
                 "manual_ingredient", "from_recipe", "from_day", "instruction"]
    )
    return grocery_list


def generate_grocery_list(config, recipes, verbose=False):
    if config.only_clean_todoist:
        project_name = "Groceries"
        todoist_helper = TodoistHelper(config.todoist_token_file)
        print("Cleaning previous items/tasks in project {:s}".format(project_name))
        todoist_helper.delete_all_items_in_project(project_name)
        return

    filepath = Path(config.menu_path, config.menu_file)
    staple_ingredients = retrieve_staple_ingredients(config)

    getter, menu, days = None, None, None
    if filepath.suffix == ".json":
        with open(filepath) as f:
            menu = json.load(f)
        days = menu.keys()
        getter = lambda d: menu[d].items()
    elif filepath.suffix == ".csv":
        menu = pd.read_csv(filepath)
        days = menu.weekday.unique()
        getter = lambda d: menu[menu.weekday == d].iterrows()

    assert getter is not None, "File type not known, no idea how to work with {:s}!".format(filepath)

    grocery_list = get_empty_grocery_df()

    for day in days:
        for _, entry in getter(day):
            if len(entry) > 0:

                # manual ingredient or addition, no matching to known recipes should be done
                if entry.get("type", None) == "ingredient":
                    if entry.get("grocery_list", None) == "Y":
                        grocery_list = parse_add_ingredient_entry_to_grocery_list(entry["item"],
                                                                                  grocery_list,
                                                                                  staple_ingredients,
                                                                                  factor=entry["factor"],
                                                                                  from_recipe="manual",
                                                                                  from_day=day
                                                                                  )
                else:
                    mask_entry = None
                    if "uuid" in entry:
                        mask_entry = recipes.uuid == entry["uuid"]
                    elif "item" in entry:
                        mask_entry = recipes.title == entry["item"]
                        if np.sum(mask_entry) == 0:
                            print("Couldn't find recipe title {:s}. Attempting (very strict) fuzzy match!".format(
                                entry["item"]))
                            match_title = get_fuzzy_match(entry["item"],
                                                          recipes.title.values,
                                                          warn=True, limit=1, reject=97)[0][0]
                            print("Identified recipe: {:s}".format(match_title))
                            mask_entry = recipes.title == match_title
                    else:
                        AssertionError("No way of matching entry {} to recipe db!".format(entry))

                    assert mask_entry is not None and np.sum(
                        mask_entry) > 0, "Could not find recipe {} in recipes db!".format(entry)

                    selected_recipe = recipes[mask_entry].iloc[0]
                    recipe_title = selected_recipe.title
                    ingredients = selected_recipe.ingredients
                    grocery_list = separate_ingredients_for_grocery_list(
                        grocery_list, staple_ingredients, recipe_title, ingredients, day,
                        mult_factor=float(entry.get("factor", 1)),
                        regex_match=True
                    )

    grocery_list = aggregate_like_ingredient(grocery_list)

    # get all food categories using USDA data
    grocery_list = get_food_categories(grocery_list, config)

    # TODO convert all masses to grams
    if verbose:
        print(grocery_list.sort_values(["is_staple", "ingredient"]))

    if not config.no_upload:
        # TODO add arg option for dry-run as currently hardcoded
        print("Uploading grocery list to todoist...")
        upload_groceries_to_todoist(
            grocery_list,
            clean=config.clean_todoist,
            dry_mode=config.dry_mode,
            todoist_token_file_path=config.todoist_token_file,
        )
        print("Upload done.")
