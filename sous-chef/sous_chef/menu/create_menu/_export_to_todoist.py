from datetime import date, datetime, timedelta
from typing import Union

import pandas as pd
from omegaconf import DictConfig
from pandera.typing.common import DataFrameBase
from sous_chef.date.get_due_date import DueDatetimeFormatter
from sous_chef.menu.create_menu.models import TmpMenuSchema, Type, YesNo

from utilities.api.todoist_api import TodoistHelper


class MenuForTodoist:
    def __init__(
        self,
        config: DictConfig,
        final_menu_df: DataFrameBase[TmpMenuSchema],
        due_date_formatter: DueDatetimeFormatter,
        todoist_helper: TodoistHelper,
    ):
        # data classes
        self.due_date_formatter = due_date_formatter
        self.dataframe = final_menu_df
        self.todoist_helper = todoist_helper
        # settings
        self.project_name = config.project_name
        self.remove_existing_task = config.remove_existing_task
        self.task_priority = config.task_priority
        self.calendar_week = self.due_date_formatter.get_calendar_week()
        self.app_week_label = f"app-week-{self.calendar_week}"
        # external service
        self.project_id = todoist_helper.get_project_id(self.project_name)

    def upload_menu_to_todoist(self) -> None:
        if self.remove_existing_task:
            self.todoist_helper.delete_all_items_in_project(
                self.project_name,
                only_with_label=self.app_week_label,
            )

        edit_task_id = self._add_task(
            task_name=f"edit recipes from week #{self.calendar_week}",
            task_due_date=self.due_date_formatter.get_anchor_date()
            + timedelta(days=6),
        )

        for _, row in self.dataframe.iterrows():
            task = self._format_task_name(row)
            # task for when to cook
            self._add_task(task_name=task, task_due_date=row.cook_datetime)
            # task reminder to edit recipes
            if row["type"] == Type.recipe.value:
                rating_label = "(unrated)"
                if not pd.isnull(row["rating"]):
                    rating_label = f"({row['rating']})"
                self._add_task(
                    task_name=f"{row['item']} {rating_label}",
                    parent_id=edit_task_id,
                )
            # task for separate preparation step
            if row.cook_datetime != row.prep_datetime:
                self._add_task(
                    task_name=f"[PREP] {task}", task_due_date=row.prep_datetime
                )
            # task for defrosting
            if row.defrost == YesNo.yes.value:
                self._add_task(
                    task_name=f"[DEFROST] {task}",
                    task_due_date=row.cook_datetime - timedelta(days=1),
                )

    def _add_task(
        self,
        task_name: str,
        task_due_date: Union[date, datetime] = None,
        parent_id: str = None,
    ) -> str:
        task_object = self.todoist_helper.add_task_to_project(
            task=task_name,
            project=self.project_name,
            project_id=self.project_id,
            due_date=task_due_date,
            priority=self.task_priority,
            parent_id=parent_id,
            label_list=[self.app_week_label],
        )
        return task_object.id

    @staticmethod
    def _format_task_name(row: pd.Series) -> str:
        if row.defrost == YesNo.yes.value:
            return row["item"]

        factor_str = f"x eat: {row.eat_factor}"
        if row.freeze_factor > 0:
            factor_str += f", x freeze: {row.freeze_factor}"

        time_total = int(row.time_total.total_seconds() / 60)
        return f"{row['item']} ({factor_str}) [{time_total} min]"
