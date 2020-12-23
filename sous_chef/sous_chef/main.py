import argparse
from pathlib import Path

from create_menu import create_menu
from read_recipes import read_recipes

CWD = Path(__file__).absolute().parent


def generate_parser():
    parser = argparse.ArgumentParser(description='sous chef activities')
    subparser = parser.add_subparsers()

    parser.add_argument("--recipe_path", type=Path,
                        default=Path(CWD, "../recipe_data"))
    parser.add_argument("--recipe_pattern", type=str,
                        default="recipes*.json")

    menu_parser = subparser.add_parser('menu')
    menu_parser.set_defaults(which='menu')
    menu_parser.add_argument('--template_path', type=Path,
                             default=Path(CWD, "../menu_template"))
    menu_parser.add_argument('--template', type=str,
                             default="four_day_cook_week.yml")

    shopping_list_parser = subparser.add_parser('shopping_list')
    shopping_list_parser.set_defaults(which='shopping_list')
    return parser


def main():
    parser = generate_parser().parse_args()
    recipes = read_recipes(parser)

    if parser.which == 'menu':
        create_menu(parser, recipes)


if __name__ == '__main__':
    main()
