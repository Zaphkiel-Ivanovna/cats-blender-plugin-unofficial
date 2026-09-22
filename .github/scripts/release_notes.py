"""Release notes for one tag: the Blender range it supports, then its commits grouped by type.

    python3 .github/scripts/release_notes.py 1.0.1 [owner/repo]
"""

import os
import re
import subprocess
import sys
import tomllib

SECTIONS = (("feat", "Features"), ("perf", "Performance"), ("fix", "Fixes"))
MAINTENANCE = "Maintenance"
INTERNAL_SCOPES = {"release", "ci", "lint", "deps", "tests"}
TAG_PATTERN = "[0-9]*.[0-9]*.[0-9]*"
SUBJECT = re.compile(r"^(?:\S+\s+)?(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?!?:\s*(?P<text>.+)$")


def git(*args, cwd=None):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True, cwd=cwd).stdout.strip()


def previous_tag(tag, cwd=None):
    try:
        return git("describe", "--tags", "--abbrev=0", "--match", TAG_PATTERN, f"{tag}^", cwd=cwd)
    except subprocess.CalledProcessError:
        return None


def supported_blender(manifest_path):
    with open(manifest_path, "rb") as handle:
        manifest = tomllib.load(handle)

    def parts(value):
        return tuple(int(piece) for piece in value.split("."))

    low, high = parts(manifest["blender_version_min"]), parts(manifest["blender_version_max"])
    names = [f"{low[0]}.{minor}" for minor in range(low[1], high[1])] if low[0] == high[0] else []
    if not names:
        return f"{low[0]}.{low[1]} or newer, below {high[0]}.{high[1]}"
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def classify(subject):
    match = SUBJECT.match(subject)
    if not match:
        return MAINTENANCE, None, subject
    kind, scope, text = match.group("type"), match.group("scope"), match.group("text")
    if kind == "chore" and scope == "release":
        return None, None, None
    text = text[0].upper() + text[1:]
    if scope in INTERNAL_SCOPES:
        return MAINTENANCE, scope, text
    section = dict(SECTIONS).get(kind, MAINTENANCE)
    return section, scope, text


def changes(previous, tag, cwd=None):
    log = git("log", "--no-merges", "--format=%h%x00%s", f"{previous}..{tag}", cwd=cwd)
    grouped = {}
    for line in filter(None, log.split("\n")):
        sha, subject = line.split("\x00", 1)
        section, scope, text = classify(subject)
        if section:
            label = f"**{scope}:** {text}" if scope else text
            grouped.setdefault(section, []).append(f"- {label} ({sha})")
    return grouped


def render(tag, repo=None, cwd=None):
    lines = [
        f"Works with Blender {supported_blender(os.path.join(cwd or '.', 'blender_manifest.toml'))}.",
        "",
        ("Install through **Edit > Preferences > Get Extensions**, the dropdown at the top right, "
         "then **Install from Disk**."),
    ]
    previous = previous_tag(tag, cwd=cwd)
    if previous is None:
        lines += ["", "First release."]
        return "\n".join(lines) + "\n"

    grouped = changes(previous, tag, cwd=cwd)
    for _, title in (*SECTIONS, (None, MAINTENANCE)):
        if grouped.get(title):
            lines += ["", f"## {title}", "", *reversed(grouped[title])]
    if repo:
        lines += ["", f"**Full changelog:** https://github.com/{repo}/compare/{previous}...{tag}"]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit(f"usage: {sys.argv[0]} <tag> [owner/repo]")
    repo = sys.argv[2] if len(sys.argv) == 3 else os.environ.get("GITHUB_REPOSITORY")
    sys.stdout.write(render(sys.argv[1], repo))
