"""Provide core logic of processing a query."""

import math
import os
import sys
import time
import sqlite3
import pickle
import pathlib
import multiprocessing
from collections import defaultdict

import util
import progressbar
import chart


def print_double_sorted_list(in_dict: dict) -> str:
    """Print lists of values."""
    # Header is used as the name of the entire in_dict.
    # in_dict is a map of key-value.

    out_str = ""
    # These double sorts allow us to:
    # 1: sort descending by count of each tag
    # 2: within groups of tags of the same count, sort alphabetically ascending by tag
    srt = sorted(in_dict.items(), key=lambda kv: (kv[0]), reverse=False)
    srt = sorted(srt, key=lambda kv: (kv[1]), reverse=True)
    for tag_count in srt:
        out_str += f"{str(tag_count[1])} {str(tag_count[0])}\n"
    out_str += "\n"
    return out_str


def print_tags_by_count() -> None:
    """Generate a human-readable list of tags ordered by question count."""
    # This file isn't used by the program, but it may be helpful for users.
    tag_file = util.Filepath.tags_out_dir / "tag_counts.md"
    # Only generate the file if it doesn't already exist
    if not tag_file.exists():
        tag_counts = {}

        # Connect to the database.
        con = sqlite3.connect(util.Filepath.cache_tag_to_questions)
        # Create the cursor.
        cur = con.cursor()
        res = cur.execute("SELECT * FROM tag_to_questions ")
        for row in res.fetchall():
            # Map the tag (row[0]) to the count of posts with that tag
            tag_counts[row[0]] = len(pickle.loads(row[1]))
        # Sort list, first by count and second by alphabetical order
        with open(tag_file, "wt", encoding="utf-8") as out_file:
            out_file.write(print_double_sorted_list(tag_counts))
        con.close()


def get_valid_posts(
    include_tags: list[str], exclude_tags: list[str]
) -> tuple[set[int], list[util.PostData]]:
    """Get the list of valid (not excluded) tags from the database."""
    # Returns a tuple with 2 elements.
    # Element 1: list of all post ids (in str format).
    # Element 2: list of all PostData objects corresponding to post ids.

    # While databases contain millions of posts, Stack Overflow queries usually have
    # <100k posts and each post stores relatively little data.
    # Therefore, it's fine to store all these posts in memory at once.
    post_ids = set()

    # Read in from the postid database
    # Exit if the file is missing
    if not util.Filepath.cache_tag_to_questions:
        print(f"Error: {util.Filepath.cache_tag_to_questions} not found. Exiting...")
        sys.exit(0)

    con = sqlite3.connect(util.Filepath.cache_tag_to_questions)
    cur = con.cursor()
    # Special case: If no include tags were specified, use the set of all post ids.
    if len(include_tags) == 0:
        print(
            "WARNING:"
            "\n  Query includes entire database."
            "\n  The logic for this is not yet implemented."
            "\n  This query will be treated as empty/invalid."
        )
        return set(), []

    # Initialize the set of valid post ids to posts with the first include tag.
    res = cur.execute(
        "SELECT ids FROM tag_to_questions WHERE tag = ?", (include_tags[0],)
    ).fetchone()
    res = pickle.loads(res[0])
    # Get the superset of all ids with the current and newly-found lists of ids
    post_ids.update(res)

    # Sanity check: post_ids should be non-empty after initialization.
    if len(post_ids) == 0:
        print("ERROR: Query involved an invalid tag with 0 associated posts.")
        return set(), []

    # Filter for the posts that contain all other include tags
    for tag in include_tags[1:]:
        res = cur.execute(
            "SELECT ids FROM tag_to_questions WHERE tag = ?", (tag,)
        ).fetchone()
        res = pickle.loads(res[0])
        post_ids.intersection_update(res)
        # Stop processing if we end up with no valid posts
        if len(post_ids) == 0:
            print("Query returned zero posts.")
            return set(), []

    # Filter for the posts that don't contain any of the exclude tags
    for tag in exclude_tags:
        res = cur.execute(
            "SELECT ids FROM tag_to_questions WHERE tag = ?", (tag,)
        ).fetchone()
        res = pickle.loads(res[0])
        post_ids.difference_update(res)
        # Stop processing if we end up with no valid posts
        if len(post_ids) == 0:
            print("Query returned zero posts.")
            return set(), []
    # Close the connection.
    con.close()

    # Use each post id to access the associated post's data from the posts database.
    post_list = []
    con = sqlite3.connect(util.Filepath.tag_database)
    cur = con.cursor()
    # We sort the list of PostData objects, from oldest to newest.
    for postid in sorted(list(post_ids)):
        res = cur.execute(
            "SELECT * FROM tags_table WHERE question_id = ?", (int(postid),)
        ).fetchone()
        post_list.append(util.PostData(res))
    con.close()
    return post_ids, post_list


def read_in_query_list():
    """Read queries from disk into the program."""
    query_list = []
    for filename in os.listdir(util.Filepath.tags_in_dir):
        query_file = util.Filepath.tags_in_dir / filename
        # Read in each tag into the query list as a single query
        with open(query_file, "rt", encoding="utf-8") as in_file:
            for line in in_file:
                # Ignore comments and whitespace/newlines
                if line[0] != "#" and line[0] != "\n":
                    query_list.append(line.strip("\n").split(" "))

    # If no queries were found, create an example file for users to study.
    if len(query_list) == 0:
        print(
            f"No queries found in {util.Filepath.tags_in_dir}.\n"
            f"  Using sample query file instead."
        )
        query_list = [["maps"], ["python", "sql"], ["python", "-sql-server", "sql"]]
        with open(
            util.Filepath.tags_in_dir / "sample_queries.txt", "wt", encoding="utf-8"
        ) as out_file:
            for line in query_list:
                out_file.write(" ".join(line) + "\n")
    else:
        print(f"Found {len(query_list)} queries in {util.Filepath.tags_in_dir}.")
    process_tags(query_list)


def process_tags(query_list: list[list[str]]):
    """Split a list of queries into single tasks."""
    # The input tags are all combined.
    # Initial pass: Check for any invalid tags.
    # Open a DB connection to check if the user-specified tag exists
    con = sqlite3.connect(util.Filepath.cache_tag_to_questions)
    cur = con.cursor()
    for tag_list in query_list:
        for tag in tag_list:
            # Ignore the negation operator, if present
            if tag[0] == "-":
                tag_base = tag[1:]
            else:
                tag_base = tag

            # Check if the tag has been used on a question before
            cur.execute("SELECT ids FROM tag_to_questions WHERE tag = ?", (tag_base,))
            if cur.fetchone() is None:
                print(f"Error: {tag_base} is not a valid tag. Full query: {tag_list}.")
                return
        # print(f"Valid query: {tag_list}")
    con.close()

    # Process queries in order.
    progressbar.start_new_stage("Processing Queries:", len(query_list))
    start_time = time.time()
    if len(query_list) > 1:
        # If we have multiple queries, create a new process for each query.
        # This enables multiprocessing to improve speed.

        # Create a pool with the number of available CPU cores (default)
        with multiprocessing.Pool() as pool:
            # Map the function to the list of inputs
            pool.map(process_posts, query_list)
    else:
        # If there are only a few queries,
        # then it's faster to split the queries into parallel sub-tasks.
        # Also, for queries that involve millions of posts, then to avoid the risk of
        # running out of memory we invoke this sequential algorithm.

        # Queries will be processed sequentially (single core), but we free up cores
        # to use on parallelizing sub-tasks of query analysis.
        # For the Stack Overflow data, this would manifest as parallelizing
        # the similar/recommended tags.
        util.Options.parallelize_query_subtask = True
        for tag_list in query_list:
            process_posts(tag_list)
    duration = time.time() - start_time
    print(f"Time to process {len(query_list)} queries: {round(duration, 2)} s")


def process_posts(tag_list: list[str]):
    """Create directory containing an individual query's analysis."""
    print(f"Processing {tag_list} on PID: {os.getpid()}")
    # Split the input tags into include/exclude tags.
    include_tags = []
    exclude_tags = []
    for tag in tag_list:
        # Check for the negation operator.
        if tag[0] == "-":
            exclude_tags.append(tag[1:])
        else:
            include_tags.append(tag)
    # Sort each list alphabetically.
    include_tags = sorted(include_tags)
    exclude_tags = sorted(exclude_tags)

    post_ids, post_data = get_valid_posts(include_tags, exclude_tags)
    if len(post_ids) == 0:
        print(f"Skipping Query: {tag_list}.\n")
        return

    # Analysis results will be placed in a folder.
    # Folder name is the concatenated include + exclude lists.
    if len(exclude_tags) == 0:
        folder_name = f"{' '.join(include_tags)}"
        # special case where there are no include/exclude tags specified.
        if len(include_tags) == 0:
            folder_name = "all_"
    else:
        folder_name = f"{' '.join(include_tags)} -{' -'.join(exclude_tags)}"

    # Append the number of valid posts to the folder name.
    # These appended values make it easier to compare query results at a glance.
    folder_name = f"{folder_name} {len(post_ids)}"

    output_dir = util.Filepath.tags_out_dir / folder_name
    if output_dir.exists():
        print(f"{folder_name} already exists, skipping query.")
    else:
        # Create the folder housing the output for this query
        # print(f"\nCreating directory: {folder_name}")
        os.mkdir(output_dir)

        # Generate and save analysis data to disk
        generate_text_and_numerical_data(output_dir, post_data)
        generate_score_chart(output_dir, post_data)
        list_similar_tags_sparse(output_dir, post_ids, post_data)
        generate_obsidian_graph(output_dir, post_data)

        # print(f"\nFinished directory: {folder_name}")
        progressbar.update_step_one()


def generate_score_chart(output_dir: pathlib.Path, post_list: list[util.PostData]):
    """Save a graph of question scores for each post."""
    chart_data = [
        {"label": "<1k words", "color": "tab:blue", "x_data": [], "y_data": []},
        {"label": "1k-5k words", "color": "tab:orange", "x_data": [], "y_data": []},
        {"label": ">5k words", "color": "tab:red", "x_data": [], "y_data": []},
    ]

    con = sqlite3.connect(util.Filepath.question_database)
    cur = con.cursor()
    for post in post_list:
        # Find the associated question data for this post
        cur.execute(
            "SELECT * FROM questions_table WHERE question_id = ?", (post.post_id,)
        )
        res = cur.fetchone()
        q = util.QuestionData(res)
        if q.body_length < 1000:
            chart_data[0]["x_data"].append(q.created)
            chart_data[0]["y_data"].append(q.score)
        elif q.body_length > 5000:
            chart_data[2]["x_data"].append(q.created)
            chart_data[2]["y_data"].append(q.score)
        else:
            chart_data[1]["x_data"].append(q.created)
            chart_data[1]["y_data"].append(q.score)
    con.close()
    chart.generate_scatter_plot(output_dir / "chart_4_score.png", chart_data)


def generate_text_and_numerical_data(
    output_dir: pathlib.Path, post_list: list[util.PostData]
):
    """Generate and save text data and pre-set charts."""
    # Pass 1: Write out individual/per-question data and tags to markdown
    with open(output_dir / "tags.md", "wt", encoding="utf-8") as out_file:
        # Header: Numerical Stats
        final_stats = "### Final Stats:\n"
        final_stats += f"Total Posts: {len(post_list)}\n\n"
        out_file.write(final_stats)

        # Iterate over each valid post
        con = sqlite3.connect(util.Filepath.question_database)
        cur = con.cursor()
        for row in post_list:
            # Find the associated question data for this post
            cur.execute(
                "SELECT * FROM questions_table WHERE question_id = ?", (row.post_id,)
            )
            q = util.QuestionData(cur.fetchone())
            # Print a markdown header and the question title
            out_file.write(f"#### {row.post_id} {q.title}")
            out_file.write(f"\nPosted: {str(q.created)[:10]}")
            out_file.write(f"\nScore:  {q.score}")
            out_file.write(f"\nLength: {q.body_length}")
            # Print each tag and leave space for the next post
            out_file.write(f"\n{' '.join(row.tags)}\n\n")
        con.close()

    # Pass 2: Write out counts of each tag in the queried posts
    with open(
        output_dir / "tag_counts_by_export_category.md", "wt", encoding="utf-8"
    ) as out_file:
        # Data structure to keep track of each tallied post.
        tag_counts = defaultdict(int)
        for row in post_list:
            for tag in row.tags:
                tag_counts[tag] += 1

        # Sort data and write tag counts for each category to disk.
        out_str = "\n"
        for tag, count in sorted(
            tag_counts.items(), key=lambda kv: (kv[1]), reverse=True
        ):
            out_str += f"{tag} {count}\n"
        out_str += "\n"
        out_file.write(out_str)

    # Pass 3: Categorical/Bar Charts
    # List of tags to scan and tally.
    chart_data = [
        {
            "javascript": 0.0,
            "java": 0.0,
            "c#": 0.0,
            "php": 0.0,
            "python": 0.0,
            "html": 0.0,
            "c++": 0.0,
            "css": 0.0,
            "sql": 0.0,
            ".net": 0.0,
            "c": 0.0,
            "ruby": 0.0,
            "xml": 0.0,
        },
        {"ios": 0.0, "android": 0.0, "linux": 0.0, "windows": 0.0, "osx": 0.0},
        {
            "regex": 0.0,
            "database": 0.0,
            "multithreading": 0.0,
            "image": 0.0,
            "algorithm": 0.0,
            "performance": 0.0,
            "function": 0.0,
            "api": 0.0,
            "file": 0.0,
            "validation": 0.0,
            "class": 0.0,
            "unit-testing": 0.0,
            "sockets": 0.0,
            "sorting": 0.0,
            "date": 0.0,
            "security": 0.0,
        },
    ]

    # Iterate over each valid post
    for row in post_list:
        for category in chart_data:
            for category_tag in category:
                if category_tag in row.tags:
                    # Increment the count of this tag.
                    category[category_tag] += 1

    # Make each value the ratio of total posts with this tag in the valid post set.
    post_list_len = len(post_list)
    for chart_dict in chart_data:
        for tag, count in chart_dict.items():
            chart_dict[tag] = count / post_list_len

    chart.generate_bar_chart(output_dir / "chart_1_language.png", chart_data[0])
    chart.generate_bar_chart(output_dir / "chart_2_platform.png", chart_data[1])
    chart.generate_bar_chart(output_dir / "chart_3_concept.png", chart_data[2])


def list_similar_tags_sparse(
    output_dir: pathlib.Path, post_ids: set[int], post_data: list[util.PostData]
):
    """Create a text file with similar/recommended tags to the queried tags."""
    # Finds similar tags via a formula derived from TF-IDF.
    # Tags that do not co-occur with the query (similarity score of 0) are omitted.

    # [--- Performance Notes ---]
    # This algorithm's implementation is optimized for sparse datasets,
    # by scanning for unique tags in the list of questions with the queried tags.
    #
    # Let n = the number of unique tags to compare to the queried tags.
    # Empirical usage of the sparse algorithm has O(log(n)) performance,
    # but can be as low as O(1) for very sparse networks
    # and !!! O(n^2) !!! for perfectly dense networks!
    # For dense datasets, it would be more performant
    # to do a single O(n) scan of the entire tag database.
    #
    # Dense tag data will often see the same tag applied to 50% or more of all posts.
    # Stack Overflow's tag limit prefers specific rather than general tags,
    # so this program always uses the sparse algorithm.

    # In a non-demo variant of this program running on a dense dataset,
    # it proved useful to implement and choose between both approaches:
    # if len(post_ids) < 10000:
    #    list_similar_tags_sparse(output_dir, post_ids, post_data)
    # else:
    #    list_similar_tags_dense(output_dir, post_ids)

    # [--- Implementation ---]
    # Store tags and their similarity + relevant info to output.
    ranked_tags = {}
    count = 1
    # Scan every unique tag in every post in the query list.
    unique_tags = []
    for post in post_data:
        count += 1
        for tag in post.tags:
            # Only calculate data for tags that are of a certain output type.
            # If the tag hasn't been encountered yet, process its similarity.
            if tag not in unique_tags:
                unique_tags.append(tag)

    # Connect to the database of tags to post ids.
    con = sqlite3.connect(util.Filepath.cache_tag_to_questions)
    cur = con.cursor()
    for tag in unique_tags:
        posts = cur.execute("SELECT ids FROM tag_to_questions WHERE tag = ?", (tag,))
        posts = pickle.loads(posts.fetchone()[0])

        inter = post_ids.intersection(posts)
        inter_len = len(inter)
        # Add posts with this tag that are shared with the query.
        if inter_len > 0:
            post_len = len(posts)
            # This logarithm ends up devaluing extremely niche tags (1-9 posts),
            # while increasing the rank of popular tags.
            # This log's score multiplier is applied to the ratio of posts
            # in the set to posts in the collection.
            # The resulting number should be high if the tag
            # 1) applies to many posts in the set (TF) and
            # 2) the tag isn't that numerous in the entire collection (IDF).
            score_mult = math.log10(inter_len)
            ratio = inter_len / post_len
            ranked_tags[tag] = (score_mult * ratio, inter_len, post_len, ratio)
    con.close()

    # Sort and print each list of tags.
    posts_len = len(post_ids)
    with open(output_dir / "similar_tags.md", mode="wt", encoding="utf-8") as out_file:
        out_file.write("### Similar Tags\n")
        out_file.write("set_num|col_num %set| tag\n")
        for tag, val in sorted(
            ranked_tags.items(), key=lambda kv: (kv[1][0]), reverse=True
        ):
            set_percentage = str(int((val[1] / posts_len) * 100)).rjust(3)
            out_file.write(
                f"{str(val[1]).rjust(4)}|{str(val[2]).ljust(7)}"
                f" {set_percentage}| {tag}\n"
            )


def generate_obsidian_graph(
    output_dir: pathlib.Path, post_data: list[util.PostData]
) -> None:
    """Plot each question as an Obsidian note with tags."""
    # FOR USERS: use Obsidian's open existing folder as vault option.

    # Performance Note: Obsidian is a text editor first, and graph/visualizer second.
    # This means Obsidian is excellent for diving deeper into individual nodes
    # (when said node is a text file representing a Stack Overflow post).
    # On the other hand, Obsidian struggles to handle queries with a high post count.

    # Only generate Obsidian graphs for queries with a low number of posts.
    if len(post_data) >= util.Options.max_graph_nodes:
        return

    # Create graph directory
    graph_dir = output_dir / "Obsidian-Graph"
    graph_dir.mkdir()

    # Iterate over each valid post
    con = sqlite3.connect(util.Filepath.question_database)
    cur = con.cursor()
    for post in post_data:

        # Create an Obsidian note for this post
        with open(graph_dir / f"{post.post_id}.md", "wt", encoding="utf-8") as out_file:
            # These tags form links on Obsidian's graph view
            # out_file.write("---\ntags:\n")
            # for tag in post.tags:
            #     out_file.write(f"  - {tag}\n")
            # out_file.write("---\n")
            # The below format gives more information while in the "context" view
            out_file.write("#")
            out_file.write(" #".join(post.tags))

            # Fill out the body of the note
            cur.execute(
                "SELECT * FROM questions_table WHERE question_id = ?", (post.post_id,)
            )
            q = util.QuestionData(cur.fetchone())
            out_file.write(f"\nTitle:  {q.title}")
            out_file.write(f"\nPosted: {str(q.created)[:10]}")
            out_file.write(f"\nScore:  {q.score}")
    con.close()
