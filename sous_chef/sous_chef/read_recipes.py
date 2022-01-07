import os
import re
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd
from sous_chef.definitions import (
    CALENDAR_COLUMNS,
    CALENDAR_FILE_PATTERN,
    INP_JSON_COLUMNS,
    RECIPE_FILE_PATTERN,
    RTK_FILE_PATTERN,
)


def flatten_dict_to_list(row_entry):
    values = []
    if row_entry is not np.nan and row_entry is not None:
        for entry in row_entry:
            values.extend(entry.values())
    return values


def create_timedelta(row_entry):
    from fractions import Fraction

    row_entry = row_entry.lower().strip()
    if row_entry.isdecimal():
        return pd.to_timedelta(int(row_entry), unit="minutes")
    else:
        # has units in string or is nan
        # cleaning, then parsing with pd.to_timedelta
        row_entry = re.sub("time", "", row_entry)
        row_entry = re.sub("prep", "", row_entry)
        row_entry = re.sub("cooking", "", row_entry)
        row_entry = re.sub("minut[eo]s.?", "min", row_entry)
        row_entry = re.sub("^[\D]+", "", row_entry)
        row_entry = re.sub("mins\.?$", "min", row_entry)
        if re.match("^\d{1,2}:\d{1,2}$", row_entry):
            row_entry = "{}:00".format(row_entry)

        # handle fractions properly
        # todo outsource to separate clean function
        if "/" in row_entry:
            groups = re.match("^(\d?\s\d+[\.\,\/]?\d*)?\s([\s\-\_\w\%]+)", row_entry)
            if groups:
                float_conv = float(sum(Fraction(s) for s in groups.group(1).split()))
                row_entry = f"{float_conv} {groups.group(2).strip()}"

        # errors = "ignore" could be put if we are confident that we want to ignore further issues
        return pd.to_timedelta(row_entry, unit=None, errors="raise")


# TODO figure out best way to separate active cooking vs inactive cooking; make resilient to problems
def retrieve_format_recipe_df(json_file, cols_to_select=INP_JSON_COLUMNS.keys()):
    tmp_df = pd.read_json(json_file, dtype=INP_JSON_COLUMNS)
    for col in cols_to_select:
        if col not in tmp_df.columns:
            tmp_df[col] = None
    tmp_df = tmp_df[cols_to_select]
    tmp_df["totalTime"] = tmp_df["totalTime"].apply(create_timedelta)
    tmp_df["preparationTime"] = tmp_df["preparationTime"].apply(create_timedelta)
    tmp_df["cookingTime"] = tmp_df["cookingTime"].apply(create_timedelta)
    tmp_df["categories"] = tmp_df.categories.apply(flatten_dict_to_list)
    tmp_df["tags"] = tmp_df.tags.apply(flatten_dict_to_list)
    return tmp_df


def delete_older_files(latest_file, rtk_list):
    for file in rtk_list:
        if file != latest_file:
            os.remove(file)


def find_latest_rtk_file(recipe_path: Path):
    rtk_list = [file for file in recipe_path.glob(RTK_FILE_PATTERN)]
    if len(rtk_list) > 0:
        latest_file = max(rtk_list, key=lambda p: p.stat().st_ctime)
        delete_older_files(latest_file, rtk_list)
        return latest_file
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


def read_recipes(recipe_path: Path, de_duplicate: bool = True):
    unzip_rtk(recipe_path)
    recipes = pd.DataFrame()
    for json in recipe_path.glob(RECIPE_FILE_PATTERN):
        recipes = recipes.append(retrieve_format_recipe_df(json))

    # if multiple recipes with exact same name exist, keep highest rated one
    if de_duplicate:
        recipes = recipes.sort_values(["rating"], ascending=False)
        recipes = recipes.drop_duplicates(["title"], keep="first")

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
