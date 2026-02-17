"""Simple jellyfin helpers."""

import argparse
import os
import pathlib
import sys
from collections import defaultdict

import pandas as pd

music_extensions = [".mp3", ".m4a", ".wav", ".flac", ".ogg", ".mp4", ".mid"]


def parse_cmd_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--library_path",
        "-l",
        help="Path to top level of library to scan.",
        required=True,
    )
    parser.add_argument(
        "--depth",
        "-d",
        help="Directory depth to scan: 0 means only "
        "library path itself and no level below.",
        required=False,
        default=2,
        type=int,
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Name of output file to write, "
        "will be created and overwritten if exists.",
        required=False,
        default="library_scan.csv",
        type=str,
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
        if sub_path.exists():
            # if directory
            if sub_path.is_dir():
                result_dict["n_dirs"] += 1
            else:
                # if file
                result_dict["n_files"] += 1
                # check if music file or other based on extensions list
                if os.path.splitext(sub_path)[-1] in music_extensions:
                    result_dict["n_music"] += 1
                else:
                    result_dict["n_other"] += 1

    return result_dict


def get_library_as_df(
    path: pathlib.Path,
    depth: int = 0,
    max_depth: int = 1,
) -> pd.DataFrame:

    # recursion stop criteria
    if depth > max_depth:
        return pd.DataFrame()

    lib_dict = defaultdict(list)
    lib_dict["path"].append(os.path.split(path)[-1])
    lib_dict["parent"].append(path.parent)
    lib_dict["depth"].append(depth)

    dir_stats = get_dir_stats(path, recursive=False)
    sub_dir_stats = get_dir_stats(path, recursive=True)

    for k, v in dir_stats.items():
        # stats directly in this directory
        lib_dict[k].append(v)
        # stats in all subdirectories (excluding root)
        lib_dict[f"{k}_sub"].append(sub_dir_stats[k] - v)

    lib_df = pd.DataFrame(lib_dict)

    if depth < max_depth:
        for sub_path in path.glob("*"):
            if sub_path.is_dir():
                sub_df = get_library_as_df(
                    sub_path,
                    depth=depth + 1,
                    max_depth=max_depth,
                )
                lib_df = pd.concat((lib_df, sub_df), ignore_index=True)

    return lib_df


def main():
    args = parse_cmd_arguments()

    lib_path = pathlib.Path(args.library_path)

    # process library
    lib_df = get_library_as_df(lib_path, max_depth=args.depth)
    lib_df.sort_values(["parent", "path"]).to_csv(
        args.output, sep=";", index=False
    )

    return


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
