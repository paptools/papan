import json

from .tree import Tree


def from_file(path):
    """Return a list of trees build from the given paptrace output file."""
    with open(path, "r") as f:
        return from_json(json.load(f))


def from_json(json):
    """Return a list of trees build from the given paptrace output json."""
    traces = json["traces"]
    if not isinstance(traces, list):
        raise TypeError("The traces entry is not a list.")
    trees = []
    for trace in traces:
        trees.append(Tree.from_trace(trace))
    return trees
