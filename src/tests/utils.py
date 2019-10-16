# -*- coding: utf-8 -*-
"""
Test utilities
"""
import inspect
import json
import os


def get_content(filename):
    """
    Returns the content of the filname within the tests directory
    """
    file_path = get_file_path(filename)

    with open(file_path) as fh:
        return fh.read()


def get_file_path(filename):
    """
    Returns the full path to a test data file
    """
    # index 0 in the frame stack is this function call
    # iterate up the frame stack until the test file is found
    frames = inspect.getouterframes(inspect.currentframe())
    for frame in frames:
        frame_filename = frame.filename

        dirname = os.path.dirname(frame_filename)

        path = os.path.join(dirname, "files", filename)

        if not os.path.exists(path):
            continue

        return path
    else:
        raise FileNotFoundError()


def get_json(filename):
    """
    Returns the content of the given filename as a parsed JSON object
    """
    return json.loads(get_content(filename))
