from datetime import date, datetime, timedelta
from typing import List, Union

import pandas as pd
from sous_chef.menu.create_menu._menu_basic import MenuBasic
from todoist_api_python.models import Task

from utilities.api.todoist_api import TodoistHelper


class MenuForTodoist(MenuBasic):
    def upload_menu_to_todoist(
        self, todoist_helper: TodoistHelper
    ) -> List[Task]:
        project_name = self.config.todoist.project_name
        calendar_week = self.due_date_formatter.get_calendar_week()
        app_week_label = f"app-week-{calendar_week}"

        if self.config.todoist.remove_existing_task:
            todoist_helper.delete_all_items_in_project(
                project_name,
                only_with_label=app_week_label,
            )

        tasks = []
        project_id = todoist_helper.get_project_id(project_name)

        def _add_task(
            task_name: str,
            task_due_date: Union[date, datetime] = None,
            parent_id: str = None,
        ):
            task_object = todoist_helper.add_task_to_project(
                task=task_name,
                project=project_name,
                project_id=project_id,
                due_date=task_due_date,
                priority=self.config.todoist.task_priority,
                parent_id=parent_id,
                label_list=[app_week_label],
            )
            tasks.append(task_object)
            return task_object

        edit_task = _add_task(
            task_name=f"edit recipes from week #{calendar_week}",
            task_due_date=self.due_date_formatter.get_anchor_date()
            + timedelta(days=6),
        )

        for _, row in self.dataframe.iterrows():
            task = self._format_task_name(row)
            # task for when to cook
            _add_task(task_name=task, task_due_date=row.cook_datetime)

            # task reminder to edit recipes
            if row["type"] == "recipe":
                rating_label = "(unrated)"
                if not pd.isnull(row["rating"]):
                    rating_label = f"({row['rating']})"
                _add_task(
                    task_name=f"{row['item']} {rating_label}",
                    parent_id=edit_task.id,
                )

            # task for separate preparation
            if row.cook_datetime != row.prep_datetime:
                _add_task(
                    task_name=f"[PREP] {task}", task_due_date=row.prep_datetime
                )
            if row.defrost == "Y":
                _add_task(
                    task_name=f"[DEFROST] {task}",
                    task_due_date=row.cook_datetime - timedelta(days=1),
                )
        return tasks

    @staticmethod
    def _format_task_name(row: pd.Series) -> str:
        if row.defrost == "Y":
            return row["item"]

        factor_str = f"x eat: {row.eat_factor}"
        if row.freeze_factor > 0:
            factor_str += f", x freeze: {row.freeze_factor}"

        time_total = int(row.time_total.total_seconds() / 60)
        return f"{row['item']} ({factor_str}) [{time_total} min]"
