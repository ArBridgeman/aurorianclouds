#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Main sous_chef steering file.
#
#
import argparse
import sys
from pathlib import Path

import pandas as pd
from sous_chef.grocery_list.generate_grocery_list import generate_grocery_list
from sous_chef.menu.create_manual_menu import create_menu
from sous_chef.menu.prepare_fixed_menu import finalize_fixed_menu
from sous_chef.read_recipes import read_calendar, read_recipes

ABS_FILE_PATH = Path(__file__).absolute().parent
HOME_PATH = str(Path.home())

pd.set_option("display.max_rows", 500)
pd.set_option("display.max_columns", 500)
pd.set_option("display.width", 1000)


def generate_parser():
    parser = argparse.ArgumentParser(description="sous chef apps")
    sub_parser = parser.add_subparsers(help="type of operation")
    parse_default_settings(parser)
    parse_manual_menu(sub_parser)
    parse_fixed_menu(sub_parser)
    parse_grocery_list(sub_parser)
    return parser


def parse_default_settings(parser):
    parser.add_argument(
        "--sender", type=str, default="ariel.m.schulz@gmail.com"
    )
    parser.add_argument(
        "--recipient",
        type=str,
        default="ariel.bridgeman@gmail.com, alex.transporter@gmail.com",
    )
    parser.add_argument(
        "--menu_path", type=Path, default=Path(ABS_FILE_PATH, "../food_plan")
    )
    parser.add_argument(
        "--recetteTek_path",
        type=Path,
        default=Path(HOME_PATH, "./Dropbox/SharedApps/RecetteTek"),
    )
    parser.add_argument(
        "--master_list_file",
        type=Path,
        default=Path(
            ABS_FILE_PATH, "../nutrition_data/master_ingredient_list.csv"
        ),
    )
    parser.add_argument(
        "--todoist_token_file",
        type=Path,
        default=Path(ABS_FILE_PATH, "tokens/todoist_token.txt"),
    )
    parser.add_argument(
        "--google_drive_secret_file",
        type=Path,
        default=Path(ABS_FILE_PATH, "tokens/google_client_key.json"),
    )
    parser.add_argument(
        "--no_mail",
        action="store_true",
        help="Do not send menu by mail, only save it locally.",
    )
    parser.add_argument(
        "--food_items_file",
        type=Path,
        default=Path(ABS_FILE_PATH, "../nutrition_data/food_items.feather"),
    )


def parse_fixed_menu(sub_parser):
    fixed_menu_parser = sub_parser.add_parser("fixed_menu")
    fixed_menu_parser.set_defaults(which="fixed_menu")
    fixed_menu_parser.add_argument(
        "--fixed_menu_path",
        type=Path,
        default=Path(ABS_FILE_PATH, "../food_plan/fixed_menu"),
    )
    fixed_menu_parser.add_argument(
        "--google_drive_menu_prefix", type=str, default="menu-"
    )
    fixed_menu_parser.add_argument(
        "--fixed_menu_number", type=int, required=True
    )

    fixed_menu_parser.add_argument(
        "--dry_mode",
        action="store_true",
        help="Perform a dry run printing actions to terminal.",
    )
    fixed_menu_parser.add_argument(
        "--menu_sorting",
        type=str,
        default="original",
    )
    fixed_menu_parser.add_argument(
        "--no_cleaning",
        action="store_true",
        help="Do not clean previously existing tasks in Menu project.",
    )


def parse_grocery_list(sub_parser):
    grocery_list_parser = sub_parser.add_parser("grocery_list")
    grocery_list_parser.set_defaults(which="grocery_list")
    grocery_list_parser.add_argument(
        "--menu_file",
        type=str,
        default=Path(ABS_FILE_PATH, "../food_plan/fixed_menu/menu-tmp.csv"),
    )
    grocery_list_parser.add_argument(
        "--grocery_list_path",
        type=str,
        default=Path(ABS_FILE_PATH, "../grocery_list"),
    )
    grocery_list_parser.add_argument(
        "--staple_ingredients_file", type=str, default="staple_ingredients.yml"
    )
    grocery_list_parser.add_argument(
        "--interactive_grouping",
        action="store_true",
        help="Will ask for user input for uncertain food groups.",
        required=False,
    )
    grocery_list_parser.add_argument(
        "--no_cleaning",
        action="store_true",
        help="Do not clean previously existing tasks in Groceries project.",
        required=False,
    )
    grocery_list_parser.add_argument(
        "--dry_mode",
        action="store_true",
        help="Perform a dry run by printing actions to terminal.",
        required=False,
    )
    grocery_list_parser.add_argument(
        "--only_clean_todoist",
        action="store_true",
        help="Remove existing entries in todoist (and nothing else).",
        required=False,
    )
    grocery_list_parser.add_argument(
        "--add_bean_cans_for_freezing",
        type=int,
        default=1,
        help="Will bump quantity of cans to prepare for freezing.",
        required=False,
    )


def parse_manual_menu(sub_parser):
    manual_menu = sub_parser.add_parser("manual_menu")
    manual_menu.set_defaults(which="manual_menu")
    manual_menu.add_argument(
        "--template_path",
        type=Path,
        default=Path(ABS_FILE_PATH, "../menu_template"),
    )
    manual_menu.add_argument(
        "--template", type=str, default="four_day_cook_week.yml"
    )
    manual_menu.add_argument(
        "--print_menu",
        action="store_true",
        help="Print out the generated menu on the "
        "terminal in addition to saving it!",
    )
    manual_menu.add_argument(
        "--interactive_menu",
        action="store_true",
        help="Build menu interactively using the terminal instead of having it"
        "automatically build.",
    )
    manual_menu.add_argument("--email", type=str, default="base_email.html")
    manual_menu.add_argument("--cuisine", type=str, default="cuisine_map.yml")


def main():
    parser = generate_parser()
    args = parser.parse_args()

    if len(sys.argv) <= 1:
        parser.print_help()
        return

    recipes = read_recipes(args.recetteTek_path)

    if args.which == "manual_menu":
        calendar = read_calendar(args.recetteTek_path, recipes)
        create_menu(args, recipes, calendar)

    elif args.which == "fixed_menu":
        finalize_fixed_menu(args, recipes)

    elif args.which == "grocery_list":
        generate_grocery_list(args, recipes)


if __name__ == "__main__":
    main()
