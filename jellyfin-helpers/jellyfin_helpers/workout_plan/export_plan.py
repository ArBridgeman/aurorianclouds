from jellyfin_helpers.jellyfin_api import Jellyfin
from jellyfin_helpers.workout_plan.plan_workouts import WorkoutPlan
from omegaconf import DictConfig
from pandera.typing.common import DataFrameBase

from utilities.api.gsheets_api import GsheetsHelper
from utilities.api.todoist_api import TodoistHelper


class PlanExporter:
    def __init__(
        self, app_config: DictConfig, plan: DataFrameBase[WorkoutPlan]
    ):
        self.app_config = app_config
        self.plan = plan

    def export_to_gsheets(self, gsheets_helper: GsheetsHelper):
        gsheets_helper.write_worksheet(
            df=self.plan,
            workbook_name=self.app_config.gsheets.workbook,
            worksheet_name=self.app_config.gsheets.plan_worksheet,
        )

    def export_to_jellyfin_playlist(self, jellyfin: Jellyfin):
        for week, values in self.plan.groupby(["week"]):
            jellyfin.post_add_to_playlist(
                playlist_name=self.app_config.jellyfin[f"playlist_{week}"],
                item_ids=values.item_id.values,
            )

    def export_to_todoist(self, todoist_helper: TodoistHelper):
        for group_conditions, values in self.plan.groupby(
            ["title", "week", "day", "total_in_min"]
        ):
            title, week, day, total_in_min = group_conditions

            todoist_helper.add_task_to_project(
                task=f"[wk {week}] {title['values']} ({total_in_min} min)",
                due_string=f"in {day} days",
                project=self.app_config.todoist.project,
                section=self.app_config.todoist.section,
                description="\n".join(values.description.values),
                priority=self.app_config.todoist.task_priority,
                label_list=["health"],
            )
