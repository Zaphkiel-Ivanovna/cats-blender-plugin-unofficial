# GPL License
"""Check the release notes generator against a throwaway repository.

    python3 tests/check_release_notes.py
"""

import importlib.util
import os
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
spec = importlib.util.spec_from_file_location("release_notes", os.path.join(ROOT, ".github", "scripts", "release_notes.py"))
notes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notes)

MANIFEST = 'blender_version_min = "5.0.0"\nblender_version_max = "5.3.0"\n'
failures = []


def check(label, condition):
    print(f"  [{'OK  ' if condition else 'FAIL'}] {label}")
    if not condition:
        failures.append(label)


def git(repo, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True)


def commit(repo, subject):
    git(repo, "commit", "--allow-empty", "-m", subject)


with tempfile.TemporaryDirectory() as repo:
    git(repo, "init", "-q", "-b", "main")
    with open(os.path.join(repo, "blender_manifest.toml"), "w") as handle:
        handle.write(MANIFEST)
    git(repo, "add", ".")
    commit(repo, "🎉 chore: start")
    git(repo, "tag", "1.0.0")

    first = notes.render("1.0.0", "o/r", cwd=repo)
    check("the first release says so instead of listing history", "First release." in first)
    check("the supported range comes from the manifest", "Works with Blender 5.0, 5.1 and 5.2." in first)
    check("the first release has no compare link", "compare" not in first)

    for subject in ("🐛 fix(merge): keep main-bone groups",
                    "✨ feat(ui): add a panel",
                    "⚡️ perf: faster joins",
                    "fix!: breaking repair without an emoji",
                    "🐛 fix(release): internal pipeline fix",
                    "🔧 build: pin a tool",
                    "an old subject with no convention",
                    "🔖 chore(release): 1.1.0"):
        commit(repo, subject)
    git(repo, "tag", "1.1.0")
    text = notes.render("1.1.0", "o/r", cwd=repo)
    print(text)

    order = [text.find(f"## {s}") for s in ("Features", "Performance", "Fixes", "Maintenance")]
    check("sections appear in order", all(i >= 0 for i in order) and order == sorted(order))
    check("scope is shown in bold", "- **merge:** Keep main-bone groups (" in text)
    check("no emoji leaks into the text", "🐛" not in text and "✨" not in text)
    check("a subject without an emoji still parses", "- Breaking repair without an emoji (" in text)
    fixes = text.split("## Fixes")[1].split("##")[0]
    maintenance = text.split("## Maintenance")[1]
    check("an internal scope goes to maintenance, not fixes",
          "Internal pipeline fix" in maintenance and "Internal pipeline fix" not in fixes)
    check("a subject outside the convention lands in maintenance", "An old subject" not in text
          and "an old subject with no convention" in maintenance)
    check("the release commit itself is left out", "1.1.0 (" not in text)
    check("entries are oldest first",
          fixes.index("Keep main-bone groups") < fixes.index("Breaking repair"))
    check("the compare link spans the two tags", "https://github.com/o/r/compare/1.0.0...1.1.0" in text)

if failures:
    print(f"\n{len(failures)} failure(s).")
    sys.exit(1)
print("\nRelease notes checks passed.")
