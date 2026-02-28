"""Generate matplotlib representations of data."""

import pathlib
import datetime
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.units as munits

# Have matplotlib use a concise formatter for time-based data
converter = mdates.ConciseDateConverter()
munits.registry[np.datetime64] = converter
munits.registry[datetime.date] = converter
munits.registry[datetime.datetime] = converter


def generate_scatter_plot(filename: pathlib.Path, chart_data: list[dict]):
    """Generate scatter plot, where each point is a question."""
    fig, ax = plt.subplots()
    # A dark grey
    # ax.set_facecolor("#4c6185")
    # A light grey
    # ax.set_facecolor("#adbed9")
    # a dark white
    # ax.set_facecolor("#bacae3")
    # A light white
    ax.set_facecolor("#deeafc")

    # Default size is 6.4 x 4.8
    # fig.set_size_inches(10, 10)

    for dataset in chart_data:
        ax.scatter(
            dataset["x_data"],
            dataset["y_data"],
            c=dataset["color"],
            label=dataset["label"],
            alpha=0.8,
            edgecolors="none",
        )
    # ax.set_title(chart_title)

    ax.legend(loc="upper right")
    ax.grid(True)

    fig.tight_layout()
    fig.savefig(filename, facecolor="#adbed9", bbox_inches="tight", pad_inches=0)
    plt.close(fig)


def generate_bar_chart(filename: pathlib.Path, data: dict):
    """Generate bar chart, where each bar is a tag."""
    # Data: each bar is an element of data, with key = name and value = bar length.

    fig, ax = plt.subplots()
    ax.set_facecolor("#deeafc")

    width = 0.6
    bar_container = ax.bar(data.keys(), data.values(), width)
    ax.bar_label(bar_container, labels=data.keys(), label_type="edge", rotation=35.0)

    # remove x-axis labels
    ax.set_xticklabels([])
    ax.set_yticks(np.arange(0.0, 1.01, 0.2))

    fig.tight_layout()
    fig.savefig(filename, facecolor="#adbed9", bbox_inches="tight", pad_inches=0)
    plt.close(fig)
