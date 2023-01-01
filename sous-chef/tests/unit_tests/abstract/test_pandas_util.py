import pandas as pd
from sous_chef.abstract.pandas_util import (
    are_shared_df_entries_identical,
    find_column_intersection,
    get_dict_from_columns,
)


def test_find_column_intersection():
    shared_values = [1, 4, 7, 8, 4]
    df1 = pd.DataFrame({"col1": [1, 9, 11] + shared_values})
    df2 = pd.DataFrame({"col1": [2, 3, 7, 4] + shared_values})

    assert set(shared_values) == find_column_intersection(
        df1, df2, column="col1"
    )


class TestAreSharedDfEntriesIdentical:
    @staticmethod
    def test_true_when_identical():
        df1 = pd.DataFrame({"id": [1, 2, 3], "y": ["a", "b", "c"]})
        assert are_shared_df_entries_identical(
            orig_df=df1, new_df=df1.copy(), shared_column="id"
        )

    @staticmethod
    def test_false_when_not_identical():
        df1 = pd.DataFrame({"id": [1, 2, 3], "y": ["a", "b", "c"]})
        df2 = df1.copy(deep=True)
        df1.iloc[0, df1.columns.get_loc("y")] = "f"
        assert not are_shared_df_entries_identical(
            orig_df=df1, new_df=df2, shared_column="id"
        )


def test_get_dict_from_columns():
    dummy_df = pd.DataFrame({"key": ["a", "b", "c"], "value": [1, 2, 3]})
    result = get_dict_from_columns(
        df=dummy_df, key_col="key", value_col="value"
    )
    assert result == {"a": 1, "b": 2, "c": 3}
