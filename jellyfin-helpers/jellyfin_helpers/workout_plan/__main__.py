from typing import List

from jellyfin_helpers.jellyfin_api import Jellyfin
from jellyfin_helpers.utils import get_config
from jellyfin_helpers.workout_plan.get_workouts import WorkoutVideos
from jellyfin_helpers.workout_plan.plan_workouts import WorkoutPlanner
from workout_plan.export_plan import PlanExporter

from utilities.api.gsheets_api import GsheetsHelper
from utilities.api.todoist_api import TodoistHelper
from utilities.testing.todoist import DebugTodoistHelper, LocalTodoistConnection

config = get_config(config_name="plan_workouts")
workout_cfg = config.plan_workouts


def get_todoist_helper():
    if workout_cfg.debug:
        connection = LocalTodoistConnection()
        project_id = connection.add_project(workout_cfg.todoist.project)
        connection.add_section(
            section_name=workout_cfg.todoist.section, project_id=project_id
        )

        todoist_helper = DebugTodoistHelper(config.todoist)
        todoist_helper.set_connection(connection=connection)
        return todoist_helper
    return TodoistHelper(config=config.todoist)


class MockJellyfin:
    @staticmethod
    def post_add_to_playlist(playlist_name: str, item_ids: List[str]):
        print(f"playlist_name: {playlist_name}")
        print(f"... add item_ids: {item_ids}")


if __name__ == "__main__":
    jellyfin = Jellyfin(config=config.jellyfin)
    gsheets_helper = GsheetsHelper(config=config.gsheets)

    # load workout library videos
    workout_videos_df = WorkoutVideos(jellyfin=jellyfin).parse_workout_videos()

    # create workout plan
    workout_planner = WorkoutPlanner(
        app_config=workout_cfg,
        jellyfin=jellyfin,
        workout_videos=workout_videos_df,
    )
    workout_plan = workout_planner.create_workout_plan(
        gsheets_helper=gsheets_helper
    )

    # export workout plan
    plan_exporter = PlanExporter(app_config=workout_cfg, plan=workout_plan)
    # overwrites existing data in gsheets
    plan_exporter.export_to_gsheets(gsheets_helper=gsheets_helper)

    if workout_cfg.debug:
        plan_exporter.export_to_jellyfin_playlist(jellyfin=MockJellyfin())
    else:
        plan_exporter.export_to_jellyfin_playlist(jellyfin=jellyfin)

    plan_exporter.export_to_todoist(todoist_helper=get_todoist_helper())
