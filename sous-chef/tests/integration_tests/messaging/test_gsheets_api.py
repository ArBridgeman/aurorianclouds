import string
from random import choice

import pandas as pd
import pytest
from tests.util import assert_equal_dataframe


def random_string(length: int):
    pool = string.ascii_lowercase + string.digits
    return "".join(choice(pool) for i in range(length))


@pytest.mark.gsheets
class TestGSheetsHelper:
    @staticmethod
    def test_write_and_read_worksheet(gsheets_helper):
        workbook_name = random_string(12)
        worksheet_name = "test"
        fake_df = pd.DataFrame({"Vars": ["a", "b"], "Vals": [1.1, 2.4]})

        gsheets_helper.write_worksheet(fake_df, workbook_name, worksheet_name)
        worksheet = gsheets_helper.get_worksheet(workbook_name, worksheet_name)
        # clean-up
        workbook_id = gsheets_helper._get_workbook(workbook_name).id
        gsheets_helper._delete_item(workbook_id)

        assert_equal_dataframe(worksheet, fake_df)

    @staticmethod
    def test__delete_item(gsheets_helper):
        folder_name = random_string(12)

        # run once to trigger create and get id
        folder_id = gsheets_helper._get_folder_id(folder_name)
        # clean-up
        gsheets_helper._delete_item(folder_id)

        assert gsheets_helper._perform_query("folder", folder_name) == []

    @staticmethod
    def test__get_folder_id_not_found_then_create(gsheets_helper, log):
        folder_name = random_string(12)

        # run once to trigger create and get id
        check1_folder_id = gsheets_helper._get_folder_id(folder_name)
        # run twice to retrieve and get id
        check2_folder_id = gsheets_helper._get_folder_id(folder_name)
        # delete folder for future usage
        gsheets_helper._delete_item(check1_folder_id)

        assert check1_folder_id == check2_folder_id
        assert log.events == [
            {
                "event": "[get_folder_id]",
                "level": "warning",
                "warn": "Could not locate folder",
                "folder_name": folder_name,
                "action": "Attempt to create one",
            }
        ]

    @staticmethod
    def test__get_workbook(gsheets_helper, log):
        workbook_name = random_string(12)

        # run once to trigger create and get id
        check1_workbook = gsheets_helper._get_workbook(workbook_name)
        # run once to trigger create and get id
        check2_workbook = gsheets_helper._get_workbook(workbook_name)

        # delete workbook for future usage
        gsheets_helper._delete_item(check1_workbook.id)

        assert check1_workbook == check2_workbook
        assert log.events == [
            {
                "event": "[get_workbook]",
                "level": "warning",
                "warn": "Could not locate workbook",
                "workbook_name": workbook_name,
                "action": "Attempt to create one",
            }
        ]

    @staticmethod
    def test__get_workbook_with_folder(gsheets_helper, log):
        folder_name = random_string(12)
        workbook_name = random_string(12)

        # run once to trigger create and get id
        check1_workbook = gsheets_helper._get_workbook(
            workbook_name, folder_name
        )
        # run once to trigger create and get id
        check2_workbook = gsheets_helper._get_workbook(
            workbook_name, folder_name
        )

        # delete workbook & folder for future usage
        folder_id = gsheets_helper._get_folder_id(folder_name)
        gsheets_helper._delete_item(check1_workbook.id)
        gsheets_helper._delete_item(folder_id)

        assert check1_workbook == check2_workbook
        assert log.events == [
            {
                "event": "[get_folder_id]",
                "level": "warning",
                "warn": "Could not locate folder",
                "folder_name": folder_name,
                "action": "Attempt to create one",
            },
            {
                "event": "[get_workbook]",
                "level": "warning",
                "warn": "Could not locate workbook",
                "workbook_name": workbook_name,
                "action": "Attempt to create one",
            },
        ]

    @staticmethod
    @pytest.mark.parametrize("mimetype", ["folder"])
    def test__perform_query(gsheets_helper, mimetype):
        fake_name = random_string(12)
        assert gsheets_helper._perform_query(mimetype, fake_name) == []
