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
from sous_chef.menu.create_manual_menu import create_menu
from sous_chef.recipe_book.read_recipe_book import read_calendar, read_recipes

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


if __name__ == "__main__":
    main()
