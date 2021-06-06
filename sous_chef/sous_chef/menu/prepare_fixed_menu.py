import argparse
import datetime
import re
from pathlib import Path

import pandas as pd
from definitions import DAYS_OF_WEEK
from messaging.todoist_api import TodoistHelper

MENU_FILE_PATTERN = lambda num: f"menu-{num}.csv"


def obtain_fixed_menu(menu_path: Path, menu_number: int):
    fixed_menu_file = MENU_FILE_PATTERN(menu_number)
    fixed_menu = Path(menu_path, fixed_menu_file)
    if fixed_menu.is_file():
        return pd.read_csv(fixed_menu)
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
    return fixed_menu.groupby("weekday", sort=False).apply(
        lambda group: check_menu_by_day(group)
    )


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
        NotImplementedError("Functionality is not implemented for menu at the moment!")
        # if not dry_mode:
        #     [todoist_helper.delete_all_items_in_project(project_name) for i in range(3)]

    if dry_mode:
        print("Dry mode! Will only simulate actions but not upload to todoist!")

    get_datetime = lambda date, day: date + datetime.timedelta(
        days=(day - date.weekday() + 7) % 7
    )
    in_day_time_hour = {"morning": "8:00", "evening": "18:30"}

    for _, item in menu.iterrows():

        if item.menu_list != "Y":
            continue

        weekday = item.weekday
        time_in_day = "evening"  # by default dinner entry
        if "_" in weekday:
            weekday, time_in_day = weekday.split("_")
        weekday = DAYS_OF_WEEK.index(weekday.lower())

        due_date = get_datetime(datetime.datetime.today(), weekday)
        if due_date.date() == datetime.date.today():
            due_date = due_date + datetime.timedelta(days=7)

        in_day_split = in_day_time_hour[time_in_day].split(":")
        due_date = due_date.replace(
            hour=int(in_day_split[0]), minute=int(in_day_split[1]), second=0
        )

        cooking_time_min = (
            int(item.totalTime.total_seconds() / 60)
            if not pd.isna(item.totalTime)
            else None
        )
        due_date = due_date - datetime.timedelta(minutes=cooking_time_min or 20)

        due_date = due_date.strftime("on %Y-%m-%d at %H:%M")
        due_dict = {"string": due_date}

        formatted_item = "{} (x {}){}".format(
            item["item"],
            item.factor,
            " [{:d} min]".format(cooking_time_min) if cooking_time_min else "",
        )
        formatted_item = re.sub("\s+", " ", formatted_item).strip()
        print(
            "Adding item {:s} to todoist for date {}".format(formatted_item, due_date)
        )
        if not dry_mode:
            todoist_helper.add_item_to_project(
                formatted_item,
                project_name,
                section=None,
                labels=None,
                due_dict=due_dict,
            )


def join_recipe_information(
    checked_menu: pd.DataFrame,
    recipes: pd.DataFrame,
    add_columns: list = ["cookingTime", "totalTime", "rating"],
) -> pd.DataFrame:
    from grocery_list.grocery_matching_mapping import get_fuzzy_match

    match_helper = lambda item: get_fuzzy_match(
        item, recipes.title.values, warn=True, limit=1, reject=98
    )[0][0]
    checked_menu_recipes_filter = checked_menu.type == "recipe"
    checked_menu_recipes = checked_menu[checked_menu_recipes_filter].copy()
    checked_menu_additions = checked_menu[~checked_menu_recipes_filter].copy()

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

    return pd.concat([checked_menu_recipes, checked_menu_additions], ignore_index=True)


def finalize_fixed_menu(
    menu_path: Path, menu_number: int, recipes: pd.DataFrame, config: argparse.Namespace
):
    fixed_menu = obtain_fixed_menu(menu_path, menu_number)
    # checked_menu = check_menu(fixed_menu)
    checked_menu = fixed_menu
    checked_menu = join_recipe_information(checked_menu, recipes)
    checked_menu = checked_menu.sort_values("weekday")
    # saving
    tmp_menu = Path(menu_path, "menu-tmp.csv")
    checked_menu.reset_index(drop=True).to_csv(tmp_menu, index=False, header=True)
    # uploading
    if not config.no_upload:
        upload_menu_to_todoist(
            checked_menu,
            dry_mode=False,
            todoist_token_file_path=config.todoist_token_file,
        )
