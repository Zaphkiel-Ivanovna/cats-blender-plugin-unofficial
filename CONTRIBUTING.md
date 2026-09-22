# Contributing

## Before you start

This fork exists to keep Cats working on Blender 5.x. If a bug is not specific to 5.x,
it belongs [upstream](https://github.com/teamneoneko/Cats-Blender-Plugin-Unofficial-),
where more people will see it.

## Running it

Install the working tree as an extension, or build a zip:

```sh
blender --command extension build --source-dir . --output-dir dist
```

Then **Edit > Preferences > Get Extensions**, the dropdown at the top right,
**Install from Disk**.

## Running the tests

```sh
pip install -r tests/requirements.txt
python3 tests/static_checks.py
python3 tests/headless/run.py --blender /path/to/blender
python3 tests/headless/run.py --case mesh       # one case file
```

The headless suite installs the tree into a throwaway directory, so your own Blender
configuration is untouched. CI runs both against Blender 5.0, 5.1 and 5.2.

`static_checks.py` includes ruff, configured in `ruff.toml` and expected to report
nothing. `ruff check --fix .` handles most of what it raises, except unused imports,
which it reports and leaves alone: some of them register classes at import time, so
deciding whether one can go is yours. The rules it leaves out are
either Blender idioms or style that would only churn inherited code, and each one is
there on purpose, so a new exclusion needs a reason in the pull request.

## What a good change looks like

**Say what you measured.** Cats edits people's avatars, so "this is faster" or "this is
cleaner" is not enough on its own. Time it, count the operator calls, compare the output
mesh. The commit history has examples.

**Check the output did not move.** For anything touching Fix Model or the mesh helpers,
run it on a real model before and after and compare what comes out: vertex and face
counts, shape key names, vertex groups, material names. Sorted hashes of the coordinate
and UV arrays work well, because Fix Model is not deterministic about raw vertex order.

**Add a case when you fix a bug.** `tests/headless/cases/` has the pattern, and
`_models.py` builds synthetic armatures for Fix Model. A case that fails before your fix
and passes after is worth more than a paragraph in the PR.

**No comments.** The tree carries license headers and docstrings, nothing else. That is
deliberate; keep it that way.

## Style

Match the file you are editing. The codebase is old and inconsistent, and a reformatting
pass mixed into a bug fix makes the fix impossible to review.

Two things worth knowing, both learned the hard way in this tree:

- An import that looks unused may not be. `@register_wrap` registers classes at import
  time, so removing a module import can silently unregister operators. It can also
  change import order and expose a circular import.
- `bpy.ops` in a loop is slow in a way that adds up. Each call re-resolves context, pushes
  an undo step and tags the depsgraph. Reach for `foreach_get` and `foreach_set` over
  per-element RNA access.

## Commits

Conventional commits with a gitmoji, in English, and a body that says what was measured:

```
⚡️ perf(mesh): read shape keys and UVs in bulk instead of per element
```
