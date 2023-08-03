import json
import pathlib
import pytest

from papan import utils


class TestGroupFromFile:
    def test_file_not_found(self):
        path = pathlib.Path("does_not_exist")
        with pytest.raises(FileNotFoundError):
            utils.from_file(path)

    def test_file_not_json(self, tmp_path):
        path = tmp_path / "not_json.txt"
        with open(path, "w") as f:
            f.write("not json")
        with pytest.raises(json.decoder.JSONDecodeError):
            utils.from_file(path)

    def test_returns_tree_list(self, tmp_path):
        data = {
            "traces": [
                {
                    "id": 123,
                    "type": "CallerExpr",
                    "sig": "int foo(int, int)",
                    "params": [
                        {"name": "a", "value": "-1"},
                        {"name": "b", "value": "1"},
                    ],
                    "children": [],
                }
            ]
        }
        path = tmp_path / "trace.json"
        with open(path, "w") as f:
            json.dump(data, f)
        trees = utils.from_file(path)
        assert isinstance(trees, list)
        assert len(trees) == 1
        tree = trees[0]
        assert tree.name == "int foo(int, int)(a=-1, b=1)"
        assert tree.root.name == 123

    def test_actual_data(self):
        path = pathlib.Path(__file__).parent / "data" / "paptrace.json"
        trees = utils.from_file(path)
        assert isinstance(trees, list)
        assert len(trees) == 36
        tree = trees[0]
        assert (
            tree.name
            == "unsigned long long fibonacci::RecursiveNaive(unsigned"
            " short)(n=0)"
        )
        root = tree.root
        assert root.name == 2106190
        assert (
            root.sig
            == "unsigned long long fibonacci::RecursiveNaive(unsigned short)"
        )
        assert root.params == [{"name": "n", "value": "0"}]
        assert len(root.children) == 1
        child = tree.root.children[0]
        assert child.name == 2106009
        assert child.type == "IfThenStmt"
        assert child.desc == "n < 2"
        assert len(child.children) == 1


class TestGroupFromJson:
    def test_no_traces_entry(self):
        with pytest.raises(KeyError, match="'traces'"):
            utils.from_json({"version": "0.1.0"})

    def test_non_list_traces_entry(self):
        with pytest.raises(TypeError, match="The traces entry is not a list."):
            utils.from_json({"version": "0.1.0", "traces": {}})

    def test_empty_traces_list(self):
        assert utils.from_json({"version": "0.1.0", "traces": []}) == []

    def test_single_trace(self, tmp_path):
        data = {
            "traces": [
                {
                    "id": 123,
                    "type": "CallerExpr",
                    "sig": "int foo(int, int)",
                    "params": [
                        {"name": "a", "value": "-1"},
                        {"name": "b", "value": "1"},
                    ],
                    "children": [],
                }
            ]
        }
        trees = utils.from_json(data)
        assert isinstance(trees, list)
        assert len(trees) == 1
        tree = trees[0]
        assert tree.name == "int foo(int, int)(a=-1, b=1)"
        assert tree.root.name == 123

    def test_multiple_traces(self, tmp_path):
        data = {
            "traces": [
                {
                    "id": 123,
                    "type": "CallerExpr",
                    "sig": "int foo(int, int)",
                    "params": [
                        {"name": "a", "value": "-1"},
                        {"name": "b", "value": "1"},
                    ],
                    "children": [],
                },
                {
                    "id": 456,
                    "type": "CallerExpr",
                    "sig": "int bar(long, char)",
                    "params": [
                        {"name": "b", "value": "-1"},
                        {"name": "c", "value": "1"},
                    ],
                    "children": [],
                },
            ]
        }
        trees = utils.from_json(data)
        assert isinstance(trees, list)
        assert len(trees) == 2
        foo_tree = trees[0]
        assert foo_tree.name == "int foo(int, int)(a=-1, b=1)"
        assert foo_tree.root.name == 123
        bar_tree = trees[1]
        assert bar_tree.name == "int bar(long, char)(b=-1, c=1)"
        assert bar_tree.root.name == 456
