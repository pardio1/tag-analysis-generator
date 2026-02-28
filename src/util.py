"""Options/Utilities that are used throughout the program."""

import pathlib
import pickle
import os


def read_last_line(file_path: pathlib.Path) -> str:
    """Read the last line from a file and return it."""
    with open(file_path, "rb") as f:
        try:
            f.seek(-2, os.SEEK_END)  # Jump to the second-to-last byte
            while f.read(1) != b"\n":
                f.seek(
                    -2, os.SEEK_CUR
                )  # Jump back two bytes (over the read byte and one more)
        except OSError:
            # Handle the case where the file is very short (e.g., one line)
            f.seek(0)

        last_line_bytes = f.readline()
        return last_line_bytes.decode().strip()  # Decode the bytes and strip newlines


class Options:
    """Options for process_tags."""

    # Don't generate Obsidian graphs for posts above this amount.
    max_graph_nodes = 500

    # Magic Numbers (MARKED FOR DEPRECIATION)
    # number of files / posts/ entries /documents
    num_posts = 111
    # Number of attributes / categories / tags / lexicon
    num_tags = 333

    # Total queries; set at runtime.
    # This number is used to determine how to utilize multiple cores.
    # If queries < cores, then each query is sequentially processed,
    # with the recommendation algorithm processed via a MapReduce framework.
    # If queries >= cores, then each query is processed by a different core.
    parallelize_query_subtask = False


def set_num_posts(num_posts: int):
    """Set the number of posts."""
    Options.num_posts = num_posts


def set_max_graph_nodes(max_graph_nodes: int):
    """Set the max graph nodes."""
    Options.max_graph_nodes = max_graph_nodes


class FileNotFound(Exception):
    """Custom Exception, for use when a file was not found."""

    def __init__(self, message="File Not Found", value=None):
        """Produce an error message."""
        self.message = message
        self.value = value
        super().__init__(self.message)


class Filepath:
    """Provide access to pathlib Paths for all I/O file locations."""

    # Directories
    root = pathlib.Path(os.getcwd())
    cache_dir = root / "cache"
    export_dir = root / "exports"
    tags_in_dir = root / "tags_in"
    tags_out_dir = root / "tags_out"

    # Cache
    tag_database = cache_dir / "tag_data.db"
    question_database = cache_dir / "question_data.db"
    cache_tag_to_questions = cache_dir / "tag_to_questions.db"
    cache_info = cache_dir / "cache_info.json"
    cache_tag_to_category = cache_dir / "tag_to_category.json"
    cache_tag_counts = cache_dir / "tag_counts.json"
    cache_postid_database = cache_dir / "postid.db"


def set_root(root: pathlib.Path):
    """Set the root folder and update Paths for all I/O file locations."""
    # Directories
    Filepath.root = root
    Filepath.cache_dir = root / "cache"
    Filepath.export_dir = root / "exports"
    Filepath.tags_in_dir = root / "tags_in"
    Filepath.tags_out_dir = root / "tags_out"

    # Cache
    Filepath.tag_database = Filepath.cache_dir / "tag_data.db"
    Filepath.question_database = Filepath.cache_dir / "question_data.db"
    Filepath.cache_tag_to_questions = Filepath.cache_dir / "tag_to_questions.db"
    Filepath.cache_info = Filepath.cache_dir / "cache_info.json"

    Filepath.cache_tag_to_category = Filepath.cache_dir / "tag_to_category.json"
    Filepath.cache_tag_counts = Filepath.cache_dir / "tag_counts.json"
    Filepath.cache_postid_database = Filepath.cache_dir / "postid.db"


def ensure_dirs_exist():
    """Ensure directories exist."""
    Filepath.cache_dir.mkdir(parents=True, exist_ok=True)
    Filepath.export_dir.mkdir(parents=True, exist_ok=True)
    Filepath.tags_in_dir.mkdir(parents=True, exist_ok=True)
    Filepath.tags_out_dir.mkdir(parents=True, exist_ok=True)


class PostData:
    """Provides convenient access to members of a pre-processed post in the database."""

    def __init__(self, data):
        """Initialize members from a table row."""
        # Data is all members from a query to the posts database.
        self.post_id = data[0]
        self.tags = pickle.loads(data[1])


class QuestionData:
    """Provides convenient access to members of a pre-processed post in the database."""

    def __init__(self, data):
        """Initialize members from a table row."""
        # Data is all members from a query to the posts database.
        self.question_id = data[0]
        self.created = pickle.loads(data[1])
        self.score = data[2]
        self.title = data[3]
        self.body_length = data[4]
