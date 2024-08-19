from typing import List

import hydra
from jellyfin_helpers.jellyfin_api import Jellyfin
from jellyfin_helpers.workout_plan.get_workouts import WorkoutVideos
from jellyfin_helpers.workout_plan.plan_workouts import WorkoutPlanner
from omegaconf import DictConfig
from workout_plan.export_plan import PlanExporter

from utilities.api.gsheets_api import GsheetsHelper
from utilities.api.todoist_api import TodoistHelper
from utilities.testing.todoist import DebugTodoistHelper, LocalTodoistConnection


def get_todoist_helper(app_config: DictConfig):
    workout_cfg = app_config.plan_workouts

    if workout_cfg.debug:
        connection = LocalTodoistConnection()
        project_id = connection.add_project(workout_cfg.todoist.project)
        connection.add_section(
            section_name=workout_cfg.todoist.section, project_id=project_id
        )

        todoist_helper = DebugTodoistHelper(app_config.todoist)
        todoist_helper.set_connection(connection=connection)
        return todoist_helper
    return TodoistHelper(config=app_config.todoist)


class MockJellyfin:
    @staticmethod
    def post_add_to_playlist(playlist_name: str, item_ids: List[str]):
        print(f"playlist_name: {playlist_name}")
        print(f"... add item_ids: {item_ids}")


@hydra.main(
    config_path="../../config", config_name="plan_workouts", version_base=None
)
def main(app_config: DictConfig):
    workout_cfg = app_config.plan_workouts

    jellyfin = Jellyfin(config=app_config.jellyfin)
    gsheets_helper = GsheetsHelper(config=app_config.gsheets)

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

    plan_exporter.export_to_todoist(
        todoist_helper=get_todoist_helper(app_config)
    )


if __name__ == "__main__":
    main()
