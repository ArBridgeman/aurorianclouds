from dataclasses import dataclass
from pathlib import Path

import pygsheets
from omegaconf import DictConfig
from pandas import DataFrame
from structlog import get_logger

ABS_FILE_PATH = Path(__file__).absolute().parent

FILE_LOGGER = get_logger(__name__)


@dataclass
class GsheetsHelper:
    config: DictConfig

    def __post_init__(self):
        service_file = Path(ABS_FILE_PATH, self.config.service_file)
        self.connection = pygsheets.authorize(
            service_file=service_file, retries=3
        )

    def get_sheet_as_df(self, workbook_name: str, sheet_name: str) -> DataFrame:
        """
        Get tab sheet_name in workbook_name and return as df.

        :param workbook_name: name of workbook (str),
        :param sheet_name: name of sheet (str),
        :return: sheet converted to pandas dataframe.
        """
        FILE_LOGGER.info(
            "[get gsheet]", workbook_name=workbook_name, sheet_name=sheet_name
        )
        workbook = self.connection.open(workbook_name)
        sheet = workbook.worksheet_by_title(sheet_name)
        df = sheet.get_as_df()
        return df

    def write_df_to_sheet(
        self,
        df,
        sheet_name,
        workbook_name,
        folder=None,
        start_cell="A1",
        copy_head=True,
        copy_index=False,
    ):
        """
        Write pandas df into google sheet.

        :param df: df to write
        :param sheet_name: name of sheet in workbook (str)
        :param workbook_name: name of workbook (str)
        :param folder: name of Google Drive folder (str, optional)
        :param start_cell: start cell in sheet (str)
        :param copy_head: copy head of dataframe (bool, default: True)
        :param copy_index: copy index of dataframe (bool, default: True)
        :return: None
        """
        # TODO refactor into smaller methods
        workbook = None
        if folder:
            folders = [
                x
                for x in self.connection.drive.list()
                if (
                    (x["name"] == folder)
                    & (x["mimeType"] == "application/vnd.google-apps.folder")
                )
            ]
            if len(folders) == 1:
                print(f"Using existing folder {folder}")
                try:
                    workbook = self.connection.open(
                        folder + "_" + workbook_name
                    )
                except pygsheets.SpreadsheetNotFound:
                    workbook = self.connection.create(
                        folder + "_" + workbook_name, folder=folders[0]["id"]
                    )
            else:
                raise ValueError(
                    "Could not create google spreadsheet in specific folder!"
                    "Check if folder exists!"
                )
        else:
            try:
                workbook = self.connection.open(workbook_name)
            except pygsheets.SpreadsheetNotFound:
                print(
                    f"Could not locate workbook with name {workbook_name}!"
                    " Trying to create anew!"
                )
                workbook = self.connection.create(workbook_name)

        if workbook is None:
            raise ValueError(
                f"Could not find/create workbook with name {workbook_name}"
            )

        try:
            worksheet = workbook.add_worksheet(sheet_name)
            worksheet.set_dataframe(
                df,
                start=start_cell,
                copy_head=copy_head,
                fit=True,
                copy_index=copy_index,
            )
        except Exception as e:
            print("Try to write/overwrite existing work sheet!")
            print(e)
            worksheet = workbook.worksheet_by_title(sheet_name)
            kwargs = {
                "start": start_cell,
                "copy_head": copy_head,
                "fit": True,
                "copy_index": copy_index,
            }
            worksheet.set_dataframe(df, **kwargs)
