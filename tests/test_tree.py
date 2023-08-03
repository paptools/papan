import re

import anytree
import pytest

from papan import Node, Tree


class TestGroupTree:
    def test_name_only(self):
        tree = Tree("foo")
        assert tree.name == "foo"
        assert tree.root == None
        assert tree.children == ()

    def test_root(self):
        root = Node("root")
        tree = Tree("foo", root=root)
        assert tree.name == "foo"
        assert tree.root == root
        assert tree.children == ()

    def test_children(self):
        child_a = Node("child_a")
        child_b = Node("child_b")
        root = Node("root", children=[child_a, child_b])
        tree = Tree("foo", root=root)
        assert tree.name == "foo"
        assert tree.root == root
        assert tree.children == (child_a, child_b)

    def test_repr(self):
        root = Node("root", val=1)
        child = Node("child", val=2)
        tree = Tree("foo", root=root)
        assert repr(tree) == "Node(name='root', val=1)"

    def test_render_tree(self):
        root = Node("root", val=1)
        child = Node("child", val=2, parent=root)
        tree = Tree("foo", root=root)
        rendered_tree = anytree.RenderTree(tree)
        expected = "Node(name='root', val=1)\n└── Node(name='child', val=2)"
        assert rendered_tree.__str__() == expected
