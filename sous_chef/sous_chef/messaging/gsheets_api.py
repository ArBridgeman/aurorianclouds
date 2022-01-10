from dataclasses import dataclass, field
from typing import Any

import pygsheets


@dataclass
class GsheetsHelper:
    connection: Any = field(init=False)
    token_str: str

    def __post_init__(self):
        self.connection = pygsheets.authorize(
            service_file=self.token_str, retries=3
        )

    def get_sheet_as_df(self, workbook_name, sheet_name):
        """
        Get tab sheet_name in workbook_name and return as df.

        :param workbook_name: name of workbook (str),
        :param sheet_name: name of sheet (str),
        :return: sheet converted to pandas dataframe.
        """
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
        conn = self.connection
        workbook = None
        if folder:
            folders = [
                x
                for x in conn.drive.list()
                if (
                    (x["name"] == folder)
                    & (x["mimeType"] == "application/vnd.google-apps.folder")
                )
            ]
            if len(folders) == 1:
                print(f"Using existing folder {folder}")
                try:
                    workbook = conn.open(folder + "_" + workbook_name)
                except pygsheets.SpreadsheetNotFound:
                    workbook = conn.create(
                        folder + "_" + workbook_name, folder=folders[0]["id"]
                    )
            else:
                raise ValueError(
                    "Could not create google spreadsheet in specific folder!"
                    "Check if folder exists!"
                )
        else:
            try:
                workbook = conn.open(workbook_name)
            except pygsheets.SpreadsheetNotFound:
                print(
                    f"Could not locate workbook with name {workbook_name}!"
                    " Trying to create anew!"
                )
                workbook = conn.create(workbook_name)

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
