from pathlib import Path

import pandas as pd
from sous_chef.menu.create_menu._menu_basic import FinalizedMenuSchema

abs_path = Path(__file__).parent.absolute()


def _get_menu_df(file_name: str) -> pd.DataFrame:
    menu = FinalizedMenuSchema.validate(
        pd.read_csv(abs_path / file_name, dtype={"uuid": str}, header=0)
    )
    menu.eat_unit.fillna("", inplace=True)
    menu.uuid.fillna("NaN", inplace=True)
    menu.cook_datetime = pd.to_datetime(menu.cook_datetime)
    menu.prep_datetime = pd.to_datetime(menu.prep_datetime)
    menu.time_total = pd.to_timedelta(menu.time_total)
    return menu


def get_tmp_menu() -> pd.DataFrame:
    # TODO figure out why differs by 30 minutes from final_menu entries
    return _get_menu_df("tmp-menu.csv")


def get_final_grocery_list() -> pd.DataFrame:
    final_grocery_list = pd.read_csv(
        abs_path / "final_grocery_list.csv", dtype={"barcode": str}, header=0
    )
    final_grocery_list.barcode.fillna("", inplace=True)
    final_grocery_list.from_recipe = final_grocery_list.from_recipe.apply(
        lambda cell: cell[1:-1].split(", ")
    )
    final_grocery_list.for_day_str = final_grocery_list.for_day_str.apply(
        lambda cell: cell[1:-1].split(", ")
    )
    final_grocery_list.for_day = pd.to_datetime(final_grocery_list.for_day)
    return final_grocery_list


def get_final_menu() -> pd.DataFrame:
    return _get_menu_df("final_menu.csv")


def get_local_recipe_book_path():
    return abs_path


def get_menu_history():
    menu_history = pd.read_csv(
        abs_path / "menu_history.csv", dtype={"uuid": str}, header=0
    )
    menu_history.cook_datetime = pd.to_datetime(menu_history.cook_datetime)
    menu_history.uuid.fillna("NaN", inplace=True)
    return menu_history


def get_tasks_menu() -> pd.DataFrame:
    tasks_menu = pd.read_csv(abs_path / "tasks_menu.csv", header=0)
    tasks_menu.labels = tasks_menu.labels.apply(
        lambda cell: cell[1:-1].split(", ")
    )
    return tasks_menu


def get_tasks_grocery_list() -> pd.DataFrame:
    tasks_menu = pd.read_csv(abs_path / "tasks_grocery_list.csv", header=0)
    tasks_menu.labels = tasks_menu.labels.apply(
        lambda cell: cell[1:-1].split(", ")
    )
    return tasks_menu
