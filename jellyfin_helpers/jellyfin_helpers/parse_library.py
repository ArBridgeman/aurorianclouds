"""Minimal import example main file."""
import argparse
import importlib.machinery
import os
import pathlib
import sys
from collections import defaultdict

import pandas as pd

music_extensions = [".mp3", ".m4a", ".wav", ".flac", ".ogg", ".mp4", ".mid"]


def import_module_from_file(file_path: str, module_name: str = "cfg"):
    return importlib.machinery.SourceFileLoader(
        module_name, file_path
    ).load_module()


def parse_cmd_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--library_path",
        "-l",
        help="Path to top level of libary to scan.",
        required=True,
    )
    args = parser.parse_args()
    return args


def get_library_as_df(
    root_path: pathlib.Path,
    depth: int = 1,
    max_depth: int = 2,
    limit: int = None,
) -> pd.DataFrame:

    if (max_depth < 1) or (depth > max_depth):
        return pd.DataFrame()

    lib_df = pd.DataFrame()
    for path in root_path.glob("*"):

        lib_sub = defaultdict(list)
        if path.is_dir():
            sub_paths = list(path.glob("*"))
            sub_sub_paths = list(path.rglob("*"))

            n_dirs = sum([1 for p in sub_paths if p.is_dir()])
            n_files = sum(
                [1 for p in sub_paths if (p.exists() and not p.is_dir())]
            )
            n_music = sum(
                [
                    1
                    for p in sub_paths
                    if (
                        p.exists()
                        and not p.is_dir()
                        and os.path.splitext(p)[-1] in music_extensions
                    )
                ]
            )

            n_dirs_all = sum([1 for p in sub_sub_paths if p.is_dir()])
            n_files_all = sum(
                [1 for p in sub_sub_paths if (p.exists() and not p.is_dir())]
            )
            n_music_all = sum(
                [
                    1
                    for p in sub_sub_paths
                    if (
                        p.exists()
                        and not p.is_dir()
                        and os.path.splitext(p)[-1] in music_extensions
                    )
                ]
            )
            lib_sub["path"].append(os.path.split(path)[-1])
            lib_sub["parent"].append(root_path)
            lib_sub["depth"].append(depth)

            # stats directly in this directory
            lib_sub["n_directories"].append(n_dirs)
            lib_sub["n_files"].append(n_files)
            lib_sub["n_music"].append(n_music)
            lib_sub["n_other"].append(n_files - n_music)

            # stats in all subdirectories
            lib_sub["n_sub_directories"].append(n_dirs_all - n_dirs)
            lib_sub["n_sub_files"].append(n_files_all - n_files)
            lib_sub["n_sub_music"].append(n_music_all - n_music)
            lib_sub["n_sub_other"].append(
                n_files_all - n_music_all - (n_files - n_music)
            )

            lib_df = pd.concat(
                (lib_df, pd.DataFrame(lib_sub)), ignore_index=True
            )

            if depth < max_depth:
                sub_df = get_library_as_df(
                    path, depth=depth + 1, max_depth=max_depth
                )
                lib_df = pd.concat((lib_df, sub_df), ignore_index=True)

            if limit is not None:
                limit -= 1
                if limit < 1:
                    break

    return lib_df


def main():
    args = parse_cmd_arguments()

    # read config file
    # cfg = import_module_from_file(args.config_file)
    lib_path = pathlib.Path(args.library_path)

    # process library
    lib_df = get_library_as_df(lib_path, max_depth=2)
    lib_df.to_csv("library_scan.csv", sep=";")

    return


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
