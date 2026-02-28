"""Receive and report data about current state of program."""

import time


def start_progress_bar():
    """Start reporting."""
    ProgressBar.exec_finished = False
    ProgressBar.start_time = time.time()

    report_progress()


def end_progress_bar():
    """End reporting."""
    ProgressBar.exec_finished = True


def start_new_stage(stage_text, max_steps):
    """Set a new series of tasks."""
    ProgressBar.current_stage = stage_text
    ProgressBar.max_step = max_steps
    ProgressBar.current_step = 0


def update_step(current_step):
    """Set completed tasks to input value."""
    ProgressBar.current_step = current_step


def update_step_one():
    """Increment completed tasks by one."""
    ProgressBar.current_step += 1


def report_progress():
    """Print current task status."""
    while not ProgressBar.exec_finished:
        # Get the current time relative to start of program execution
        current_time = time.time() - ProgressBar.start_time
        print(
            f"{round(current_time, 0)}s: [{ProgressBar.current_stage}] "
            f"{ProgressBar.current_step} / {ProgressBar.max_step}"
        )

        # Wait between reports.
        # Subtract the time it takes to run this function and switch threads.
        time.sleep(ProgressBar.report_interval - (current_time % 1))


class ProgressBar:
    """Object to bundle functionality for displaying progress of current operation."""

    # Stage is a text description of the current goal.
    # Step is a single operation.
    current_stage = "Initializing"
    current_step = 1
    max_step = 1

    # Start times
    start_time = 0
    start_time_stage = 0

    # Flag
    exec_finished = False

    # Options
    # How many seconds to wait between reports
    report_interval = 1
