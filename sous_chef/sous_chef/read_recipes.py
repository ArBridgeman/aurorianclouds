import numpy as np

import pandas as pd

COLUMNS = {"title": str,
           "preparationTime": str,
           "cookingTime": str,
           "totalTime": str,
           "ingredients": str,
           "instructions": str,
           "rating": float,
           "favorite": bool,
           "categories": list,
           "tags": list,
           }

TIME_UNITS = ["min", "minutes", "hour", "hours"]


def flatten_dict_to_list(row_entry):
    values = []
    if row_entry is not np.nan:
        for entry in row_entry:
            values.extend(entry.values())
    return values


def create_timedelta(row_entry):
    if row_entry.isdecimal():
        return pd.to_timedelta(int(row_entry), unit="minutes")
    else:
        # has units in string or is nan
        return pd.to_timedelta(row_entry)


# TODO figure out best way to separate active cooking vs inactive cooking
def retrieve_format_recipe_df(json_file):
    tmp_df = pd.read_json(json_file, dtype=COLUMNS)[COLUMNS.keys()]
    tmp_df["totalTime"] = tmp_df["totalTime"].apply(create_timedelta)
    tmp_df["preparationTime"] = tmp_df["preparationTime"].apply(create_timedelta)
    # tmp_df["cookingTime"] = tmp_df["cookingTime"].apply(create_timedelta)
    tmp_df["categories"] = tmp_df.categories.apply(flatten_dict_to_list)
    tmp_df["tags"] = tmp_df.tags.apply(flatten_dict_to_list)
    return tmp_df


def read_recipes(config):
    recipes = pd.DataFrame()
    for json in config.recipe_path.glob(config.recipe_pattern):
        recipes = recipes.append(retrieve_format_recipe_df(json))
    return recipes
