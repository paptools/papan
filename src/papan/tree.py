from papan import CallNode


class Tree:
    def __init__(self, name, root=None):
        self.name = name
        self.root = root

    def __repr__(self):
        return repr(self.root)

    @property
    def children(self):
        return self.root.children if self.root else ()

    @staticmethod
    def from_trace(trace):
        """Create a tree from a paptrace trace entry."""
        if not isinstance(trace, dict):
            raise TypeError("The JSON object is not a dict.")
        root = CallNode.from_trace(trace)
        param_str = ", ".join(
            [f"{p['name']}={p['value']}" for p in root.params]
        )
        name = f"{root.sig}({param_str})"
        return Tree(name, root)

    def get_cf_nodes(self):
        """Return a list of control flow nodes."""
        return self.root.get_cf_nodes()

    def to_expr(self, known_exprs):
        """Returns a symbolic expression of the tree."""
        return self.root.to_expr(known_exprs)

    def get_loop_nodes(self):
        """Returns a list of loop nodes."""
        return self.root.get_loop_nodes()

    def has_loop(self):
        """Returns True if the tree has at least one loop."""
        return len(self.get_loop_nodes()) > 0
