import hydra
import pandas as pd
from omegaconf import DictConfig
from sous_chef.grocery_list.generate_grocery_list.make_grocery_list import (
    GroceryList,
)
from sous_chef.rtk.read_write_rtk import RtkService
from structlog import get_logger

from utilities.api.todoist_api import TodoistHelper

LOGGER = get_logger(__name__)


def run_grocery_list(config: DictConfig) -> pd.DataFrame:
    if config.grocery_list.run_mode.only_clean_todoist_mode:
        todoist_helper = TodoistHelper(config.api.todoist)
        LOGGER.info(
            "Deleting previous tasks in project {}".format(
                config.grocery_list.todoist.project_name
            )
        )
        todoist_helper.delete_all_items_in_project(
            config.grocery_list.todoist.project_name
        )
    else:
        # unzip latest recipe versions
        rtk_service = RtkService(config.rtk)
        rtk_service.unzip()

        grocery_list = GroceryList(config=config)
        raw_grocery_df = grocery_list.extract_ingredients_from_menu()
        grocery_list_df, prep_task_df = grocery_list.prepare_grocery_list(
            raw_grocery_df=raw_grocery_df
        )

        if config.grocery_list.run_mode.with_todoist:
            grocery_list.export_to_todoist(
                grocery_list_df=grocery_list_df, prep_task_df=prep_task_df
            )
        return grocery_list_df


@hydra.main(
    config_path="../../config", config_name="grocery_list", version_base=None
)
def main(config: DictConfig) -> None:
    run_grocery_list(config=config)


if __name__ == "__main__":
    main()
