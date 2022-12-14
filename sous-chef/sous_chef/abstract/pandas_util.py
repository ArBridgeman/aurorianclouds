from typing import Dict, Set

import pandas as pd
from structlog import get_logger

FILE_LOGGER = get_logger(__name__)


def find_column_intersection(
    df1: pd.DataFrame, df2: pd.DataFrame, column: str
) -> Set:
    return set(df1[column]).intersection(df2[column])


def are_shared_df_entries_identical(
    orig_df: pd.DataFrame, new_df: pd.DataFrame, shared_column: str
):
    shared_columns = set(orig_df.columns).intersection(new_df.columns)
    shared_values = find_column_intersection(orig_df, new_df, shared_column)

    def _select_shared_columns(df: pd.DataFrame) -> pd.DataFrame:
        mask_df = df[shared_column].isin(shared_values)
        return (
            df[shared_columns]
            .loc[mask_df]
            .copy(deep=True)
            .drop_duplicates(keep="first")
        )

    diff_df = (
        pd.concat(
            [_select_shared_columns(orig_df), _select_shared_columns(new_df)]
        )
        .drop_duplicates(keep=False)
        .sort_values(by=[shared_column])
    )

    if diff_df.shape[0] > 0:
        FILE_LOGGER.warning(
            "[are_shared_df_entries_identical]",
            number_diff=diff_df.shape[0] / 2,
            diff_df=diff_df,
        )
        return False
    return True


def get_dict_from_columns(
    df: pd.DataFrame, key_col: str, value_col: str
) -> Dict:
    return {key: value for key, value in df[[key_col, value_col]].values}
