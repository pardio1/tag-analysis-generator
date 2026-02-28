"""Generate and use a cache for speedier processing.

Contains functions for reading /exports/ and outputting cached files in /cache/.
"""

import csv
import datetime
import os
import json
import pickle
import sqlite3
from collections import defaultdict
import util
import progressbar


def generate_cache_if_missing():
    """Check for existing cache files.

    Attempts to generate missing cache files.
    """
    # Retrieve values from the cache info file, or generate a new one if missing.
    if util.Filepath.cache_info.exists():
        with open(util.Filepath.cache_info, "rt", encoding="utf-8") as in_file:
            cache_info = json.loads(in_file.read())
    else:
        # If the info file is missing, generate a default one
        cache_info = {
            "cached_tags": False,
            "cached_questions": False,
            "current_version": 1,
        }
        update_cache_info(cache_info)

    # Detect if any cache files are missing and regenerate them as necessary.
    # Step 1: Cache Tags
    if (
        cache_info["cached_tags"]
        and util.Filepath.tag_database.exists()
        and util.Filepath.cache_tag_to_questions.exists()
    ):
        pass
    else:
        print("Cache missing/incomplete. Generating cache.")
        print("  This one-time process may take a few minutes.")
        print(
            "  Your request will be processed after generating the missing cache files."
        )
        # Remove any existing tag files
        if util.Filepath.tag_database.exists():
            os.remove(util.Filepath.tag_database)
        if util.Filepath.cache_tag_to_questions.exists():
            os.remove(util.Filepath.cache_tag_to_questions)
        cache_info["cached_tags"] = False
        update_cache_info(cache_info)

        # Create and fill out a new database
        cache_tags()
        # Mark the config file as having successfully processed tag data
        cache_info["cached_tags"] = True
        update_cache_info(cache_info)

    # Step 2: Cache Questions
    if cache_info["cached_questions"] and util.Filepath.question_database.exists():
        pass
    else:
        # Remove any existing question files
        if util.Filepath.question_database.exists():
            os.remove(util.Filepath.question_database)
        cache_info["cached_questions"] = False
        update_cache_info(cache_info)

        # Create and fill out a new database
        cache_questions()
        # Mark the config file as having successfully processed question data
        cache_info["cached_questions"] = True
        update_cache_info(cache_info)


def cache_tags():
    """Process tags export file into a pruned table and tag-to-ids table."""
    # Search for an export of the form "Tags.csv".
    export_file = None
    for file in os.listdir(util.Filepath.export_dir):
        if file == "Tags.csv":
            export_file = util.Filepath.export_dir / file
            break
    # Exit if the file was not found
    if not export_file:
        raise (
            util.FileNotFound(
                message=f"File Not Found: {util.Filepath.export_dir}/Tags.csv"
            )
        )

    # Get the number of lines in the export file
    # Value hardcoded for Stack Overflow dataset.
    # last_line = util.read_last_line(export_file)
    # num_lines = last_line.split(",", maxsplit=1)[0]
    # if not num_lines.isnumeric():
    #    print("Unable to estimate length of export file, ETA inaccurate.")
    #    num_lines = 0
    util.set_num_posts(40143380)

    progressbar.start_new_stage("Cache Stage 1/3:", util.Options.num_posts)

    # Connect to the database
    con = sqlite3.connect(util.Filepath.tag_database)
    # Create the cursor.
    cur = con.cursor()

    # Initialize the tags table.
    # question_id: primary key.
    # tags: (pickled) list of strings
    cur.execute("CREATE TABLE tags_table(question_id INTEGER PRIMARY KEY, tags BLOB)")

    current_question_id = 0
    # The csv has a new row for each individual tag on a question,
    # but the database stores all tags for a question in a single block.
    merged_tags = []
    # Keep track of every unique tag used on Stack Overflow
    unique_tags = set()
    # Map a tag to all questions with that tag
    tag_to_ids = defaultdict(set)

    # Read in the Tags file.
    with open(export_file, "rt", encoding="utf-8") as in_file:
        # Create a csv.reader object
        csv_reader = csv.reader(in_file, delimiter=",", quotechar='"')
        # Skip the header row:
        next(csv_reader, None)

        # Iterate over each row in the CSV file
        for row in csv_reader:
            # position - value
            # 0 Question ID
            # 1 Tag
            question_id = int(row[0])
            tag = row[1]

            progressbar.update_step(question_id)
            # If we've moved onto a new question, save the previous question's data
            if question_id != current_question_id:
                data = (current_question_id, pickle.dumps(merged_tags))
                cur.execute("INSERT INTO tags_table VALUES(?, ?)", data)
                # Prepare for the next question's data
                current_question_id = question_id
                merged_tags = []
            unique_tags.add(tag)
            merged_tags.append(tag)
            tag_to_ids[tag].add(question_id)

    # Write the last question's data to disk
    data = (current_question_id, pickle.dumps(merged_tags))
    cur.execute("INSERT INTO tags_table VALUES(?, ?)", data)
    # Commit changes to database.
    con.commit()
    # Close the connection.
    con.close()

    # Connect to the database
    con = sqlite3.connect(util.Filepath.cache_tag_to_questions)
    # Create the cursor.
    cur = con.cursor()

    # Initialize the table of tags mapped to questions with that tag.
    # tag: primary key.
    # ids: (pickled) list of ints
    cur.execute("CREATE TABLE tag_to_questions(tag TEXT PRIMARY KEY, ids BLOB)")

    # We'll end up loading the entire tags.csv file into memory with this method,
    # but the Stack Overflow data is fairly small so it's not an issue.
    # Initialize mapping a tag to a list of question_ids.
    progressbar.start_new_stage("Cache Stage 2/3:", len(tag_to_ids))
    for tag, id_list in tag_to_ids.items():
        data = (tag, pickle.dumps(id_list))
        cur.execute("INSERT INTO tag_to_questions VALUES(?, ?)", data)
        progressbar.update_step_one()
    # Commit changes to database.
    con.commit()
    # Close the connection.
    con.close()


def cache_questions():
    """Process questions export file into a pruned table."""
    # Search for an export of the form "Questions.csv".
    export_file = None
    for file in os.listdir(util.Filepath.export_dir):
        if file == "Questions.csv":
            export_file = util.Filepath.export_dir / file
            break
    # Exit if the file was not found
    if not export_file:
        raise (
            util.FileNotFound(
                message=f"File Not Found: {util.Filepath.export_dir}/Questions.csv"
            )
        )

    # Get the number of lines in the export file.
    # Value hardcoded for Stack Overflow dataset.
    num_lines = 39666760
    util.set_num_posts(num_lines)

    progressbar.start_new_stage("Cache Stage 3/3:", util.Options.num_posts)

    # Connect to the database
    con = sqlite3.connect(util.Filepath.question_database)
    # Create the cursor.
    cur = con.cursor()
    # Initialize the pruned question data table.
    # question_id: primary key
    # created: (pickled) datetime of question creation date
    # score: score of question
    # title: title of question
    # body_length: length of body of question
    cur.execute(
        "CREATE TABLE questions_table(question_id INTEGER PRIMARY KEY, created BLOB,"
        " score INTEGER, title TEXT, body_length INTEGER)"
    )

    # Read in the Questions file.
    # Stack Overflow evidently uses a different text encoding than UTF-8
    with open(export_file, "rt", encoding="latin-1") as in_file:
        # Create a csv.reader object
        csv_reader = csv.reader(in_file, delimiter=",", quotechar='"')
        # Skip the header row:
        next(csv_reader, None)
        # Iterate over each row in the CSV file
        for row in csv_reader:
            # position - value
            # 0 Question ID
            # 1 Question Owner ID
            # 2 Creation Date
            # 3 Closed Date
            # 4 Score
            # 5 Title
            # 6 Body

            question_id = int(row[0])
            progressbar.update_step(question_id)

            # Example creation date value from csv: 2008-08-01T13:57:07Z
            # We convert dates to python datetime objects, which are faster to process
            # but use more storage in the database.
            created = datetime.datetime.fromisoformat(row[2])

            score = int(row[4])
            title = row[5]
            body_length = len(row[6])

            # Save processed data to disk
            data = (question_id, pickle.dumps(created), score, title, body_length)
            cur.execute("INSERT INTO questions_table VALUES(?, ?, ?, ?, ?)", data)
    # Commit changes to database.
    con.commit()
    # Close the connection.
    con.close()


def update_cache_info(cache_info: dict):
    """Store current state of caching process."""
    # It's possible for a database to be created but missing data
    # (such as interrupting the caching process).
    # This file helps deduce if a cache file exists but has incomplete data.
    with open(util.Filepath.cache_info, "wt", encoding="utf-8") as out_file:
        out_file.write(json.dumps(cache_info, separators=(",", ":")))
