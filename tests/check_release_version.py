# GPL License
"""Check that a release tag agrees with the version in the source.

This fork ships one build for every Blender series the manifest supports, so the tag
is a plain <major>.<minor>.<patch> owned by the fork rather than one encoding a Blender
release. __init__.CATS_VERSION and blender_manifest.toml carry the same three parts.

    python3 tests/check_release_version.py 1.0.0
"""

import ast
import io
import os
import re
import sys
import tomllib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def cats_version():
    tree = ast.parse(io.open(os.path.join(ROOT, "__init__.py"), encoding="utf-8").read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "CATS_VERSION":
            return ast.literal_eval(node.value)
    raise SystemExit("CATS_VERSION not found in __init__.py")


def parts(value):
    return tuple(int(piece) for piece in value.split("."))


def main(argv):
    if len(argv) != 2:
        raise SystemExit(f"usage: {argv[0]} <tag>")
    tag = argv[1].lstrip("v")

    if not re.fullmatch(r"\d+\.\d+\.\d+", tag):
        raise SystemExit(f"tag {tag!r} is not <major>.<minor>.<patch>")

    with open(os.path.join(ROOT, "blender_manifest.toml"), "rb") as handle:
        manifest = tomllib.load(handle)

    source = cats_version()
    problems = []

    if source != tag:
        problems.append(f"__init__.CATS_VERSION is {source}, the tag says {tag}")
    if manifest["version"] != tag:
        problems.append(f"manifest version is {manifest['version']}, the tag says {tag}")

    low, high = manifest["blender_version_min"], manifest["blender_version_max"]
    if parts(low) >= parts(high):
        problems.append(f"manifest supports Blender {low} up to {high}, an empty range")

    for problem in problems:
        print(f"  {problem}")
    if problems:
        return 1
    print(f"  tag {tag} agrees with CATS_VERSION and the manifest")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
