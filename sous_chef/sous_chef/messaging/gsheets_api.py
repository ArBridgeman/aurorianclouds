import re
from collections import defaultdict
from dataclasses import dataclass, field
from time import sleep
from typing import Any

import pandas as pd
import pygsheets


@dataclass
class GsheetsHelper:
    connection: Any = field(init=False)
    token_str: str

    def __post_init__(self):
        self.connection = pygsheets.authorize(service_file=self.token_str, retries=3)

    def get_sheet_as_df(self, workbook_name, sheet_name):
        """
        Get tab sheet_name in workbook_name and return as df
        """
        workbook = self.connection.open(workbook_name)
        sheet = workbook.worksheet_by_title(sheet_name)
        df = sheet.get_as_df()
        return df
