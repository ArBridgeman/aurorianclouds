import numpy as np
import pandas as pd
import pytest
from hydra import compose, initialize
from sous_chef.messaging.gsheets_api import GsheetsHelper


@pytest.fixture
def gsheets_helper():
    with initialize(config_path="../../config/messaging"):
        config = compose(config_name="gsheets_api")
        return GsheetsHelper(config.gsheets)


class TestGSheetsHelper:
    def test_valid_connection(self, gsheets_helper, check_dir="sous_chef"):
        files = gsheets_helper.connection.drive.list()
        found = [
            f
            for f in files
            if (
                f["name"] == check_dir
                and f["mimeType"] == "application/vnd.google-apps.folder"
            )
        ]
        assert (
            len(found) == 1
        ), "Could not verify valid google drive/sheets connection!"

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
    def test_get_sheet_as_df(
        self, gsheets_helper, test_workbook, test_sheet, expected_df
    ):
        assert np.all(
            gsheets_helper.get_sheet_as_df(test_workbook, test_sheet)
            == expected_df
        ), "Could not validate reading of test df!"

    @pytest.mark.parametrize(
        "test_workbook, test_sheet, write_df",
        [
            (
                "unit_test_sheet",
                "test_sheet_2",
                pd.DataFrame(
                    {
                        "Vars": ["a", "b", "b", "d"],
                        "Vals": [1, 2, 3, pd.datetime.now().strftime("%H%M%S")],
                    }
                ),
            )
        ],
    )
    def test_write_df_to_sheet(
        self, gsheets_helper, test_workbook, test_sheet, write_df
    ):
        gsheets_helper.write_df_to_sheet(
            write_df, test_sheet, test_workbook, copy_index=False
        )
        write_df["Vals"] = write_df["Vals"].astype(int)
        read_df = gsheets_helper.get_sheet_as_df(test_workbook, test_sheet)
        read_df["Vals"] = read_df["Vals"].astype(int)
        assert np.all(
            read_df == write_df
        ), "Could not validate writing of test dataframe to Google drive!"
