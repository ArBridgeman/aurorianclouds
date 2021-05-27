from pathlib import Path

import pandas as pd

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


def finalize_fixed_menu(menu_path: Path, menu_number: int):
    fixed_menu = obtain_fixed_menu(menu_path, menu_number)
    checked_menu = check_menu(fixed_menu)
    tmp_menu = Path(menu_path, "menu-tmp.csv")
    checked_menu.reset_index(drop=True).to_csv(tmp_menu, index=False, header=True)
