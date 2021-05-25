"""Client class to interface with FoodData Central.
FoodData Central requires a Data.gov key: https://api.data.gov/signup/
"""

import json
from enum import Enum

import requests

BASE_URL = "https://api.nal.usda.gov/fdc/v1"
DATA_TYPES = ["Foundation", "SR Legacy", "Branded", "Survey (FNDDS)"]


class DataType(Enum):
    Foundation = "Foundation"
    SR = "SR Legacy"  # USDA Standard Refernece
    Branded = "Branded"
    FNDDS = "Survey (FNDDS)"


class Format(Enum):
    abridged = "abridged"  # shortened list of elements
    full = "full"  # default. all elements


class Sorting(Enum):
    """Options for sorting results"""

    dataType = "dataType.keyword"
    description = "lowercaseDescription.keyword"
    fdcId = "fdcId"
    publishedDate = "publishedDate"


class Client:
    def __init__(self, api_key):
        self.api_key = api_key

    def process_args(self, **kwargs):
        """Process and validate arguments from any endpoint.
        # Arguments per endpoint
            ## Food and Foods
            format:: Format enum
            nutrients:: list
                ### Just Food
                fdcId:: string
                ### Just Foods
                fdcIds:: list
            ## Foods List and Foods Search
            dataTypes:: list
            sortBy:: Sorting enum
            reverse:: bool (corresponds to sortOrder in API spec)
            pageSize:: int
            pageNumber:: int
                ### Just Foods Search
                query:: str
                brandOwner:: str
        """
        data = {}

        if "format" in kwargs:
            _format = kwargs["format"]
            assert isinstance(
                _format, Format
            ), f"'format' arg should be an instance of the noms.Format enum class. format object was {_format} instead."
            data.update({"format": _format.value})

        if "nutrients" in kwargs:
            # TODO: check against an internal register of all nutrients
            if data["nutrients"] is not None:
                _nutrients = kwargs["nutrients"]
                data.update({"nutrients": _nutrients})

        if "fdcId" in kwargs:
            # TODO: validate this and the next under constraints
            _fdcId = kwargs["fdcId"]
            data.update({"fdcId": _fdcId})

        if "fdcIds" in kwargs:
            _fdcIds = kwargs["fdcIds"]
            data.update({"fdcIds": _fdcIds})

        if "dataTypes" in kwargs:
            _dataTypeEnums = kwargs["dataTypes"]
            _dataTypes = []
            for dt in _dataTypeEnums:
                assert isinstance(
                    dt, DataType
                ), f"'dataType' should be a list of noms.DataType enums. '{dt}' not understood."
                _dataTypes.append(dt.value)
            data.update({"dataType": ",".join(_dataTypes)})
            # data.update({'dataType': _dataTypes})
            # data.update({'dataType': "Foundation,SR Legacy"})

        if "sortBy" in kwargs:
            _sortBy = kwargs["sortBy"]
            assert isinstance(
                _sortBy, Sorting
            ), f"'sortBy' arg should be an instance of the noms.Sorting enum class. sortBy object was {_sortBy} instead."
            data.update({"sortBy": _sortBy.value})

        if "reverse" in kwargs:
            data.update({"sortOrder": "asc" if not kwargs["reverse"] else "desc"})

        if "pageSize" in kwargs:
            _pageSize = kwargs["pageSize"]
            assert (
                _pageSize >= 1
            ), f"pageSize must be at least one. pageSize was {_pageSize}"
            if _pageSize > 200:
                print(
                    f"Warning: maximum page size is 200. pageSize passed is {_pageSize}"
                )
            data.update({"pageSize": _pageSize})

        if "pageNumber" in kwargs:
            _pageNumber = kwargs["pageNumber"]
            data.update({"pageNumber": _pageNumber})

        if "query" in kwargs:
            _query = kwargs["query"]
            data.update({"query": _query})

        if "brandOwner" in kwargs:
            _brandOwner = kwargs["brandOwner"]
            if _brandOwner is not None:
                data.update({"brandOwner": _brandOwner})

        return data

    def food(
        self, fdcId: str, format: Format = Format.abridged, nutrients: list = None
    ):
        """Retrieves a single food item by an FDC ID. Optional format and
        nutrients can be specified.
            Endpoint: /food/{fdcId}
            Spec: https://fdc.nal.usda.gov/fdc_api.html#/FDC/getFood
        """
        data = self.process_args(**{"format": format, "nutrients": nutrients})
        response = requests.get(
            BASE_URL + f"/food/{fdcId}", params={"api_key": self.api_key, **data}
        )
        obj = json.loads(response.text) if response.status_code == 200 else None
        return response, obj

    def foods(
        self, fdcIds: list, format: Format = Format.abridged, nutrients: list = None
    ):
        """Retrieves a list of food items by a list of up to 20 FDC IDs.
        Optional format and nutrients can be specified. Invalid FDC ID's or ones
        that are not found are omitted and an empty set is returned if there are
        no matches.
            Endpoint: /foods
            Spec: https://fdc.nal.usda.gov/fdc_api.html#/FDC/postFoods
        """
        data = self.process_args(
            **{"fdcIds": fdcIds, "format": format, "nutrients": nutrients}
        )
        response = requests.post(
            BASE_URL + "/foods", params={"api_key": self.api_key}, json=data
        )
        obj = json.loads(response.text) if response.status_code == 200 else None
        return response, obj

    def foods_list(
        self,
        dataTypes: list = [DataType.Foundation, DataType.SR],
        pageSize: int = 50,
        pageNumber: int = 1,
        sortBy: Sorting = Sorting.dataType,
        reverse=False,
    ):
        """Retrieves a paged list of foods. Use the pageNumber parameter to page
        through the entire result set.
            Endpoint: /foods/list
            Spec: https://fdc.nal.usda.gov/fdc_api.html#/FDC/postFoodsList
        """
        data = self.process_args(
            **{
                "dataTypes": dataTypes,
                "pageSize": pageSize,
                "pageNumber": pageNumber,
                "sortBy": sortBy,
                "reverse": reverse,
            }
        )
        response = requests.post(
            BASE_URL + "/foods/list", params={"api_key": self.api_key}, json=data
        )
        obj = json.loads(response.text) if response.status_code == 200 else None
        return response, obj

    def foods_search(
        self,
        query: str,
        dataTypes: list = [DataType.Foundation, DataType.SR],
        pageSize: int = 50,
        pageNumber: int = 1,
        sortBy: Sorting = Sorting.dataType,
        reverse=False,
        brandOwner: str = None,
    ):
        """Search for foods using keywords. Results can be filtered by dataType
        and there are options for result page sizes or sorting.
            Endpoint: /foods/search
            Spec: https://fdc.nal.usda.gov/fdc_api.html#/FDC/postFoodsSearch
        """
        data = self.process_args(
            **{
                "query": query,
                "dataTypes": dataTypes,
                "pageSize": pageSize,
                "pageNumber": pageNumber,
                "sortBy": sortBy,
                "reverse": reverse,
                "brandOwner": brandOwner,
            }
        )
        dataType = data["dataType"]
        del data["dataType"]
        _json = {**data, "dataType": dataType}
        print(_json)
        response = requests.post(
            BASE_URL + "/foods/search",
            params={"api_key": self.api_key, "dataType": dataType},
            json=_json,
        )
        obj = json.loads(response.text) if response.status_code == 200 else None
        return response, obj
