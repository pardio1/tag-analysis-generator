# TAG

>"Data science for a simpler time"

Lightweight, performant tag database query analyzer and recommendation algorithm
- Run via command line
- Analysis output stored on disk
	- Study as-is (with text/image viewer of choice)
	- Open in Obsidan's graph view
	- Feed into TAG as another query
- Written in Python/SQL
- Optimized for databases with millions of posts
- Options to customize analysis output
- Simple design to help developers modify program to work with other datasets
- Lightweight: Get up and running within 10 minutes on a toaster; no data-specific machine learning training/smoothing needed!

> [!NOTE]
> This is the public/demo release of TAG.
> 
> This demo is geared towards a publicly-available Stack Overflow scrape of 1.2 million questions containing 3.7 million instances of ~37,000 unique tags.
> 
> The [Performance section](#performance) of this README goes into detail about the algorithms used by TAG, including solutions to bottlenecks encountered with private datasets.

## How To Use

### Downloading/Installation
#### Download TAG and export data:
- Download and unzip TAG's Python files (under `src/`)
	- TAG does not need to be installed; it will be run from the folder it is placed inside.
- Download this [Stack Overflow Scrape ](https://www.kaggle.com/datasets/stackoverflow/stacksample) from Kaggle.
	- Place the extracted Tags.csv and Questions.csv files into the `exports/` folder of TAG.
	- You may need to register a free Kaggle account.

#### Install Libraries
Install [Python](https://www.python.org/downloads/) (TAG was developed on Python 3.12)
```bash
pip install numpy
pip install matplotlib
```

### Basic Usage (Command Line)
> [!CAUTION]
> TAG utilizes a cache to speed up processing. This cache can take several minutes to generate on your first run of the program, but only needs to be generated once.
```bash
# By default, TAG is run from the current working directory
cd path/to/TAG/driver.py

# Run the program with default commands.
# This will generate an output/ folder containing analysis reuslt of a sample query.
python driver.py

# Specify another folder to read/write data
# (Useful for having one copy of TAG analyze different snapshots of a database)
python driver.py --source /path/to/folder/

# Include Obsidian graphs in output
python driver.py --graph
# Include Obsidian graphs but only for queries with 50 or less posts (default 500 posts)
python driver.py --graph --graph_nodes 50
```

## Input: Queries
A query can be thought of as a tag: `python`

A query can be the combination of multiple tags: `python sql`

TAG reads queries from text files in `input/` rather than the command line. This facilitates processing thousands of queries at once and keeping a history of queries to the system. Here is an example file containing 3 queries: `input/sample_queries.txt`
```text
maps
python sql
python sql -sql-server
```
> [!TIP]
> TAG will output text files of tags relevant to the given query. These text files can also be used as queries in `input/`.
### Query Syntax
> [!NOTE]
> Queries contain syntax to AND and NOT tags.
> OR is not supported.
> Order of tags is ignored; there is no () operator.

- TAG will process all .txt files in `input/`
- Each line of an input file is a new query
- A query can contain zero, one, or multiple space-separated tags
	- Posts must contain all tags in the query (boolean AND)
	- Posts must not contain any tag in the query that starts with `-` (boolean NOT)
	- If no tag is supplied (an empty line), then the query is treated as containing all posts in the database

## Output
### Output: Text
#### tag_counts.md:
A simple count of tags, ranked by number of instances in the query (not the database).
```text
### Tag Counts
maps 547
android 118
google-maps 101
javascript 99
(...)
```
#### similar_tags.md:
A ranked list of tags, based on a formula derived from TF-IDF.
The columns in the analyzed data help differentiate if a tag was ranked similar because it is very popular across the dataset (TF) versus tags that occupy a niche that overlaps with the query (IDF).

Columns:
- set_num: Count of posts in the query (collection) with this tag.
- col_num: Count of posts in the database (collection) with this tag.
- %set: Percentage of posts in the set with this tag.
- tag: text name of tag.

```text
### Similar Tags
set_num|col_num %set| tag
 547|547     100| maps
 101|4775     18| google-maps
  25|831       4| geolocation
   8|176       1| latitude-longitude
(...)
   1|2825      0| dictionary
   1|1009      0| insert
   1|543       0| logic
   1|15        0| transport
```
### Output: Charts
#### Categorical Bar Charts
See how the query stacks up against frequently-referenced tags with bar charts:
![Bar chart comparing occurences of programming language tags in the query.](/images/barchart.png)
#### Score Scatter Plot
The score scatter plot helps visualize the posting frequency of the tag, how those posts are ranked, and any relation between the word count of a post and it's score:
![Scatter plot comparing the score, date, and word count of individual posts in the query.](/images/scatterplot.png)
### Output: Obsidian Graphs

> [!IMPORTANT]
> Remember to enable Obsidian graph output (and that the query size isn't larger than the graph node limit)!
>```bash
># Include Obsidian graphs for queries with 500 or less posts
>python driver.py --graph --graph_nodes 500
>```

#### Benefits of Obsidian Graphs:
- See connections between tags
- Spot regions shared by nearby tags
- Investigate notes of interest with the Tag View plugin
- Utilize Obsidian's search filters
- Make use of Obsidian's newly-added ✨command line interface✨

![Obsidians Graph view.](/images/dataviz_small.jpg)

#### Set-Up an Obsidian Vault
1. Manage Vaults -> Open new vault -> navigate to the Obsidian-Graph folder of the desired query.
2. Open Graph View (on the left side command bar)
3. Enable Tags (under the Filters tab of the graph view settings)

> [!TIP]
> When viewing posts linked to a tag node, hold `control` when hovering over posts to view the post's details (such as their title, body, and score). Enable the option to "Show more context" so that simply hovering over posts shows details.
> 
> This requires the Tag View core plugin, which is installed and enabled by default.

Example Tag View of a post (Question 10337640):
![Obsidians Tag view showing a post's details.](/images/post_details.png)
## Performance Writeup
> [!WARNING]
> Stats for ✨ nerds ✨ ahead :)
### Notation
Let:
- P = number of posts in the database
- T = number of (unique) tags in the database
- P<sub>q</sub> = number of posts matching query
- T<sub>q</sub> = number of (unique) tags matching query

- Queries are bounded by the size of the database:
	- P<sub>q</sub>  <= P
	- T<sub>q</sub>  <= T.
	- In the worst case (a query matches the entire database), P<sub>q</sub>  == P and T<sub>q</sub>  == T.
	- In practice, a query's posts and tags (P<sub>q</sub>, T<sub>q</sub>) will be several factors smaller than the database's posts and tags (P, T).
		- This is the case TAG is optimized for.

### Cache Design and Memory Optimization
Motivation:
	A map data structure is essential as it enables constant-time O(1) lookup of any post or tag rather than a linear-time O(P) or O(T) scan of the database.
Solution:
	An inverted index maps any given tag to its associated posts, alongside other maps.
	SQL is used to implement this cache.
		-A built-in Python dict may hold gigabytes of data in memory at once.
		-However, most queries only access a few rows of the millions that may be in a map. Thus, storing the map on disk and retrieving desired rows with SQL saves a significant amount of memory with minimal slowdown.

Memory Hogs:
	For simplicity (i.e. ease of modifying TAG to operate on other datasets), TAG's data is object-oriented (rather than data-orientated) and output is assembled is several passes. The pass-based system of the output means that we need to fetch or reuse the object holding a post's data for each pass. For memory usage, this means that:
- Every post associated with the query will be loaded at once
- With multi-core processing, multiple queries will be loaded at once

> [!IMPORTANT]
> Developers: TAG using too much memory?
>- Prune posts from the original database to contain only "active" posts
>- Condense each post to contain only data used by TAG
>- Disable multi-core processing if large queries are detected during pre-processing
### Recommendation Algorithm Basics
Goal:
	The goal of the recommendation algorithm is to output a list of tags ranked by semantic similarity to the input query.
		Example: If someone searches for "math," then "algebra" should be recommended before "furniture."

TAG's formula is based on the TF-IDF algorithm:
A given tag's score should be high (tag is highly recommended) if:
1. the query/tag applies to many posts in the set (TF)
2. the query/tag isn't that numerous in the entire collection (IDF).
Compared to the original form of TF-IDF, outputs tags (words) rather than posts (documents). Stated differently, tag will recommend "similar searches" rather than specific posts.

> [!NOTE]
> A logarithm is applied to the score, to devalue extremely niche tags (1-9 posts), while flattening the rank of extremely popular tags (1000+ posts). The goal is to have mid-size tags (10-1000 posts) have relatively higher visibility, as they contain a worthwhile amount of posts to study but are not so large as to encompass the entire database.
> 
> Tags that do not occur in any post matched with the query (similarity score of 0) are omitted from the results--this facilitates an optimization unique to the sparse algorithm's implementation.
### Recommendation Algorithm: Sparse vs Dense Optimization
#### Dense Algorithm
A naive approach is to scan each of the T tags in the database and calculate the query similarity for each of them.
	Runtime Performance: O(T)
	-query-independent
	-This ends up being the optimal approach for densely-connected datasets (where we'd need to rank most of the tags anyways).

#### Sparse Algorithm
Scan each tag of each post in the query to form a set of unique tags, then rank each of those unique tags.
	Runtime Performance: O(P<sub>q</sub>T<sub>q</sub>)
		-query-dependent, heavily dependent on sparseness/density of database
		-At the cost of some overhead, this algorithm can calculate similarity for T<sub>q</sub> rather than T tags--skipping calculating similarity for any tag that would have a rank of 0. This takes advantage of the observation that, for most queries, T<sub>q</sub> <<< T.

Empirical usage of the sparse algorithm has O(log(P<sub>q</sub>)) performance, but can be as low as O(1) for very sparse networks and as high as ⚠️ O(PT) ⚠️ for very dense networks!

#### Which is better: Dense or Sparse?
![Chart of performance of dense vs sparse algorithm.](/images/chart_dense_vs_sparse.png)
The performance of the sparse version of the algorithm greatly depends on the query, whereas the dense algorithm runs at a large but constant time independent of query size (the overall execution time change is from other sources). The charts reveal that neither algorithm is the best in *every* case, even if one is better than the other in *some* cases.

Thankfully, we can determine which algorithm is best on a per-query basis by pre-processing a query and using a heuristic to guess if it's going to be sparse or dense. This pre-processing varies based on the dataset, but an approach like the below is a good starting point:
1. Make a query list of a query with 10 posts, 100 posts, 1000 posts, etc...
2. Run the test suite through only the sparse algorithm, noting the times for each query. Then do the same for dense.
3. The sparse algorithm should perform better on small queries, but eventually the dense algorithm will start to perform better. Try to figure out the number of posts where both algorithms have the same performance--this will be your threshold.
4. Within TAG's code, compare the number of posts in the query to the magical threshold and choose the appropriate algorithm:
```python
# Threshold of 10000 found through empirical testing
if len(query_posts) < 10000:
	recommnded tags = list_similar_tags_sparse(...)
else:
	recommnded tags = list_similar_tags_dense(...)
```

> [!NOTE]
> The demo version of TAG always uses the sparse algorithm as curiously Stack Overflow's tagging culture avoids general tags in favor of a a small number of specific tags.
>- The most popular tag, javascript, represents only 10.3% of Stack Overflow posts in the dataset (124,155 of 1.2 million posts).
>- The dataset contains only three tags with more than 100,000 posts: javascript, java, and C#.

> [!NOTE]
> One instance of TAG has been used on a densely-connected dataset of 6-7 😼 million posts, although most (but not all) queries involve relatively niche (sparsely-connected) tags. In such a case, it's worth the overhead to pre-process a query and determine if the sparse or dense recommendation algorithm is appropriate.
#### Runtime Performance Bottlenecks:
The main runtime bottlenecks for the program are plotting the matplotlib (MPL) charts and running the recommendation algorithm (TF-IDF). Here are two charts estimating the runtime usage of MPL and the sparse/dense TF-IDF as the query size increases:

![Chart of performance of dense vs sparse algorithm.](/images/chart_sparse_annotated.png)

![Chart of performance of dense vs sparse algorithm.](/images/chart_dense_annotated.png)

---
2026 Oliver Pardi