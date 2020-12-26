from pathlib import Path

import numpy as np
import pandas as pd

CALENDAR_COLUMNS = {"date": str,
                    "title": str,
                    "recipeUuid": str,
                    "uuid": str}

RECIPE_COLUMNS = {"title": str,
                  "preparationTime": str,
                  "cookingTime": str,
                  "totalTime": str,
                  "ingredients": str,
                  "instructions": str,
                  "rating": float,
                  "favorite": bool,
                  "categories": list,
                  # TODO quantity should be split/standardized...it's bad!!!
                  "quantity": str,
                  "tags": list,
                  "uuid": str
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
    tmp_df = pd.read_json(json_file, dtype=RECIPE_COLUMNS)[RECIPE_COLUMNS.keys()]
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


def read_calendar(config):
    filepath = Path(config.recipe_path, config.calendar_file)
    calendar = pd.read_json(filepath, dtype=CALENDAR_COLUMNS)[CALENDAR_COLUMNS.keys()]
    calendar["date"] = pd.to_datetime(calendar["date"]).dt.date
    return calendar
