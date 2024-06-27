import json
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Union

import requests
from numpy import ndarray
from omegaconf import DictConfig
from pydantic import HttpUrl
from pydantic.tools import parse_obj_as

ABS_FILE_PATH = Path(__file__).absolute().parent


def _build_url(server_url: HttpUrl, path: str, kwargs: OrderedDict) -> str:
    base_url = f"{server_url}/{path}"
    separator = "?"
    for key, value in kwargs.items():
        value_str = _convert_parameter_value_to_string(value)
        base_url += f"{separator}{key}={value_str}"
        # switch separator after first run through
        separator = "&"
    # return HttpUrl(base_url) for pydantic 2.0
    return base_url


def _convert_parameter_value_to_string(value: Union[int, str, List]) -> str:
    if isinstance(value, str):
        return value
    elif isinstance(value, list) or isinstance(value, ndarray):
        return ",".join(value)
    return str(value)


def _compare_strings(str1: str, str2: str) -> bool:
    return str1.strip().lower() == str2.strip().lower()


class Jellyfin:
    def __init__(self, config: DictConfig):
        credentials_file_path = Path(
            ABS_FILE_PATH, config.credentials_file_path
        )
        credentials_file = open(credentials_file_path)
        credentials = json.load(credentials_file)

        self.token: str = credentials["token"]
        self.user_id: str = credentials["user_id"]
        self.server_url: HttpUrl = parse_obj_as(
            HttpUrl, credentials["server_url"]
        )

    def _prepare_request_url(
        self, path: str, parameters: Optional[Dict] = None
    ) -> str:
        kwargs = OrderedDict()
        kwargs["userId"] = self.user_id
        if parameters:
            kwargs.update(parameters)
        return _build_url(server_url=self.server_url, path=path, kwargs=kwargs)

    def _send_get_request(
        self, path: str, parameters: Optional[Dict] = None
    ) -> Dict:
        url = self._prepare_request_url(path=path, parameters=parameters)
        response = requests.get(url, headers={"X-Emby-Token": self.token})
        response.raise_for_status()
        return response.json()

    def _send_post_request(
        self, path: str, parameters: Optional[Dict] = None
    ) -> None:
        url = self._prepare_request_url(path=path, parameters=parameters)
        response = requests.post(url, headers={"X-Emby-Token": self.token})
        response.raise_for_status()

    def _get_item_id(self, item_name: str) -> str:
        items = self._send_get_request(
            path="Items",
            parameters={
                "searchTerm": item_name,
                "recursive": True,
            },
        )["Items"]
        if len(items) < 1:
            raise ValueError(f"nothing with item_name={item_name}")
        return items[0]["Id"]

    def _get_genre_id(self, genre_name: str) -> str:
        genre = self._send_get_request(path=f"Genres/{genre_name}")
        return genre["Id"]

    def _get_library_id(self, library_name: str) -> str:
        libraries = self._send_get_request(path="Library/VirtualFolders")
        match = list(
            filter(
                lambda x: _compare_strings(x["Name"], library_name), libraries
            )
        )
        if len(match) < 1:
            raise ValueError(
                f"{library_name} not found; options are: ",
                list(map(lambda d: d["Name"], libraries)),
            )
        return match[0]["ItemId"]

    def get_genres_per_library(self, library_name: str) -> List[Dict]:
        genres = self._send_get_request(
            path="Genres",
            parameters={
                "parentId": self._get_library_id(library_name=library_name)
            },
        )["Items"]
        return list(map(lambda d: {"Name": d["Name"], "Id": d["Id"]}, genres))

    def get_items_per_genre(self, genre_id: str) -> List[Dict]:
        extra_fields = ["Tags", "Path"]

        def _extract_item(source_dict: Dict) -> Dict:
            desired_keys = [
                "Name",
                "Id",
                "VideoType",
                "RunTimeTicks",
            ] + extra_fields
            return {key: source_dict.get(key) for key in desired_keys}

        items = self._send_get_request(
            path="Items",
            parameters={
                "genreIds": genre_id,
                "recursive": True,
                "fields": extra_fields,
            },
        )["Items"]
        if len(items) < 1:
            raise ValueError(f"no items found for genre_id={genre_id}")
        return [_extract_item(source_dict=item) for item in items]

    def post_add_to_playlist(self, playlist_name: str, item_ids: List[str]):
        playlist_id = self._get_item_id(item_name=playlist_name)
        self._send_post_request(
            path=f"Playlists/{playlist_id}/Items",
            parameters={
                "ids": item_ids,
            },
        )


# to access item in browser, but not yet deeplinked in jellfyin android
# item_url = build_url(path="web/index.html#!/details", kwargs=item_parameters)
# print(item_url)
