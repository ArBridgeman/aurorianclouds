"""Minimal import example main file."""
import argparse
import os
import pathlib
import sys
from collections import defaultdict

import pandas as pd

music_extensions = [".mp3", ".m4a", ".wav", ".flac", ".ogg", ".mp4", ".mid"]


# def import_module_from_file(file_path: str, module_name: str = "cfg"):
#     return importlib.machinery.SourceFileLoader(
#         module_name, file_path
#     ).load_module()


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


def get_dir_stats(path_str: str, recursive: bool = False) -> {}:

    if recursive:
        sub_paths = list(path_str.rglob("*"))
    else:
        sub_paths = list(path_str.glob("*"))

    # not defaultdict, need to explicitly set!
    result_dict = {"n_dirs": 0, "n_files": 0, "n_music": 0, "n_other": 0}
    for sub_path in sub_paths:
        if sub_path.exists():  # should be redundant, keep for safety
            if sub_path.is_dir():
                result_dict["n_dirs"] += 1
            else:
                result_dict["n_files"] += 1
                if os.path.splitext(sub_path)[-1] in music_extensions:
                    result_dict["n_music"] += 1
                else:
                    result_dict["n_other"] += 1

    return result_dict


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

            lib_sub["path"].append(os.path.split(path)[-1])
            lib_sub["parent"].append(root_path)
            lib_sub["depth"].append(depth)

            dir_stats = get_dir_stats(path, recursive=False)
            sub_dir_stats = get_dir_stats(path, recursive=True)

            for k, v in dir_stats.items():
                # stats directly in this directory
                lib_sub[k].append(v)
                # stats in all subdirectories (excluding root)
                lib_sub[f"{k}_sub"].append(sub_dir_stats[k] - v)

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
