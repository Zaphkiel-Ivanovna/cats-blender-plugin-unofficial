# GPL License
"""Headless test runner for CATS on Blender 5.x.

Installs the working tree as an extension into a throwaway user-resources
directory, then runs each case file inside Blender. Nothing touches the real
Blender configuration.

    python3 tests/headless/run.py [--blender /path/to/blender] [--case NAME]
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CASES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cases")
PACKAGE = "bl_ext.user_default.cats_blender_plugin"
SKIP = {".git", "__pycache__", ".idea", "tests"}


def install(root):
    target = os.path.join(root, "extensions", "user_default", "cats_blender_plugin")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    shutil.copytree(REPO, target, ignore=shutil.ignore_patterns(*SKIP))
    return target


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blender", default=os.environ.get("BLENDER", "blender"))
    ap.add_argument("--case", default=None, help="run only cases whose name contains this")
    args = ap.parse_args()

    if not shutil.which(args.blender) and not os.path.exists(args.blender):
        print(f"blender not found: {args.blender}", file=sys.stderr)
        return 2

    cases = sorted(f for f in os.listdir(CASES) if f.startswith("test_") and f.endswith(".py"))
    if args.case:
        cases = [c for c in cases if args.case in c]
    if not cases:
        print("no cases to run", file=sys.stderr)
        return 2

    root = tempfile.mkdtemp(prefix="cats-tests-")
    try:
        install(root)
        env = dict(os.environ, BLENDER_USER_RESOURCES=root, CATS_TEST_PACKAGE=PACKAGE)
        failed = []
        for case in cases:
            print(f"\n=== {case} ===", flush=True)
            proc = subprocess.run(
                [args.blender, "--background", "--factory-startup",
                 "--python-exit-code", "1",
                 "--python", os.path.join(CASES, case)],
                env=env, capture_output=True, text=True)
            body = proc.stdout
            for line in body.splitlines():
                if line.startswith(("  [", "FAIL", "PASS")):
                    print(line)
            if proc.returncode != 0:
                failed.append(case)
                print(proc.stdout[-3000:])
                print(proc.stderr[-3000:], file=sys.stderr)
        print()
        if failed:
            print(f"FAILED: {', '.join(failed)}")
            return 1
        print(f"All {len(cases)} case file(s) passed.")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
