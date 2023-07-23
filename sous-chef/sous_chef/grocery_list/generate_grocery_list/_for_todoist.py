from itertools import chain

from sous_chef.grocery_list.generate_grocery_list._grocery_list_basic import (
    GroceryListBasic,
    GroceryListIncompleteError,
)
from structlog import get_logger

from utilities.api.todoist_api import TodoistHelper

FILE_LOGGER = get_logger(__name__)


class GroceryListForTodoist(GroceryListBasic):
    def upload_grocery_list_to_todoist(self, todoist_helper: TodoistHelper):
        if self.has_errors:
            raise GroceryListIncompleteError(
                "will not send to ToDoist until fixed"
            )

        # TODO what should be in todoist (e.g. dry mode & messages?)
        project_name = self.config.todoist.project_name
        if self.config.todoist.remove_existing_task:
            todoist_helper.delete_all_items_in_project(
                project_name, only_with_label=self.app_week_label
            )

        for aisle_group, group in self.grocery_list.groupby(
            "aisle_group", as_index=False
        ):
            section_name = aisle_group
            if aisle_group in self.config.store_to_specialty_list:
                section_name = "Specialty"
            if aisle_group in self.config.todoist.skip_group:
                FILE_LOGGER.warning(
                    "[skip group]",
                    action="do not add to todoist",
                    section=section_name,
                    aisle_group=aisle_group,
                    ingredient_list=group["item"].values,
                )
                continue

            project_id = todoist_helper.get_project_id(project_name)
            section_id = todoist_helper.get_section_id(
                project_id=project_id, section_name=section_name
            )

            # TODO CODE-197 add barcode (and later item name in description)
            for _, entry in group.iterrows():
                todoist_helper.add_task_to_project(
                    task=self._format_ingredient_str(entry),
                    due_date=entry["shopping_date"],
                    label_list=entry["from_recipe"]
                    + entry["for_day_str"]
                    + [self.app_week_label],
                    description=str(entry["barcode"]),
                    project=project_name,
                    project_id=project_id,
                    section=section_name,
                    section_id=section_id,
                    priority=2
                    if entry["shopping_date"] != self.primary_shopping_date
                    else 1,
                )

    def send_preparation_to_todoist(self, todoist_helper: TodoistHelper):
        # TODO separate service? need freezer check for defrosts
        project_name = self.config.preparation.project_name
        if self.config.todoist.remove_existing_prep_task:
            todoist_helper.delete_all_items_in_project(
                project_name, only_with_label=self.app_week_label
            )

        if self.queue_preparation is not None:
            for _, row in self.queue_preparation.iterrows():
                todoist_helper.add_task_to_project(
                    task=row.task,
                    project=project_name,
                    label_list=list(
                        chain.from_iterable([row.from_recipe, row.for_day_str])
                    )
                    + ["prep", self.app_week_label],
                    due_date=row.due_date,
                    priority=self.config.preparation.task_priority,
                )
