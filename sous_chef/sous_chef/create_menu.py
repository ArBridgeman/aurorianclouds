from pathlib import Path

import pandas as pd
import yaml

from filter_recipes import create_previously_tried_filter, create_protein_filter, \
    create_time_filter, has_recipe_category_or_tag, skip_protein_filter, create_tags_or_filter


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


def select_food_item(recipes, params, tags=None, food_type: str = "Entree", cuisine_select=None):
    mask = recipes.categories.apply(has_recipe_category_or_tag,
                                    args=(food_type,))

    if tags is None:
        tags = []

    if food_type == "Entree":
        mask &= create_protein_filter(recipes, params["protein_source"])
    elif food_type == "Side":
        mask &= skip_protein_filter(recipes)
        mask &= select_by_near_cuisine(recipes, cuisine_select)

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


def select_random_side_from_calendar(recipes, calendar, recipe_uuid, food_type):
    mask_entree = calendar.recipeUuid == recipe_uuid
    # TODO somehow ensure that get a veggie/starch side -> pre-match with recipes?
    # TODO some recipes like lasagna...don't really need sides: need tertiary logic
    # TODO some recipes may already be paired with multiple sides (starch + veggie) -> want both?
    if sum(mask_entree) > 0:
        dates = calendar[mask_entree].date.unique()
        mask_side = (calendar.date.isin(dates)) & (calendar.recipeUuid != recipe_uuid) & (
                calendar.food_type == food_type)
        if sum(mask_side) > 0:
            side_uuid = calendar[mask_side].sample().iloc[0].recipeUuid
            return recipes[recipes.uuid == side_uuid]

        # TODO use error messages instead and catch based on them and apply appropriate action?
        # TODO let errors be caught at more appropriate level (not just select_side)
        return -1
    return 0


def select_side(recipes, calendar, params, recipe_uuid, cuisine_select):
    veggie_side = select_random_side_from_calendar(recipes, calendar, recipe_uuid, "veggies")

    if isinstance(veggie_side, pd.DataFrame):
        return veggie_side
    elif veggie_side == -1:
        return None
    elif veggie_side == 0:
        # TODO limit somehow the cuisine type (e.g. Asian)
        # TODO once cuisine is fixed: randomly choose between new recipe & found one?
        return select_food_item(recipes, params, ["veggies"],
                                food_type="Side", cuisine_select=cuisine_select)


def determine_cuisine_selection(entree_tags, cuisine_map):
    for cuisine_group in cuisine_map.keys():
        if any(cuisine_tag in entree_tags for cuisine_tag in cuisine_map[cuisine_group]):
            return cuisine_map[cuisine_group]
    return None


def select_random_meal(recipes, calendar, params, cuisine_map):
    entree = select_food_item(recipes, params)
    cuisine_select = determine_cuisine_selection(entree.tags.values[0], cuisine_map)
    veggie_side = None
    if "bowl" not in entree.tags:
        veggie_side = select_side(recipes, calendar, params, entree.iloc[0].uuid, cuisine_select)
    # TODO link to and somehow limit starches to cuisine
    #  type (Asian->rice? or somehow weighted to grains)
    return entree, veggie_side


# TODO write to json that will be sent via cron to email addresses
def write_menu_entry(day, meal):
    print(f"\n# {day}".ljust(120, "#"))
    for entry in meal:
        if entry is not None:
            print(entry[["title", "tags", "categories", "totalTime"]])


# TODO mode or alternate between this and historic/calendar
def create_menu(config, recipes, calendar):
    template_filepath = Path(config.template_path, config.template)
    template = retrieve_template(template_filepath)
    cuisine_filepath = Path(config.template_path, config.cuisine)
    cuisine_map = retrieve_cuisine_map(cuisine_filepath)
    for entry in template:
        day = list(entry.keys())[0]
        specifications = entry[day]
        meal = select_random_meal(recipes, calendar, specifications, cuisine_map)
        write_menu_entry(day, meal)
