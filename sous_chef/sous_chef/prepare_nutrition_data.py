#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# File to prepare ingredient/nutrition data files from USDA.
#
#
import pathlib

import pandas as pd
import pyarrow.feather as feather

data_base = pathlib.Path.cwd() / ".." / "nutrition_data"
food_groups = data_base / "FD_GROUP.txt.gz"
food_items = data_base / "FOOD_DES.txt.gz"


def clean_entries(df, cols=None):
    if cols is None:
        cols = df.columns
    for col in cols:
        if df.dtypes[col] == "object":
            df[col] = df[col].str.replace("~", "")
    df = df.convert_dtypes()
    return df


# read files via pandas
food_groups_pd = pd.read_csv(
    food_groups, sep="^", names=["group_id", "group_name"], compression="gzip"
)

food_groups_pd = clean_entries(food_groups_pd)

food_items_pd = pd.read_csv(
    food_items,
    sep="^",
    names=[
        "item_id",
        "group_id",
        "desc_long",
        "desc_short",
        "common_name",
        "manufacturer_name",
        "in_survey",
        "refuse_desc",
        "refuse_pct",
        "sci_name",
        "n_fac",
        "pro_fac",
        "fat_fac",
        "cho_fac",
    ],
    compression="gzip",
)

food_items_pd = clean_entries(food_items_pd)

food_items_joined_pd = pd.merge(
    food_items_pd, food_groups_pd, on="group_id", how="left"
)

food_items_joined_pd["desc_long"] = food_items_joined_pd.desc_long.str.lower()
food_items_joined_pd["is_raw"] = food_items_joined_pd.desc_long.str.contains(
    ", raw"
)
food_items_joined_pd["desc_len"] = food_items_joined_pd.desc_long.str.len()

feather.write_feather(
    food_groups_pd, data_base / "food_groups.feather", compression="lz4"
)
feather.write_feather(
    food_items_joined_pd, data_base / "food_items.feather", compression="lz4"
)

print("Prepared and saved new files!")

# print(food_items_joined_pd.group_name.unique())

# print(food_groups_pd)
# print(food_items_pd)
#
# print(food_groups_pd.dtypes)
# print(food_items_pd.dtypes)
