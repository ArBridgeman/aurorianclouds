from datetime import date
import json
from collections import defaultdict, OrderedDict
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from filter_recipes import create_previously_tried_filter, create_protein_filter, create_time_filter, \
    has_recipe_category_or_tag, skip_protein_filter
from send_email import EmailSender


def retrieve_template(filepath):
    with open(filepath) as file:
        weekly_template = yaml.load(file, Loader=yaml.FullLoader)
    return weekly_template


def select_food_item(recipes, params, tags=[], food_type: str = "Entree"):
    mask = recipes.categories.apply(has_recipe_category_or_tag,
                                    args=(food_type,))

    if food_type == "Entree":
        mask &= create_protein_filter(recipes, params["protein_source"])
    elif food_type == "Side":
        mask &= skip_protein_filter(recipes)

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


def select_random_side_from_calendar(recipes, calendar, recipeUuid):
    mask_entree = calendar.recipeUuid == recipeUuid
    # TODO somehow ensure that get a veggie/starch side -> pre-match with recipes?
    # TODO some recipes like lasagna...don't really need sides: need tertiary logic
    # TODO some recipes may already be paired with multiple sides (starch + veggie) -> want both?
    if sum(mask_entree) > 0:
        dates = calendar[mask_entree].date.unique()
        mask_side = (calendar.date.isin(dates)) & (calendar.recipeUuid != recipeUuid)
        if sum(mask_side) > 0:
            sideUuid = calendar[mask_side].sample().iloc[0].recipeUuid
            return recipes[recipes.uuid == sideUuid].iloc[0]

        # TODO use error messages instead and catch based on them and apply appropriate action?
        # TODO let errors be caught at more appropriate level (not just select_side)
        return -1
    return 0


def select_side(recipes, calendar, params, recipeUuid):
    veggie_side = select_random_side_from_calendar(recipes, calendar, recipeUuid)

    if isinstance(veggie_side, pd.Series):
        return veggie_side
    elif veggie_side == -1:
        return None
    elif veggie_side == 0:
        # TODO limit somehow the cuisine type (e.g. Asian)
        # TODO once cuisine is fixed: randomly choose between new recipe & found one?
        return select_food_item(recipes, params, ["veggies"], food_type="Side")


def get_str_minutes(time):
    # TODO fix occasional error when 'ValueError: cannot convert float NaN to integer"'
    return f"{int(time.round('1min').total_seconds() // 60) if time is not np.nan else 0} min"


def format_time_entry(entry):
    return OrderedDict({"prep": get_str_minutes(entry.preparationTime),
                        # TODO make proper time
                        "cook": entry.cookingTime + " min" if entry.cookingTime.isdecimal() else "",
                        "total": get_str_minutes(entry.totalTime)})


def format_json_entry(entry):
    return OrderedDict({"title": entry.title,
                        "rating": entry.rating,
                        # TODO add scaling factor to recipe? or do with grocery list
                        "orig_quantity": entry.quantity,
                        "time": format_time_entry(entry),
                        "uuid": entry.uuid})


def format_email_entry(entry):
    return OrderedDict({"title": entry.title,
                        "time": format_time_entry(entry)})


def select_random_meal(recipes, calendar, params):
    meal_attachment = defaultdict(dict)
    meal_text = defaultdict(dict)

    entree = select_food_item(recipes, params)
    # TODO better way to refactor?
    meal_attachment["entree"] = format_json_entry(entree)
    meal_text["entree"] = format_email_entry(entree)

    # TODO would be better if entree not needing side did not do this check...
    # TODO with starch, ensure that meal already doesn't have starch component (e.g. noodles, potatoes)
    veggie_side = select_side(recipes, calendar, params, entree.uuid)
    if veggie_side is not None:
        meal_attachment["veggie"] = format_json_entry(veggie_side)
        meal_text["veggie"] = format_email_entry(veggie_side)

    # TODO link to and somehow limit starches to cuisine type (Asian->rice? or somehow weighted to grains)
    return meal_attachment, meal_text


# TODO write to json that will be sent via cron to email addresses
def write_menu(write_path, menu):
    with open(write_path, "w") as outfile:
        json.dump(menu, outfile)


# TODO mode or alternate between this and historic/calendar
def create_menu(config, recipes, calendar):
    week = date.today().strftime("%Y-%m-%d")
    input_filepath = Path(config.template_path, config.template)
    template = retrieve_template(input_filepath)
    menu = OrderedDict()
    email_text = OrderedDict()
    for entry in template:
        day = list(entry.keys())[0]
        specifications = entry[day]
        menu[day], email_text[day] = select_random_meal(recipes, calendar, specifications)

    write_path = f"../food_plan/{week}.json"
    write_menu(write_path, menu)
    email_sender = EmailSender(config)
    email_sender.send_message_with_attachment(f"Menu for {week}", f"{json.dumps(email_text, indent=4)}",
                                              write_path)
