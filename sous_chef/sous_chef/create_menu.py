import os
import json

from collections import defaultdict, OrderedDict
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from filter_recipes import (
    create_previously_tried_filter,
    create_protein_filter,
    create_time_filter,
    has_recipe_category_or_tag,
    skip_protein_filter,
    create_tags_or_filter,
)
from messaging.send_email import EmailSender

from fuzzywuzzy import fuzz
from sous_chef.grocery_list.utils_groceries import get_fuzzy_match


def retrieve_template(filepath):
    with open(filepath) as file:
        weekly_template = yaml.load(file, Loader=yaml.FullLoader)
    return weekly_template


def retrieve_cuisine_map(filepath):
    with open(filepath) as file:
        weekly_template = yaml.load(file, Loader=yaml.FullLoader)
    return weekly_template


def select_by_near_cuisine(recipes, cuisine_select):
    if cuisine_select is not None:
        mask = create_tags_or_filter(recipes, cuisine_select)
        if sum(mask) > 0:
            return mask
    return [True] * recipes.shape[0]


def select_food_item(
        recipes, params, tags=None, food_type: str = "Entree", cuisine_select=None
):
    mask = recipes.categories.apply(has_recipe_category_or_tag, args=(food_type,))

    if tags is None:
        tags = []

    if food_type == "Entree":
        mask &= create_protein_filter(recipes, params["protein_source"])
    elif food_type == "Side":
        mask &= skip_protein_filter(recipes)
        mask &= select_by_near_cuisine(recipes, cuisine_select)

    # TODO implement cuisine or other (tag?) selection here
    # if len(tags) > 0:
    #     print(tags)
    #     mask &= create_tags_and_filter(recipes, tags)

    if params["max_active_time"] > 0:
        mask &= create_time_filter(recipes, params["max_active_time"])
    else:
        # TODO switch to warning?
        print("... no max time set for day")

    if bool(params["recipe_previously_tried"]):
        mask &= create_previously_tried_filter(recipes)
        selection = recipes[mask].copy()
        return selection.sample(weights=selection.rating).iloc[0]
    else:
        selection = recipes[mask].copy()
        weights = selection.rating.replace(0, 2.5)
        return selection.sample(weights=weights).iloc[0]


def select_random_side_from_calendar(recipes, calendar, recipe_uuid, food_type):
    mask_entree = calendar.recipeUuid == recipe_uuid
    # TODO somehow ensure that get a veggie/starch side -> pre-match with recipes?
    # TODO some recipes like lasagna...don't really need sides: need tertiary logic
    # TODO some recipes may already be paired with multiple sides (starch + veggie) -> want both?
    if sum(mask_entree) > 0:
        dates = calendar[mask_entree].date.unique()
        mask_side = (
                (calendar.date.isin(dates))
                & (calendar.recipeUuid != recipe_uuid)
                & (calendar.food_type == food_type)
        )
        if sum(mask_side) > 0:
            side_uuid = calendar[mask_side].sample().iloc[0].recipeUuid
            return recipes[recipes.uuid == side_uuid].iloc[0]
        # TODO use error messages instead and catch based on them and apply appropriate action?
        # TODO let errors be caught at more appropriate level (not just select_side)
        return -1
    return 0


def select_side(recipes, calendar, params, recipe_uuid, cuisine_select):
    veggie_side = select_random_side_from_calendar(
        recipes, calendar, recipe_uuid, "veggies"
    )

    if isinstance(veggie_side, pd.Series):
        return veggie_side
    elif veggie_side == -1:
        return None
    elif veggie_side == 0:
        # TODO limit somehow the cuisine type (e.g. Asian)
        # TODO once cuisine is fixed: randomly choose between new recipe & found one?
        return select_food_item(
            recipes,
            params,
            ["veggies"],
            food_type="Side",
            cuisine_select=cuisine_select,
        )


def get_str_minutes(time):
    if time is None or pd.isnull(time):
        return "0 min"
    return f"{int(time.round('1min').total_seconds() // 60)} min"


def format_time_entry(entry):
    return OrderedDict(
        {
            "prep": get_str_minutes(entry.preparationTime),
            # TODO make proper time
            "cook": entry.cookingTime + " min" if entry.cookingTime.isdecimal() else "",
            "total": get_str_minutes(entry.totalTime),
        }
    )


def format_json_entry(entry):
    return OrderedDict(
        {
            "title": entry.title,
            "rating": entry.rating,
            # TODO add scaling factor to recipe? or do with grocery list
            "orig_quantity": entry.quantity,
            "time": format_time_entry(entry),
            "uuid": entry.uuid,
        }
    )


def format_email_entry(entry):
    return OrderedDict({"title": entry.title, "time": format_time_entry(entry)})


def select_random_meal(recipes, calendar, params, cuisine_map):
    meal_attachment = defaultdict(dict)
    meal_text = defaultdict(dict)

    entree = select_food_item(recipes, params)
    # TODO better way to refactor?
    meal_attachment["entree"] = format_json_entry(entree)
    meal_text["entree"] = format_email_entry(entree)

    cuisine_select = determine_cuisine_selection(entree.tags, cuisine_map)
    # TODO with starch, ensure that meal already doesn't have
    #  starch component (e.g. noodles, potatoes)
    if "bowl" not in entree.tags:
        veggie_side = select_side(
            recipes, calendar, params, entree.uuid, cuisine_select
        )

        # TODO create new YAML mapping for veggies to be used with new veggie cookbook
        #  to be able to draw easily from new cook book
        if veggie_side is not None:
            meal_attachment["veggie"] = format_json_entry(veggie_side)
            meal_text["veggie"] = format_email_entry(veggie_side)

    # TODO link to and somehow limit starches to cuisine type
    # (Asian->rice? or somehow weighted to grains)
    return meal_attachment, meal_text


def interactive_meal_selection(recipes, calendar, params, cuisine_map):
    meal_attachment = defaultdict(dict)
    meal_text = defaultdict(dict)

    def validate_answer(ans, expected):
        if ans.lower().strip() == expected:
            return True
        return False

    side = False
    selector = lambda s: "entree" if not s else "veggie"
    while True:
        title = input(
            "Please enter at least the start of the title of your desired {:s}dish: ".format("side " if side else ""))
        best_results = get_fuzzy_match(title,
                                       recipes.title,
                                       limit=3,
                                       scorer=fuzz.partial_ratio)
        print("Is your desired {:s}dish in this list?:".format("side " if side else ""))
        for i_dish, dish in enumerate(best_results):
            print("({:d}) {:s}".format(i_dish, best_results[i_dish][0]))
        answer = input("Please enter the according number or no (n): [0] ") or 0

        if validate_answer(str(answer), "n"):
            print("Please retry and enter more details!")
            continue
        try:
            answer = int(answer)
            if answer in range(len(best_results)):
                best_result = best_results[answer][0]
            else:
                raise AssertionError("Input is not in list of valid options!")
        except Exception as e:
            print(e)
            continue

        selected_recipe = recipes[recipes.title == best_result].iloc[0]
        meal_attachment[selector(side)] = format_json_entry(selected_recipe)
        meal_text[selector(side)] = format_email_entry(selected_recipe)

        if not side:
            answer = input("Do you wish to add a side dish? (y/n): [y] ") or "y"
            if validate_answer(answer, "y"):
                side = True
                continue
        break

    return meal_attachment, meal_text


def determine_cuisine_selection(entree_tags, cuisine_map):
    for cuisine_group in cuisine_map.keys():
        if any(
                cuisine_tag in entree_tags for cuisine_tag in cuisine_map[cuisine_group]
        ):
            return cuisine_map[cuisine_group]
    return None


# TODO write to json that will be sent via cron to email addresses
def write_menu(write_path, menu):
    if not os.path.exists(os.path.dirname(write_path)):
        os.makedirs(os.path.dirname(write_path))
    with open(write_path, "w") as outfile:
        json.dump(menu, outfile)


# TODO mode or alternate between this and historic/calendar
def create_menu(config, recipes, calendar):
    week = date.today().strftime("%Y-%m-%d")
    template_filepath = Path(config.template_path, config.template)
    template = retrieve_template(template_filepath)
    cuisine_filepath = Path(config.template_path, config.cuisine)
    cuisine_map = retrieve_cuisine_map(cuisine_filepath)
    menu = OrderedDict()
    email_text = OrderedDict()

    for entry in template:
        day = list(entry.keys())[0]
        specifications = entry[day]
        if not config.interactive_menu:
            menu[day], email_text[day] = select_random_meal(
                recipes, calendar, specifications, cuisine_map
            )
        else:  # interactive grouping:
            print("\nWe are going to select the entree for {:s}".format(day))
            skip = input("Skip (y/n): [n] ")
            if skip == "y":
                continue
            menu[day], email_text[day] = interactive_meal_selection(
                recipes, calendar, specifications, cuisine_map
            )

        if config.print_menu:
            print(f"\n# {day} ".ljust(100, "#"))
            print(menu[day]["entree"])
            print(menu[day]["veggie"])

    write_path = Path(config.menu_path, f"{week}.json")
    write_menu(write_path, menu)
    if not config.no_mail:
        email_sender = EmailSender(config)
        email_sender.send_message_with_attachment(
            f"Menu for {week}", email_text, write_path
        )
    else:
        print("Sending of e-mail deactivated by user!")
