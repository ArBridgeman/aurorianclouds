from jellyfin_helpers.jellyfin_api import Jellyfin
from jellyfin_helpers.utils import get_config
from jellyfin_helpers.workout_plan.export_plan import PlanExporter
from jellyfin_helpers.workout_plan.get_workouts import WorkoutVideos
from jellyfin_helpers.workout_plan.plan_workouts import WorkoutPlanner

from utilities.api.gsheets_api import GsheetsHelper

if __name__ == "__main__":
    config = get_config(config_name="plan_workouts")

    jellyfin = Jellyfin(config=config.jellyfin_api)
    gsheets_helper = GsheetsHelper(config=config.gsheets)

    # load workout library videos
    workout_videos_df = WorkoutVideos(
        app_config=config.plan_workouts, jellyfin=jellyfin
    ).parse_workout_videos()

    # create workout plan
    workout_planner = WorkoutPlanner(
        app_config=config.plan_workouts,
        jellyfin=jellyfin,
        workout_videos=workout_videos_df,
    )
    workout_plan = workout_planner.create_workout_plan(
        gsheets_helper=gsheets_helper
    )

    # export workout plan
    plan_exporter = PlanExporter(
        app_config=config.plan_workouts, plan=workout_plan
    )
    # -- overwrites existing data in gsheets
    plan_exporter.export_to_gsheets(gsheets_helper=gsheets_helper)
    # plan_exporter.export_to_jellyfin_playlist(jellyfin=jellyfin)
    # plan_exporter.export_to_todoist(
    #     todoist_helper=TodoistHelper(config=config.todoist)
    # )
