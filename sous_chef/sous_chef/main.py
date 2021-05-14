#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Main sous_chef steering file.
#
#
import sys
import argparse
from pathlib import Path

from create_menu import create_menu
from grocery_list.generate_grocery_list import generate_grocery_list
from read_recipes import read_calendar, read_recipes

ABS_FILE_PATH = Path(__file__).absolute().parent


def generate_parser():
    parser = argparse.ArgumentParser(description="sous chef activities")
    sub_parser = parser.add_subparsers(help="type of operation")

    parser.add_argument("--sender", type=str, default="ariel.m.schulz@gmail.com")
    parser.add_argument(
        "--recipient",
        type=str,
        default="ariel.bridgeman@gmail.com, alex.transporter@gmail.com",
    )

    parser.add_argument(
        "--menu_path", type=Path, default=Path(ABS_FILE_PATH, "../food_plan")
    )

    parser.add_argument(
        "--recipe_path", type=Path, default=Path(ABS_FILE_PATH, "../recipe_data")
    )
    parser.add_argument("--recipe_pattern", type=str, default="recipes*.json")
    parser.add_argument("--calendar_file", type=str, default="calendar.json")
    parser.add_argument(
        "--master_list_file",
        type=Path,
        default=Path(ABS_FILE_PATH, "../nutrition_data/master_ingredient_list.csv")
    )
    parser.add_argument(
        "--todoist_token_file",
        type=Path,
        default=Path(ABS_FILE_PATH, "./todoist_token.txt")
    )
    parser.add_argument(
        "--no_mail",
        action="store_true",
        help="Do not send menu by mail, only save it locally."
    )
    parser.add_argument(
        "--food_items_file",
        type=Path,
        default=Path(ABS_FILE_PATH, "../nutrition_data/food_items.feather")
    )

    menu_parser = sub_parser.add_parser("menu")
    menu_parser.set_defaults(which="menu")
    menu_parser.add_argument(
        "--template_path", type=Path, default=Path(ABS_FILE_PATH, "../menu_template")
    )
    menu_parser.add_argument("--template", type=str, default="four_day_cook_week.yml")
    menu_parser.add_argument(
        "--print_menu",
        action="store_true",
        help="Print out the generated menu on the "
             "terminal in addition to saving it!",
    )
    menu_parser.add_argument(
        "--interactive_menu",
        action="store_true",
        help="Build menu interactively using the terminal instead of having it"
             "automatically build."
    )

    menu_parser.add_argument("--email", type=str, default="base_email.html")
    menu_parser.add_argument("--cuisine", type=str, default="cuisine_map.yml")

    grocery_list_parser = sub_parser.add_parser("grocery_list")
    grocery_list_parser.set_defaults(which="grocery_list")
    grocery_list_parser.add_argument("--menu_file", type=str)
    grocery_list_parser.add_argument(
        "--grocery_list_path", type=str, default=Path(ABS_FILE_PATH, "../grocery_list")
    )
    grocery_list_parser.add_argument(
        "--staple_ingredients_file", type=str, default="staple_ingredients.yml"
    )
    grocery_list_parser.add_argument(
        "--no_upload",
        action="store_true",
        help="Deactivate Todoist upload for this run.",
    )
    grocery_list_parser.add_argument(
        "--interactive_grouping",
        action="store_true",
        help="Will ask for user input for uncertain food groups.",
    )
    grocery_list_parser.add_argument(
        "--clean_todoist",
        action="store_true",
        help="Will clean previously existing items/tasks in Groceries project.",
    )

    # grocery_list_parser.add_argument(
    #     "--test_todoist_mode",
    #     action="store_true",
    #     help="Will add (test) to grocery entry and delete according entries.",
    # )
    return parser


def main():
    parser = generate_parser()
    args = parser.parse_args()

    if len(sys.argv) <= 1:
        parser.print_help()
        return

    recipes = read_recipes(args)

    if args.which == "menu":
        calendar = read_calendar(args, recipes)
        create_menu(args, recipes, calendar)

    elif args.which == "grocery_list":
        generate_grocery_list(args, recipes)


if __name__ == "__main__":
    main()
