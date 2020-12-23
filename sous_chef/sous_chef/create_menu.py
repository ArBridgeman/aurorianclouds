from pathlib import Path

import yaml

from filter_recipes import create_previously_tried_filter, create_protein_filter, \
    create_time_filter, has_recipe_category_or_tag, skip_protein_filter


def retrieve_template(filepath):
    with open(filepath) as file:
        weekly_template = yaml.load(file, Loader=yaml.FullLoader)
    return weekly_template


def select_food_item(recipes, params, tags=None, food_type: str = "Entree"):
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


def select_meal(recipes, params):
    entree = select_food_item(recipes, params)
    # TODO limit somehow the cuisine type (e.g. Asian)
    veggie_side = select_food_item(recipes, params, ["veggies"], food_type="Side")
    # TODO link to and somehow limit starches to cuisine type
    #  (Asian->rice? or somehow weighted to grains)
    return entree, veggie_side


# TODO write to json that will be sent via cron to email addresses
def write_menu_entry(entree, side):
    pass


# TODO mode or alternate between this and historic/calendar
def create_menu(config, recipes):
    input_filepath = Path(config.template_path, config.template)
    template = retrieve_template(input_filepath)
    for entry in template:
        day = list(entry.keys())[0]
        specifications = entry[day]
        entree, veggie_side = select_meal(recipes, specifications)
        print(f"\n# {day}".ljust(120, "#"))
        print(entree[["title", "tags", "categories", "totalTime"]])
        print(veggie_side[["title", "tags", "categories", "totalTime"]])
        # write_menu_entry(entree, side)
