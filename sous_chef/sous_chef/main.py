import argparse
from pathlib import Path

from create_menu import create_menu
from generate_grocery_list import generate_grocery_list
from read_recipes import read_calendar, read_recipes

CWD = Path(__file__).absolute().parent


def generate_parser():
    parser = argparse.ArgumentParser(description='sous chef activities')
    subparser = parser.add_subparsers()

    parser.add_argument("--sender", type=str, default="ariel.m.schulz@gmail.com")
    parser.add_argument("--recipient", type=str, default="ariel.bridgeman@gmail.com, alex.transporter@gmail.com")

    parser.add_argument("--menu_path", type=Path,
                        default=Path(CWD, "../food_plan"))

    parser.add_argument("--recipe_path", type=Path,
                        default=Path(CWD, "../recipe_data"))
    parser.add_argument("--recipe_pattern", type=str,
                        default="recipes*.json")
    parser.add_argument("--calendar_file", type=str,
                        default="calendar.json")

    menu_parser = subparser.add_parser('menu')
    menu_parser.set_defaults(which='menu')
    menu_parser.add_argument('--template_path', type=Path,
                             default=Path(CWD, "../menu_template"))
    menu_parser.add_argument('--template', type=str,
                             default="four_day_cook_week.yml")

    grocery_list_parser = subparser.add_parser('grocery_list')
    grocery_list_parser.set_defaults(which='grocery_list')
    grocery_list_parser.add_argument("--menu_file", type=str)
    return parser


def main():
    parser = generate_parser().parse_args()
    recipes = read_recipes(parser)

    if parser.which == "menu":
        calendar = read_calendar(parser)
        create_menu(parser, recipes, calendar)

    elif parser.which == "grocery_list":
        generate_grocery_list(parser, recipes)


if __name__ == '__main__':
    main()
