import pathlib

import numpy as np
import pandas as pd
import pytest
from sous_chef.messaging.gsheets_api import GsheetsHelper

# todo: refactor to not have hardcoded path here
client_secret_path = (
    pathlib.Path(__file__).parent / ".." / ".." / "sous_chef" / "client_key.json"
)

gsheets_helper = GsheetsHelper(client_secret_path)


class TestGSheetsHelper:
    def test_valid_connection(self, check_dir="sous_chef"):
        files = gsheets_helper.connection.drive.list()
        found = [
            f
            for f in files
            if (
                f["name"] == check_dir
                and f["mimeType"] == "application/vnd.google-apps.folder"
            )
        ]
        assert len(found) == 1

    @pytest.mark.parametrize(
        "test_workbook, test_sheet, expected_df",
        [
            (
                "unit_test_sheet",
                "test_sheet_1",
                pd.DataFrame({"Vars": ["a", "b", "b"], "Vals": [1, 2, 3]}),
            )
        ],
    )
    def test_get_sheet_as_df(self, test_workbook, test_sheet, expected_df):
        assert np.all(
            gsheets_helper.get_sheet_as_df(test_workbook, test_sheet) == expected_df
        )
