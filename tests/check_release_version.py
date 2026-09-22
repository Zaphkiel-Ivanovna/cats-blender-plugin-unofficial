# GPL License
"""Check that a release tag agrees with the version in the source.

Releases are tagged <blender major>.<blender minor>.<cats major>.<cats minor>, so
5.0.3.1 is the CATS 3.1 build for Blender 5.0. __init__.CATS_VERSION carries the
same four parts, and blender_manifest.toml carries the first three.

    python3 tests/check_release_version.py 5.0.3.1
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


def main(argv):
    if len(argv) != 2:
        raise SystemExit(f"usage: {argv[0]} <tag>")
    tag = argv[1].lstrip("v")

    if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", tag):
        raise SystemExit(f"tag {tag!r} is not <blender major>.<blender minor>.<cats major>.<cats minor>")

    with open(os.path.join(ROOT, "blender_manifest.toml"), "rb") as handle:
        manifest = tomllib.load(handle)

    source = cats_version()
    expected_manifest = ".".join(tag.split(".")[:3])
    problems = []

    if source != tag:
        problems.append(f"__init__.CATS_VERSION is {source}, the tag says {tag}")
    if manifest["version"] != expected_manifest:
        problems.append(f"manifest version is {manifest['version']}, the tag implies {expected_manifest}")

    series = ".".join(tag.split(".")[:2])
    low = ".".join(manifest["blender_version_min"].split(".")[:2])
    high = ".".join(manifest["blender_version_max"].split(".")[:2])
    if not (low <= series < high):
        problems.append(f"tag targets Blender {series}, the manifest supports {low} up to but not including {high}")

    for problem in problems:
        print(f"  {problem}")
    if problems:
        return 1
    print(f"  tag {tag} agrees with CATS_VERSION and the manifest")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
