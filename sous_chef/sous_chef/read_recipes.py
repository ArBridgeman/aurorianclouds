from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd
from definitions import (CALENDAR_COLUMNS, CALENDAR_FILE_PATTERN,
                         INP_JSON_COLUMNS, RECIPE_FILE_PATTERN,
                         RTK_FILE_PATTERN)


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


# TODO figure out best way to separate active cooking vs inactive cooking; make resilient to problems
def retrieve_format_recipe_df(json_file):
    tmp_df = pd.read_json(json_file, dtype=INP_JSON_COLUMNS)[INP_JSON_COLUMNS.keys()]
    # tmp_df["totalTime"] = tmp_df["totalTime"].apply(create_timedelta)
    # tmp_df["preparationTime"] = tmp_df["preparationTime"].apply(create_timedelta)
    # tmp_df["cookingTime"] = tmp_df["cookingTime"].apply(create_timedelta)
    tmp_df["categories"] = tmp_df.categories.apply(flatten_dict_to_list)
    tmp_df["tags"] = tmp_df.tags.apply(flatten_dict_to_list)
    return tmp_df


def find_latest_rtk_file(recipe_path: Path):
    rtk_list = [file for file in recipe_path.glob(RTK_FILE_PATTERN)]
    if len(rtk_list) > 0:
        return max(rtk_list, key=lambda p: p.stat().st_ctime)
    return None


def unzip_rtk(recipe_path):
    rtk_file = find_latest_rtk_file(recipe_path)
    if rtk_file is not None:
        with ZipFile(rtk_file, "r") as zip_ref:
            files_in_zip = zip_ref.namelist()
            for fileName in files_in_zip:
                if fileName.endswith(".json"):
                    zip_ref.extract(fileName, path=recipe_path)
        rtk_file.unlink()


def read_recipes(recipe_path: Path):
    unzip_rtk(recipe_path)
    recipes = pd.DataFrame()
    for json in recipe_path.glob(RECIPE_FILE_PATTERN):
        recipes = recipes.append(retrieve_format_recipe_df(json))
    return recipes


def create_food_type(row):
    if "veggies" in row.tags:
        return "veggies"
    elif "starch" in row.tags:
        return "starch"
    elif "Entree" in row.categories:
        return "protein"
    else:
        return "dessert"


def label_calendar(calendar, recipes):
    calendar = pd.merge(
        calendar,
        recipes[["uuid", "tags", "categories"]],
        how="inner",
        left_on="recipeUuid",
        right_on="uuid",
    )
    calendar["food_type"] = calendar.apply(lambda x: create_food_type(x), axis=1)
    return calendar


def read_calendar(calendar_path, recipes):
    filepath = Path(calendar_path, CALENDAR_FILE_PATTERN)
    calendar = pd.read_json(filepath, dtype=CALENDAR_COLUMNS)[CALENDAR_COLUMNS.keys()]
    calendar["date"] = pd.to_datetime(calendar["date"]).dt.date
    return label_calendar(calendar, recipes)
