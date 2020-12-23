from typing import List

import numpy as np
import pandas as pd

PROTEIN_SOURCE = {"beef": ["beef"],
                  "unspecified": ["beef", "seafood", "poultry", "plant protein", "milk protein", "egg", "pork"],
                  "non-flesh": ["plant protein", "milk protein", "egg"],
                  "seafood": ["seafood"],
                  "poultry": ["poultry"],
                  "pork": ["pork"],
                  "side_excluded": ["beef", "seafood", "poultry", "plant protein", "pork"],
                  }


def has_recipe_category_or_tag(recipe_tags, desired_category_or_tag):
    return desired_category_or_tag in recipe_tags


# TODO add type for dataframe
def create_tags_and_filter(recipes, tags: List[str]):
    mask = np.array([True] * recipes.shape[0])
    for tag in tags:
        if "not-" in tag:
            reverse_tag = tag.replace("not-", "")
            mask &= ~recipes.tags.apply(has_recipe_category_or_tag, args=(reverse_tag,))
        else:
            mask &= recipes.tags.apply(has_recipe_category_or_tag, args=(tag,))
    return mask


# TODO add type for dataframe
def create_tags_or_filter(recipes, tags: List[str]):
    mask = np.array([False] * recipes.shape[0])
    for tag in tags:
        mask = np.logical_or(mask, recipes.tags.apply(has_recipe_category_or_tag, args=(tag,)))
    return mask


def create_protein_filter(recipes, protein_source: str):
    return create_tags_or_filter(recipes, PROTEIN_SOURCE[protein_source])


def create_previously_tried_filter(recipes):
    return recipes.rating > 0.0


# TODO add type for dataframe and timedelta
def create_time_filter(recipes, max_time_minutes):
    return recipes.totalTime <= pd.to_timedelta(max_time_minutes, unit="minutes")


def skip_protein_filter(recipes):
    return ~create_tags_or_filter(recipes, PROTEIN_SOURCE["side_excluded"])
