from pathlib import Path

import pandas as pd
import yaml

from filter_recipes import create_previously_tried_filter, create_protein_filter, create_time_filter, \
    has_recipe_category_or_tag, skip_protein_filter


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
        return selection.sample(weights=selection.rating)
    else:
        selection = recipes[mask].copy()
        weights = selection.rating.replace(0, 2.5)
        return selection.sample(weights=weights)


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
            return recipes[recipes.uuid == sideUuid]

        # TODO use error messages instead and catch based on them and apply appropriate action?
        # TODO let errors be caught at more appropriate level (not just select_side)
        return -1
    return 0


def select_side(recipes, calendar, params, recipeUuid):
    veggie_side = select_random_side_from_calendar(recipes, calendar, recipeUuid)

    if isinstance(veggie_side, pd.DataFrame):
        return veggie_side
    elif veggie_side == -1:
        return None
    elif veggie_side == 0:
        # TODO limit somehow the cuisine type (e.g. Asian)
        # TODO once cuisine is fixed: randomly choose between new recipe & found one?
        return select_food_item(recipes, params, ["veggies"], food_type="Side")


def select_random_meal(recipes, calendar, params):
    entree = select_food_item(recipes, params)
    veggie_side = select_side(recipes, calendar, params, entree.iloc[0].uuid)

    # TODO link to and somehow limit starches to cuisine type (Asian->rice? or somehow weighted to grains)
    return entree, veggie_side


# TODO write to json that will be sent via cron to email addresses
def write_menu_entry(day, meal):
    print(f"\n# {day}".ljust(120, "#"))
    for entry in meal:
        if entry is not None:
            print(entry[["title", "tags", "categories", "totalTime"]])


# TODO mode or alternate between this and historic/calendar
def create_menu(config, recipes, calendar):
    input_filepath = Path(config.template_path, config.template)
    template = retrieve_template(input_filepath)
    for entry in template:
        day = list(entry.keys())[0]
        specifications = entry[day]
        meal = select_random_meal(recipes, calendar, specifications)
        write_menu_entry(day, meal)
