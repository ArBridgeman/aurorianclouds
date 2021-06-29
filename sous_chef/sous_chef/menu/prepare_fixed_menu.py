import argparse
import datetime
import re
from pathlib import Path

import pandas as pd
from definitions import DAYS_OF_WEEK, DESIRED_MEAL_TIMES
from messaging.todoist_api import TodoistHelper

MENU_FILE_PATTERN = lambda num: f"menu-{num}.csv"


def obtain_fixed_menu(menu_path: Path, menu_number: int, sep: str = ";"):
    fixed_menu_file = MENU_FILE_PATTERN(menu_number)
    fixed_menu = Path(menu_path, fixed_menu_file)
    if fixed_menu.is_file():
        return pd.read_csv(fixed_menu, sep=sep)
    else:
        raise ValueError(f"{fixed_menu_file} does not exist")


def edit_menu_by_item(row):
    print(" editing ".center(20, "-"))
    changed_factor = input(f"new factor for {row['item']} (old: {row['factor']}): \n")
    row["factor"] = float(changed_factor)
    return row


def check_menu_by_day(group):
    tmp_group = group.copy()
    weekday = group.weekday.unique()[0]
    print(f" Menu for {weekday} ".center(40, "#"))
    print(group[["factor", "item"]])
    menu_status = input("menu [g]ood as is, [e]dit, or [d]elete:\n")

    if menu_status == "e":
        tmp_group = group.apply(lambda row: edit_menu_by_item(row), axis=1)
    elif menu_status == "d":
        return

    return tmp_group


def check_menu(fixed_menu: pd.DataFrame):
    return (
        fixed_menu.groupby("weekday", sort=False)
        .apply(lambda group: check_menu_by_day(group))
        .reset_index(drop=True)
    )


def get_anchor_date(weekday_index):
    today = datetime.datetime.today()
    return today + datetime.timedelta(days=max(0, weekday_index - today.weekday()))


def get_due_date(
    day, anchor_date=datetime.datetime.today(), hour=0, minute=0, second=0
):
    new_date = anchor_date + datetime.timedelta(
        days=(day - anchor_date.weekday() + 7) % 7
    )
    if new_date.date() == anchor_date.date():
        new_date = new_date + datetime.timedelta(days=7)

    new_date = new_date.replace(hour=int(hour), minute=int(minute), second=int(second))

    return new_date


def upload_menu_to_todoist(
    menu: pd.DataFrame,
    project_name: str = "Menu",
    dry_mode: bool = False,
    clean: bool = False,
    todoist_token_file_path="todoist_token.txt",
):
    print("Uploading finalized menu to todoist")

    todoist_helper = TodoistHelper(todoist_token_file_path)

    if clean:
        print("Cleaning previous items/tasks in project {:s}".format(project_name))
        if not dry_mode:
            [
                todoist_helper.delete_all_items_in_project(
                    project_name, no_recurring=False, only_app_generated=True
                )
                for i in range(3)
            ]

    if dry_mode:
        print("Dry mode! Will only simulate actions but not upload to Todoist!")

    for _, item in menu.iterrows():

        if item.menu_list != "Y":
            continue

        time_in_day = "evening"  # by default dinner entry

        weekday = item.weekday
        if "_" in weekday:
            weekday, time_in_day = weekday.split("_")
        weekday_index = DAYS_OF_WEEK.index(weekday.lower())

        in_day_split = DESIRED_MEAL_TIMES[time_in_day].split(":")
        due_date = get_due_date(
            weekday_index,
            get_anchor_date(4),
            hour=int(in_day_split[0]),
            minute=int(in_day_split[1]),
        )

        cooking_time_min = 20
        if not pd.isna(item.totalTime):
            cooking_time_min = int(item.totalTime.total_seconds() / 60)

        due_date = due_date - datetime.timedelta(minutes=cooking_time_min)
        due_date_str = due_date.strftime("on %Y-%m-%d at %H:%M")
        due_dict = {"string": due_date_str}

        formatted_item = "{} (x {}){}".format(
            item["item"],
            item.factor,
            " [{:d} min]".format(cooking_time_min)
            if not pd.isna(item.totalTime)
            else "",
        )
        formatted_item = re.sub("\s+", " ", formatted_item).strip()
        print(
            "Adding item {:s} to todoist for date {}".format(
                formatted_item, due_date_str
            )
        )
        if not dry_mode:
            todoist_helper.add_item_to_project(
                formatted_item,
                project_name,
                due_date_dict=due_dict,
            )


def join_recipe_information(
    checked_menu: pd.DataFrame,
    recipes: pd.DataFrame,
    add_columns: list = ["cookingTime", "totalTime", "rating"],
) -> pd.DataFrame:
    from grocery_list.grocery_matching_mapping import get_fuzzy_match

    checked_menu = checked_menu.reset_index()
    match_helper = lambda item: get_fuzzy_match(
        item, recipes.title.values, warn=True, limit=1, reject=95, warn_thresh=95
    )[0][0]
    checked_menu_recipes_filter = checked_menu.type == "recipe"
    checked_menu_recipes = checked_menu[checked_menu_recipes_filter].copy()
    checked_menu_ingredients = checked_menu[~checked_menu_recipes_filter].copy()

    checked_menu_recipes["best_match"] = checked_menu_recipes["item"].apply(
        match_helper
    )

    checked_menu_recipes = pd.merge(
        checked_menu_recipes,
        recipes[add_columns + ["title"]],
        left_on="best_match",
        right_on="title",
        how="left",
    ).drop(columns=["title", "best_match"])

    df_concat = pd.concat([checked_menu_recipes, checked_menu_ingredients])
    df_concat = df_concat.sort_values("index").drop(columns="index")

    return df_concat


def finalize_fixed_menu(config: argparse.Namespace, recipes: pd.DataFrame):
    menu_path = config.fixed_menu_path
    menu_number = config.fixed_menu_number
    fixed_menu = obtain_fixed_menu(menu_path, menu_number)
    checked_menu = check_menu(fixed_menu)
    checked_menu = join_recipe_information(checked_menu, recipes)
    if config.menu_sorting != "original":
        checked_menu = checked_menu.sort_values(config.menu_sorting)
    # saving
    tmp_menu = Path(menu_path, "menu-tmp.csv")
    checked_menu.reset_index(drop=True).to_csv(
        tmp_menu, index=False, header=True, sep=";"
    )
    # uploading
    upload_menu_to_todoist(
        checked_menu,
        clean=not config.no_cleaning,
        dry_mode=config.dry_mode,
        todoist_token_file_path=config.todoist_token_file,
    )
