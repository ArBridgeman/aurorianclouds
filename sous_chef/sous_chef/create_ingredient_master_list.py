#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Helper script to create master ingredient list for selected recipes (e.g. only rated ones).
#
#
import sys
import argparse
from pathlib import Path

import pandas as pd

# from create_menu import create_menu
from generate_grocery_list import generate_grocery_list, retrieve_staple_ingredients, \
    separate_ingredients_for_grocery_list, aggregate_like_ingredient, get_food_categories
from read_recipes import read_calendar, read_recipes

ABS_FILE_PATH = Path(__file__).absolute().parent


def generate_parser():
    parser = argparse.ArgumentParser(description='script activities')
    sub_parser = parser.add_subparsers(help="type of operation")

    parser.add_argument("--recipe_path", type=Path,
                        default=Path(ABS_FILE_PATH, "../recipe_data"))
    parser.add_argument("--recipe_pattern", type=str,
                        default="recipes*.json")
    parser.add_argument("--grocery_list_path", type=str,
                        default=Path(ABS_FILE_PATH, "../grocery_list"))
    parser.add_argument("--staple_ingredients_file", type=str,
                        default="staple_ingredients.yml")
    parser.add_argument("--calendar_file", type=str,
                        default="calendar.json")
    parser.add_argument("--food_items_file", type=Path,
                        default=Path(ABS_FILE_PATH, "../nutrition_data/food_items.feather"))
    parser.add_argument("--master_list_out_file", type=Path,
                        default=Path(ABS_FILE_PATH, "../nutrition_data/master_ingredient_list.csv"))
    parser.add_argument("--only_rated", action="store_true",
                        help="Consider only rated recipes (independent of rating score).")

    return parser


def generate_master_list(config, recipes, only_rated=True):
    staple_ingredients = retrieve_staple_ingredients(config)

    # TODO how to handle or options (e.g. lettuce or tortillas?) -> special type in ingredient list?
    grocery_list = pd.DataFrame(columns=["quantity", "unit", "ingredient",
                                         "is_staple", "is_optional", "group"])

    selected_recipes = recipes.copy()
    if only_rated:
        print("Considering only rated recipes!")
        selected_recipes = selected_recipes[selected_recipes.rating > 0]

    print("Working with {:d} recipes.".format(selected_recipes.shape[0]))

    for _, selected_recipe in selected_recipes.iterrows():
        recipe_title = selected_recipe.title
        ingredients = selected_recipe.ingredients
        grocery_list = separate_ingredients_for_grocery_list(grocery_list, staple_ingredients,
                                                             recipe_title,
                                                             ingredients)

    # quantities are not immediately of interest for the ingredient master list
    # grocery_list = aggregate_like_ingredient(grocery_list)
    # de-duplicate on ingredient
    grocery_list = grocery_list.drop_duplicates(["ingredient"])

    # get all food categories using USDA data
    grocery_list = get_food_categories(grocery_list, config)
    # TODO convert all masses to grams
    print(grocery_list.sort_values(by=["is_staple", "ingredient"]))
    print(grocery_list.shape)

    grocery_list_sub = grocery_list[["ingredient", "is_staple", "group"]]
    grocery_list_sub.to_csv(config.master_list_out_file, index=False)
    print("Master list written to {}".format(config.master_list_out_file))


def main():
    parser = generate_parser()
    args = parser.parse_args()

    recipes = read_recipes(args)

    generate_master_list(args, recipes,
                         only_rated=args.only_rated)

    return 0


if __name__ == '__main__':
    main()
