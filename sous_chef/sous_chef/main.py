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
from generate_grocery_list import generate_grocery_list
from read_recipes import read_calendar, read_recipes

CWD = Path(__file__).absolute().parent


def generate_parser():
    parser = argparse.ArgumentParser(description='sous chef activities')
    sub_parser = parser.add_subparsers(help="type of operation")

    parser.add_argument("--sender", type=str, default="ariel.m.schulz@gmail.com")
    parser.add_argument("--recipient", type=str,
                        default="ariel.bridgeman@gmail.com, alex.transporter@gmail.com")

    parser.add_argument("--menu_path", type=Path,
                        default=Path(CWD, "../food_plan"))

    parser.add_argument("--recipe_path", type=Path,
                        default=Path(CWD, "../recipe_data"))
    parser.add_argument("--recipe_pattern", type=str,
                        default="recipes*.json")
    parser.add_argument("--calendar_file", type=str,
                        default="calendar.json")
    parser.add_argument("--no_mail", action="store_true",
                        help="Do not send menu by mail, only save it locally.")

    menu_parser = sub_parser.add_parser('menu')
    menu_parser.set_defaults(which='menu')
    menu_parser.add_argument('--template_path', type=Path,
                             default=Path(CWD, "../menu_template"))
    menu_parser.add_argument('--template', type=str,
                             default="four_day_cook_week.yml")

    menu_parser.add_argument('--email', type=str, default="base_email.html")
    menu_parser.add_argument('--cuisine', type=str, default="cuisine_map.yml")

    grocery_list_parser = sub_parser.add_parser('grocery_list')
    grocery_list_parser.set_defaults(which='grocery_list')
    grocery_list_parser.add_argument("--menu_file", type=str)
    return parser


def main():
    parser = generate_parser()
    args = parser.parse_args()

    if len(sys.argv) <= 1:
        parser.print_help()
        return

    recipes = read_recipes(args)

    if args.which == "menu":
        calendar = read_calendar(parser)
        create_menu(parser, recipes, calendar)

    elif parser.which == "grocery_list":
        generate_grocery_list(parser, recipes)


if __name__ == '__main__':
    main()
