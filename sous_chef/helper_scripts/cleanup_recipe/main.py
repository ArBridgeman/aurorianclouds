import argparse
from pathlib import Path

from convert_unit import convert_to_desired_unit
from read_recipe import read_recipes
from standardize_unit_value import standardize_unit_values

count = 0
# from standardize_unit_name import standardize_unit_names

ABS_FILE_PATH = Path(__file__).absolute().parent


def generate_parser():
    parser = argparse.ArgumentParser(description="sous chef activities")
    parser.add_argument(
        "--recipe_path", type=Path, default=Path(ABS_FILE_PATH, "../../recipe_data")
    )
    parser.add_argument("--recipe_pattern", type=str, default="recipes*.json")
    return parser


def transform_ingredient_line(ingredient_line):
    print(ingredient_line)
    std_ingredient_line = standardize_unit_values(ingredient_line)
    # standard_ingredient_line = standardize_unit_names(standard_ingredient_line)
    std_ingredient_line = convert_to_desired_unit(std_ingredient_line)
    return std_ingredient_line


def split_ingredients_perform_operation(row_ingredients):
    global count
    print(count)
    split_ingredients = row_ingredients.split("\n")
    transformed_ingredients = [transform_ingredient_line(line_ingredient) for line_ingredient in split_ingredients]
    count += 1
    return "\n".join(transformed_ingredients)


def main():
    parser = generate_parser()
    args = parser.parse_args()

    orig_recipes = read_recipes(args)
    orig_recipes["modified_ingredients"] = orig_recipes.ingredients.apply(
        lambda row: split_ingredients_perform_operation(row))
    orig_recipes[["title", "ingredients", "modified_ingredients"]].to_csv("recipes.csv")


if __name__ == "__main__":
    main()
