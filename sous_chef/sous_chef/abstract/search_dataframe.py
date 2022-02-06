from dataclasses import dataclass

import numpy as np
import pandas as pd
from fuzzywuzzy import fuzz, process
from omegaconf import DictConfig
from structlog import get_logger

FILE_LOGGER = get_logger(__name__)


@dataclass
class DirectSearchError(Exception):
    field: str
    search_term: str
    message: str = "[direct search failed]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        values = {"field": self.field, "search_term": self.search_term}
        return f"{self.message}: {values} "


@dataclass
class FuzzySearchError(Exception):
    field: str
    search_term: str
    result: str
    match_quality: float
    threshold: int
    message: str = "[fuzzy search failed]"

    def __post_init__(self):
        super().__init__(self.message)

    def __str__(self):
        values = {
            "field": self.field,
            "search_term": self.search_term,
            "result": self.result,
            "quality": self.match_quality,
            "threshold": self.threshold,
        }
        return f"{self.message}: {values}"


@dataclass
class DataframeSearchable:
    config: DictConfig
    dataframe: pd.DataFrame = pd.DataFrame()

    def retrieve_direct_match(self, field: str, search_term: str) -> pd.Series:
        field_values = self.dataframe[field].apply(self._purify_string)
        mask = field_values == self._purify_string(search_term)
        if np.sum(mask) > 0:
            return self.dataframe[mask].iloc[0]
        raise DirectSearchError(field=field, search_term=search_term)

    def retrieve_direct_match_or_fuzzy_fallback(
        self, field: str, search_term: str
    ) -> pd.Series:
        for retrieval_method in [
            self.retrieve_direct_match,
            self._retrieve_fuzzy_fallback,
        ]:
            try:
                found_recipe = retrieval_method(field, search_term)
                return found_recipe
            # only care if all searches fail
            except DirectSearchError:
                pass

    def _retrieve_fuzzy_fallback(self, field: str, search_term: str):
        field_values = self.dataframe[field].apply(self._purify_string).values
        limit_number_results = self.config.fuzzy_match.limit_number_results

        best_match_search_term, best_match_quality = process.extract(
            self._purify_string(search_term),
            field_values,
            scorer=fuzz.ratio,
            limit=limit_number_results,
        )[0]

        min_threshold_to_accept = self.config.fuzzy_match.min_thresh_to_accept
        if best_match_quality < min_threshold_to_accept:
            raise FuzzySearchError(
                field=field,
                search_term=search_term,
                result=best_match_search_term,
                match_quality=best_match_quality,
                threshold=min_threshold_to_accept,
            )

        min_thresh_ok_match = self.config.fuzzy_match.min_thresh_ok_match
        if best_match_quality < min_thresh_ok_match:
            FILE_LOGGER.warning(
                "[fuzzy search poor]",
                field=field,
                value=search_term,
                match_quality=best_match_quality,
                threshold=min_thresh_ok_match,
            )

        mask_result = field_values == best_match_search_term
        return self.dataframe[mask_result].iloc[0]

    @staticmethod
    def _purify_string(search_term: str):
        return search_term.strip().casefold()
