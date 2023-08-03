import anytree
import sympy


class Node(anytree.AnyNode):
    def __init__(self, name, type_, parent=None, children=None, **kwargs):
        super(Node, self).__init__(
            name=name, type=type_, parent=parent, children=children, **kwargs
        )

    def __eq__(self, other):
        if not isinstance(other, Node):
            # don't attempt to compare against unrelated types
            return NotImplemented
        return repr(self) == repr(other)

    # @property
    # def type(self):
    #    return self._type

    @staticmethod
    def is_call_type(type_):
        return type_ in ["CallerExpr", "CalleeExpr"]

    def is_call_node(self):
        return Node.is_call_type(self.type)

    @staticmethod
    def is_cf_type(type_):
        return type_ in [
            "IfThenStmt",
            "ReturnStmt",
            "CXXThrowExpr",
            "ForStmt",
            "WhileStmt",
            "LoopIter",
        ]

    def is_cf_node(self):
        return Node.is_cf_type(self.type)

    @staticmethod
    def is_loop_type(type_):
        return type_ in ["ForStmt", "WhileStmt"]

    def is_loop_node(self):
        return Node.is_loop_type(self.type)

    @staticmethod
    def is_iter_type(type_):
        return type_ in ["LoopIter"]

    def is_iter_node(self):
        return Node.is_iter_type(self.type)

    @staticmethod
    def from_trace(trace):
        if Node.is_call_type(trace["type"]):
            return CallNode.from_trace(trace)
        elif Node.is_loop_type(trace["type"]):
            return LoopNode.from_trace(trace)
        else:
            return StmtNode.from_trace(trace)

    def get_cf_nodes(self):
        raise NotImplementedError

    def to_expr(self, known_exprs):
        raise NotImplementedError

    def get_loop_nodes(self):
        """Returns a list of loop nodes."""
        loop_nodes = []
        for child in self.children:
            loop_nodes.extend(child.get_loop_nodes())
        if self.is_loop_node():
            loop_nodes.append(self)
        return loop_nodes


class StmtNode(Node):
    def __init__(self, name, type_, desc, parent=None, children=None):
        super(StmtNode, self).__init__(name, type_, parent, children, desc=desc)
        self._desc = desc

    @property
    def desc(self):
        return self._desc

    @staticmethod
    def from_trace(trace):
        if Node.is_call_type(type_ := trace["type"]):
            raise ValueError(f"Type '{type_}' is not a StmtNode type.")
        children = [Node.from_trace(child) for child in trace["children"]]
        desc = (
            trace["sig"] if "sig" in trace else trace["desc"]
        )  # For op nodes.
        return StmtNode(
            name=trace["id"],
            type_=type_,
            desc=desc,
            children=children,
        )

    def get_cf_nodes(self):
        """Return a list of control flow nodes."""
        cf_nodes = [self.name] if self.is_cf_node() else []
        for child in self.children:
            cf_nodes.extend(child.get_cf_nodes())
        return cf_nodes

    def to_expr(self, known_exprs):
        """Returns a symbolic expression of the tree."""
        if self.desc in known_exprs:
            expr = sympy.sympify(known_exprs[self.desc])
        else:
            expr = (
                sympy.sympify(f"T_{self.name}")
                if not self.is_cf_node()
                else None
            )
        for child in self.children:
            child_expr = child.to_expr(known_exprs)
            if child_expr is None:
                continue
            expr = child_expr if expr is None else expr + child_expr
        return expr


class LoopNode(StmtNode):
    def __init__(self, name, type_, desc, parent=None, children=None):
        super(LoopNode, self).__init__(name, type_, desc, parent, children)
        self._loop_expr = None
        self.iter_block = []
        self.iter_count = 0
        self.trailing_iter_block = None
        self._partition_children()

    def set_loop_expr(self, loop_expr):
        """Set the loop expression."""
        print(f"    Setting loop expr for {id(self)} to {loop_expr}")
        self._loop_expr = loop_expr

    # def get_loop_expr(self):
    #    """Return the loop expression."""
    #    print(f"  Getting loop expr for {id(self)}: {self.loop_expr}")
    #    return self._loop_expr

    @staticmethod
    def from_trace(trace):
        if not Node.is_loop_type(type_ := trace["type"]):
            raise ValueError(f"Type '{type_}' is not a LoopNode type.")
        children = [Node.from_trace(child) for child in trace["children"]]
        desc = (
            trace["sig"] if "sig" in trace else trace["desc"]
        )  # For op nodes.
        return LoopNode(
            name=trace["id"],
            type_=type_,
            desc=desc,
            children=children,
        )

    def _partition_children(self):
        """Partition children into pre-body, body, and post-body nodes."""
        if len(self.children) == 0:
            return

        # We need to walk through an entire iteration to determine the pre-body and
        # post-body nodes if there are any.
        # Note that pre-body nodes will be execcuted for each iteration, while post-body
        # nodes will be executed if the loop does not exit early.
        pre_body_nodes = []
        post_body_nodes = []
        in_pre_body = True
        for child in self.children:
            if child.is_iter_node():
                if not in_pre_body:
                    # We have walked an entire iteration.
                    break
                in_pre_body = False
                continue
            if in_pre_body:
                pre_body_nodes.append(child)
            else:
                post_body_nodes.append(child)

        # If we never left the pre-body, then all children are pre-body nodes and we
        # can treat the loop as having no iterations.
        if in_pre_body:
            return

        if len(pre_body_nodes) > 0 and len(post_body_nodes) > 0:
            # When both pre-body and post-body nodes are present, the logic above will
            # incorrectly assign pre-body nodes to post-body nodes.
            post_body_nodes = [
                x for x in post_body_nodes if x not in pre_body_nodes
            ]

        # For now we are only supporting no iterations, consistent iterations, and
        # and an inconsistent trailing iteration.
        # We want to assembly a list where each element is the list of nodes that
        # constitute an iteration.
        # If there are children, but no iterations, then we will just mark it as a
        # single iteration.
        # Once we have the list of iterations, we can determine the number of iterations
        # for the main iter block and record a trailing iter block if there is one.
        iter_blocks = []
        curr_iter_block = []
        in_pre_body = True
        for child in self.children:
            if not in_pre_body:
                if child.is_iter_node() or child in pre_body_nodes:
                    # An iteration has ended.
                    iter_blocks.append(curr_iter_block)
                    curr_iter_block = []
                    in_pre_body = True
            if child.is_iter_node():
                in_pre_body = False
            curr_iter_block.append(child)
        if len(curr_iter_block) > 0:
            iter_blocks.append(curr_iter_block)
        self.iter_block = iter_blocks[0]

        # if self.name == 264379:
        #    print()
        #    print()
        #    for i, iter_block in enumerate(iter_blocks):
        #        print(f"Iter block {i}")
        #        for node in iter_block:
        #            print(anytree.RenderTree(node))
        #            print(f"CF points: {node.get_cf_nodes()}")

        # Now we can determine the number of iterations. We need to compare iter blocks
        # by cf nodes.
        unique_iter_blocks = []
        for iter_block in iter_blocks:
            cf_nodes = []
            for node in iter_block:
                cf_nodes.extend(node.get_cf_nodes())
            # Deduplicate adjacent control flow nodes.
            cf_nodes = [
                x
                for i, x in enumerate(cf_nodes)
                if i == 0 or x != cf_nodes[i - 1]
            ]
            if cf_nodes not in unique_iter_blocks:
                unique_iter_blocks.append(cf_nodes)
        if self.name == 264379:
            print(f"Unique iter blocks: {unique_iter_blocks}")
        if len(unique_iter_blocks) == 1:
            # All iterations are consistent.
            self.iter_count = len(iter_blocks)
        else:
            # We have an inconsistent trailing iteration.
            self.iter_count = len(iter_blocks) - 1
            self.trailing_iter_block = iter_blocks[-1]
        if self.name == 264379:
            print()
            print(anytree.RenderTree(self.root))
            print()

    def get_cf_nodes(self):
        """Return a list of control flow nodes."""
        cf_nodes = [self.name]
        if len(self.children) == 0:
            return cf_nodes

        for child in self.iter_block:
            if self.name == 264379:
                print(f"Getting cf nodes for {child}")
            cf_nodes.extend(child.get_cf_nodes())
        if self.name == 264379:
            print()
        if self.trailing_iter_block is not None:
            for child in self.trailing_iter_block:
                cf_nodes.extend(child.get_cf_nodes())
        return cf_nodes

    def to_expr(self, known_exprs):
        """Returns a symbolic expression of the tree."""
        expr = None
        for child in self.iter_block:
            child_expr = child.to_expr(known_exprs)
            if child_expr is None:
                continue
            if expr is None:
                expr = child_expr
            else:
                expr += child_expr
        if self._loop_expr is not None:
            expr = sympy.Mul(self._loop_expr, expr)
        if self.trailing_iter_block is not None:
            for child in self.trailing_iter_block:
                child_expr = child.to_expr(known_exprs)
                if child_expr is None:
                    continue
                if expr is None:
                    expr = child_expr
                else:
                    expr += child_expr
        return expr


class CallNode(Node):
    def __init__(self, name, type_, sig, params, parent=None, children=None):
        super(CallNode, self).__init__(
            name, type_, parent, children, sig=sig, params=params
        )
        self._sig = sig
        self._params = params

    @property
    def sig(self):
        return self._sig

    @property
    def params(self):
        return self._params

    @staticmethod
    def from_trace(trace):
        if not Node.is_call_type(type_ := trace["type"]):
            raise ValueError(f"Type '{type_}' is not a CallNode type.")
        children = [Node.from_trace(child) for child in trace["children"]]
        return CallNode(
            name=trace["id"],
            type_=type_,
            sig=trace["sig"],
            params=trace["params"],
            children=children,
        )

    def get_cf_nodes(self):
        """Return a list of control flow nodes."""
        cf_nodes = [self.name] if self.is_cf_node() else []
        for child in self.children:
            cf_nodes.extend(child.get_cf_nodes())
        return cf_nodes

    def to_expr(self, known_exprs):
        """Returns a symbolic expression of the tree."""
        if self.type == "CallerExpr":
            if self.sig in known_exprs:
                expr = sympy.sympify(known_exprs[self.sig])
            else:
                expr = sympy.sympify(f"T_{self.name}")
        else:
            expr = sympy.sympify(f"C_{self.name}")
            for child in self.children:
                child_expr = child.to_expr(known_exprs)
                if child_expr is None:
                    continue
                expr += child_expr
        return expr
