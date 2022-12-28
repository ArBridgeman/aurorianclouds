from pathlib import Path

import pytest
from requests.exceptions import HTTPError


def clean_up_add_todoist_task(todoist_helper, task_id: str):
    # delete task
    todoist_helper.connection.delete_task(task_id=task_id)

    # verify task was deleted
    with pytest.raises(HTTPError) as error:
        todoist_helper.connection.get_task(task_id=task_id)
    assert str(error.value) == (
        "404 Client Error: Not Found for url: "
        f"https://api.todoist.com/rest/v2/tasks/{task_id}"
    )


def get_location():
    return Path(__file__).parent.absolute()
