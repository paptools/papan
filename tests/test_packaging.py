import subprocess


def test_paptrace_attrs(tmp_path):
    script_path = tmp_path / "script.py"
    script_path.write_text("""
import paptrace

# Node classes are attributes of the paptrace.
assert hasattr(paptrace, 'Node')
assert hasattr(paptrace, 'StmtNode')
assert hasattr(paptrace, 'CallNode')

# The utils module is also an attribute of the paptrace.
assert hasattr(paptrace, 'utils')
""")
    proc = subprocess.run(["python", str(script_path)])
    assert proc.returncode == 0
