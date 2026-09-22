# GPL License
"""Checks that need neither Blender nor the network.

    python3 tests/static_checks.py
"""

import ast
import os
import sys
import warnings

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKIP = {".git", "__pycache__", "extern_tools", ".github"}


def sources():
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for name in sorted(files):
            if name.endswith(".py"):
                yield os.path.join(root, name)


def relative(path):
    return os.path.relpath(path, ROOT)


def check_compiles():
    """Every file parses, and none of them warns."""
    errors = []
    for path in sources():
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", SyntaxWarning)
            try:
                compile(text, path, "exec")
            except SyntaxError as e:
                errors.append(f"{relative(path)}:{e.lineno}: {e.msg}")
        for warning in caught:
            errors.append(f"{relative(path)}:{warning.lineno}: {warning.message}")
    return errors


def check_manifest():
    """The manifest parses and its bounds line up with the version gate."""
    import tomllib
    errors = []
    with open(os.path.join(ROOT, "blender_manifest.toml"), "rb") as handle:
        manifest = tomllib.load(handle)

    if len(manifest["tagline"]) > 64:
        errors.append(f"blender_manifest.toml: tagline is {len(manifest['tagline'])} characters, 64 allowed")
    if not isinstance(manifest.get("permissions"), dict):
        errors.append("blender_manifest.toml: permissions must be a table with a reason per entry")

    with open(os.path.join(ROOT, "__init__.py"), encoding="utf-8") as handle:
        init = handle.read()
    tree = ast.parse(init)
    gate = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Attribute):
            if ast.unparse(node.left) == "bpy.app.version" and isinstance(node.comparators[0], ast.Tuple):
                gate.append(tuple(ast.literal_eval(node.comparators[0])))
    lo = tuple(int(p) for p in manifest["blender_version_min"].split("."))[:2]
    hi = tuple(int(p) for p in manifest["blender_version_max"].split("."))[:2]
    if lo not in gate:
        errors.append(f"__init__.py does not gate on the manifest minimum {lo}")
    if hi not in gate:
        errors.append(f"__init__.py does not gate on the manifest maximum {hi}")
    return errors


def in_ci():
    return os.environ.get("CI", "").strip().lower() in {"1", "true", "yes"}


def check_ruff():
    """ruff, the version pinned in tests/requirements.txt, expected to report nothing."""
    import importlib.util
    import subprocess

    if importlib.util.find_spec("ruff") is None:
        if in_ci():
            return ["ruff is not installed, and CI must not skip the lint check"]
        print("  ruff not installed for this Python, skipping the lint check")
        return []

    proc = subprocess.run([sys.executable, "-m", "ruff", "check", "--no-cache", "--quiet",
                           "--output-format", "concise", ROOT],
                          capture_output=True, text=True, cwd=ROOT)
    if proc.returncode == 0:
        return []
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return lines or [proc.stderr.strip() or f"ruff exited {proc.returncode}"]


def main():
    failed = 0
    for label, check in (("syntax and warnings", check_compiles),
                         ("manifest", check_manifest),
                         ("ruff", check_ruff)):
        problems = check()
        status = "ok" if not problems else f"{len(problems)} problem(s)"
        print(f"  {label:22s} {status}")
        for problem in problems:
            print(f"      {problem}")
        failed += len(problems)
    if failed:
        print(f"\n{failed} problem(s) found.")
        return 1
    print("\nStatic checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
