from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import pandas as pd
import pygsheets
from omegaconf import DictConfig
from structlog import get_logger

ABS_FILE_PATH = Path(__file__).absolute().parent

FILE_LOGGER = get_logger(__name__)


class MimeType(Enum):
    folder = "application/vnd.google-apps.folder"


@dataclass
class GsheetsHelper:
    config: DictConfig

    def __post_init__(self):
        token_file = Path(ABS_FILE_PATH, self.config.token_file_path)
        self.connection = pygsheets.authorize(
            service_account_file=token_file, retries=3
        )

    def get_worksheet(
        self, workbook_name: str, worksheet_name: str, numerize: bool = False
    ) -> pd.DataFrame:
        FILE_LOGGER.info(
            "[get_worksheet]",
            workbook_name=workbook_name,
            worksheet_name=worksheet_name,
        )
        # TODO catch & raise specific exception here when resource not found
        workbook = self.connection.open(workbook_name)
        worksheet = workbook.worksheet_by_title(worksheet_name)
        return worksheet.get_as_df(numerize=numerize)

    def write_worksheet(
        self,
        df: pd.DataFrame,
        workbook_name: str,
        worksheet_name: str,
        folder: Optional[str] = None,
    ):
        workbook = self._get_workbook(workbook_name, folder)

        try:
            # if exists, then will overwrite
            worksheet = workbook.worksheet_by_title(worksheet_name)
        except pygsheets.WorksheetNotFound:
            # then create
            worksheet = workbook.add_worksheet(worksheet_name)

        worksheet.set_dataframe(
            df,
            start="A1",
            copy_head=True,
            fit=True,
            copy_index=False,
        )

    def _delete_item(self, item_id: str):
        self.connection.drive.delete(item_id)

    def _get_folder_id(self, folder_name: str):
        folders = self._perform_query("folder", folder_name)
        if len(folders) == 0:
            FILE_LOGGER.warning(
                "[get_folder_id]",
                warn="Could not locate folder",
                action="Attempt to create one",
                folder_name=folder_name,
            )
            folder_id = self.connection.drive.create_folder(folder_name)
        elif len(folders) > 1:
            # TODO make custom exception to catch when called
            raise ValueError(f"{len(folders)} folders named {folder_name}")
        else:
            folder_id = folders[0]["id"]
        return folder_id

    def _get_workbook(
        self, workbook_name: str, folder_name: Optional[str] = None
    ):
        file_name = workbook_name
        kwargs = {}
        if folder_name:
            file_name = f"{folder_name}_" + file_name
            kwargs["folder"] = self._get_folder_id(folder_name)

        try:
            workbook = self.connection.open(file_name)
        except pygsheets.SpreadsheetNotFound:
            FILE_LOGGER.warning(
                "[get_workbook]",
                warn="Could not locate workbook",
                workbook_name=workbook_name,
                action="Attempt to create one",
            )
            workbook = self.connection.create(file_name, **kwargs)
        return workbook

    def _perform_query(self, mimetype_name: str, file_name: str) -> list[dict]:
        query = f"name='{file_name}'"
        query += f" and mimeType='{MimeType[mimetype_name].value}'"
        return self.connection.drive.list(q=query)
