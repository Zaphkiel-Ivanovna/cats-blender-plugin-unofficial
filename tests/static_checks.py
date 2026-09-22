# GPL License
"""Checks that need neither Blender nor the network.

    python3 tests/static_checks.py
"""

import ast
import io
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
        with io.open(path, encoding="utf-8") as handle:
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


def check_undefined_names():
    """pyflakes, narrowed to undefined names.

    Its other reports are mostly pre-existing unused imports, several of which are
    load-bearing because @register_wrap registers classes at import time.
    """
    try:
        from pyflakes import api, reporter
    except ImportError:
        print("  pyflakes not installed, skipping the undefined-name check")
        return []

    class Collect(reporter.Reporter):
        def __init__(self):
            super().__init__(io.StringIO(), io.StringIO())
            self.found = []

        def flake(self, message):
            if type(message).__name__ == "UndefinedName":
                self.found.append(f"{relative(message.filename)}:{message.lineno}: {message.message % message.message_args}")

        def unexpectedError(self, filename, msg):
            self.found.append(f"{relative(filename)}: {msg}")

    collected = Collect()
    for path in sources():
        api.checkPath(path, collected)
    # bpy.props annotations hold string literals that pyflakes reads as forward
    # references, so Scene.* and similar names are reported and are not real.
    return [f for f in collected.found
            if not any(f.endswith(f"undefined name '{n}'")
                       for n in ("Scene", "shapekeys", "HIDDEN", "PMX", "BLENDER", "Blender", "RENAMED_BONES"))]


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

    with io.open(os.path.join(ROOT, "__init__.py"), encoding="utf-8") as handle:
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


def main():
    failed = 0
    for label, check in (("syntax and warnings", check_compiles),
                         ("undefined names", check_undefined_names),
                         ("manifest", check_manifest)):
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
