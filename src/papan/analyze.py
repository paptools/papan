import json

import anytree
import sympy
import numpy as np

from .node import Node
from .utils import from_file
from .regression import gplearn_symreg, deap_symreg


def to_params_str(params):
    # return ", ".join([f"{param['name']}={param['value']}" for param in params])
    return ", ".join([f"{param['value']}" for param in params])


def to_call_str(node):
    return f"{node.sig}: ({to_params_str(node.params)})"


def link_recursive_nodes(trees):
    # Let's start by putting our trace root nodes in a container that allows us
    # to lookup the trace by context.
    # NOTE: This does not account for complete non-root traces (e.g., RecursiveMemoImpl).
    trace_roots = {}
    for tree in trees:
        call_str = to_call_str(tree.root)
        if call_str not in trace_roots:
            trace_roots[call_str] = tree.root
        else:
            if tree.root != trace_roots[call_str]:
                raise RuntimeError(
                    "Unhandled scenario: 2 traces with the same context have"
                    " differing trees."
                )

    # Next we walk the trees looking for child nodes that can be substituted with a
    # trace root node.
    for tree in trees:
        for node in anytree.PreOrderIter(tree.root):
            if node.is_root:
                continue
            replace_children = False
            new_children = []
            for child in node.children:
                if child.type == "CalleeExpr":
                    child_call_str = to_call_str(child)
                    if child_call_str in trace_roots:
                        replace_children = True
                        child = anytree.SymlinkNode(child)
                new_children.append(child)
            if replace_children:
                node.children = tuple(new_children)


def get_path_partitions(trees):
    # Schema: {sig: {cf_tuple: {path_id: int, traces: [tree]}}}
    path_dict = {}
    for tree in trees:
        sig_paths = path_dict.setdefault(tree.root.sig, {})
        cf_tuple = tuple(tree.get_cf_nodes())
        sig_paths.setdefault(
            cf_tuple, {"path_id": len(sig_paths), "traces": []}
        )["traces"].append(tree)
    return path_dict


def is_constant(exprs):
    """Returns True if all expressions are equal."""
    return len(set(exprs)) == 1


def find_repr_exprs(path_dict, known):
    # We will want to query the results with a tuple of (signature, ctx). To do
    # this we will need to map the ctx for a signature to the correct path ID.
    # Therefore, the results will need to contain two sections:
    # 1. A mapping from (signature) to sig_id.
    # 2. A mapping from (sig_id, ctx) to path_id.
    # 3. A mapping from (sig_id, path_id) to the path expression.
    results = {"sigs": {}, "ctxs": {}, "exprs": {}}

    def add_result(sig, path_id, expr, trees):
        print(f"  Found expr.: {expr}")
        sig_id = results["sigs"].setdefault(sig, f"sig_{len(results['sigs'])}")
        path_id_str = f"path_{path_id}"
        results["exprs"].setdefault(sig_id, {})[path_id_str] = str(expr)
        result_ctxs = results["ctxs"].setdefault(sig_id, {})
        for tree in trees:
            result_ctxs[to_params_str(tree.root.params)] = path_id_str

    for sig, sig_entry in path_dict.items():
        for cf_tuple, path_entry in sig_entry.items():
            path_id = path_entry["path_id"]
            trees = path_entry["traces"]
            print(f"\nFinding general expr. for: {sig}: ({path_id})")

            # Check if there are any loops in the trees. If the loop iter counts are
            # different, then we will need to solve for the loop expression.
            if trees[0].has_loop():
                ctxs = np.array(
                    [int(to_params_str(tree.root.params)) for tree in trees]
                )
                loop_nodes = [tree.get_loop_nodes() for tree in trees]
                ref_nodes = loop_nodes[0]
                found_variable_loop = False
                for i, ref_node in enumerate(ref_nodes):
                    if ref_node.iter_count == 0:
                        # This is a constant loop node. We can skip it.
                        continue

                    print(f"  Solving for loop expr for node: {ref_node.name}")
                    found_variable_loop = True
                    iter_cnts = np.zeros((len(loop_nodes),))
                    for j in range(0, len(loop_nodes)):
                        iter_cnts[j] = loop_nodes[j][i].iter_count

                    # Optimization: If the loop iter counts are the same, then we can
                    # just use values from the 0th entry.
                    loop_expr = None
                    if iter_cnts.ptp() == 0:
                        print(f"    Loop iteration is constant.")
                        loop_expr = sympy.sympify(iter_cnts[0])
                    else:
                        # Optimization: Check for complete linear dependence.
                        x = ctxs
                        y = iter_cnts
                        corr = np.corrcoef(ctxs, iter_cnts)
                        if corr.ptp() == 0 and corr[0, 1] == 1:
                            print(
                                f"    Loop iteration has perfect linear"
                                f" correlation."
                            )
                            m = (iter_cnts[1] - iter_cnts[0]) / (
                                ctxs[1] - ctxs[0]
                            )
                            b = iter_cnts[0] - m * ctxs[0]
                            loop_expr = sympy.sympify(f"{m} * X0 + {b}")
                        else:
                            print(f"    Performing symbolic regression.")
                            # We need to regress for the relationship.
                            # loop_expr = gplearn_symreg(data)
                            loop_expr = deap_symreg(x, y)

                    if loop_expr is None:
                        raise RuntimeError("Failed to find loop expression.")
                    ref_node.set_loop_expr(loop_expr)

                if found_variable_loop:
                    add_result(sig, path_id, trees[0].to_expr(known), trees)
                    continue

            # Get the expressions for each trace.
            exprs = [tree.to_expr(known) for tree in trees]

            if is_constant(exprs):
                print("  Path is constant.")
                add_result(sig, path_id, exprs[0], trees)
                continue

            print("  No general expr. found for exprs:")
            for expr in exprs:
                print(f"    {expr}")

    return results


def analyze(known, trees):
    link_recursive_nodes(trees)

    path_dict = get_path_partitions(trees)
    print("Path summary:")
    for sig, sig_entry in path_dict.items():
        print(f"- {sig}: {len(sig_entry)} paths")
        for cf_tuple, path_entry in sig_entry.items():
            print(
                f"  - [path_{path_entry['path_id']}] {cf_tuple}:"
                f" {len(path_entry['traces'])} traces"
            )

    results = find_repr_exprs(path_dict, known)
    return results
    print("\nResults:")
    print(json.dumps(results, indent=4))
    with open(args.output_file, "w") as f_out:
        f_out.write(json.dumps(results, indent=2))
