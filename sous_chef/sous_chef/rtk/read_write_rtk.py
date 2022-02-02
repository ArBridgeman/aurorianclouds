from pathlib import Path
from typing import List
from zipfile import ZipFile

from omegaconf import DictConfig

HOME_PATH = str(Path.home())


class RtkService:
    def __init__(self, config: DictConfig):
        self.delete_older_file = config.delete_older_file
        self.path = Path(HOME_PATH, config.path)
        self.file_pattern = config.file_pattern

    def unzip(self):
        latest_file = self._find_latest_file()
        if latest_file is not None:
            with ZipFile(latest_file, "r") as zip_ref:
                files_in_zip = zip_ref.namelist()
                for fileName in files_in_zip:
                    if fileName.endswith(".json"):
                        zip_ref.extract(fileName, path=self.path)
            latest_file.unlink()

    @staticmethod
    def _delete_older_files(latest_file: Path, file_list: List[Path]):
        for file in file_list:
            if file != latest_file:
                file.unlink()

    def _find_all_file(self):
        return list(self.path.glob(self.file_pattern))

    def _find_latest_file(self):
        file_list = self._find_all_file()
        if len(file_list) > 0:
            latest_file = max(file_list, key=lambda p: p.stat().st_ctime)
            if self.delete_older_files:
                self._delete_older_files(latest_file, file_list)
            return latest_file
        return None
