"""Main driver for TAG: Tag Analysis Generator."""

import sys
import traceback
import threading
import argparse
import pathlib
import os

import util
import cache
import tag
import progressbar

if __name__ == "__main__":
    # Start a progress bar on a separate thread from the main program

    # Initialize the parser
    parser = argparse.ArgumentParser(description="Analyze tag-based data.")

    parser.add_argument(
        "--source", type=str, default=0, help="Set data/ directory (default: CWD)."
    )
    parser.add_argument(
        "--graph",
        action="store_true",
        help="Enable obsidian-ready graphs (default: graphs disabled).",
    )
    parser.add_argument(
        "--graph-nodes",
        type=int,
        default=500,
        help="Only graph queries below this amount of posts (default: 500).",
    )

    # argparse will print a message and exit with invalid input or with --help
    args = parser.parse_args()

    # Determine /data/ directory.
    # Prefer "source" argument. Defaults to CWD
    if args.source:
        try:
            root_dir = pathlib.Path(args.source)
        except Exception as e:
            print("Error: Unable to parse source directory filepath.")
            sys.exit(0)
        if not root_dir.exists():
            print(f"Error: Unable to find source directory {args.source}")
            sys.exit(0)
    else:
        root_dir = pathlib.Path(os.getcwd())
    util.set_root(root_dir)
    util.ensure_dirs_exist()

    # Apply graphing options
    if not args.graph:
        util.set_max_graph_nodes(0)
    else:
        util.set_max_graph_nodes(args.graph_nodes)

    t = threading.Thread(target=progressbar.start_progress_bar)
    t.start()

    # Main tag analysis
    try:
        # Ensure cache exists
        cache.generate_cache_if_missing()
        tag.print_tags_by_count()
        # Process input data
        tag.read_in_query_list()

    except util.FileNotFound as e:
        print(f"\n{e.message}")
        print(
            f" Did you unzip Tags.csv and Questions.csv into {util.Filepath.export_dir}"
        )
    except Exception as e:
        print("\n[ERROR - EXITING EXECUTION]")
        print(traceback.format_exc())

    # End the progress bar thread, as we've finished execution.
    progressbar.end_progress_bar()
    t.join()
