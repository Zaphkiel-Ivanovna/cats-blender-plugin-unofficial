## What this changes

<!-- What the code does differently now. If it fixes an issue, link it. -->

## Why

<!-- The problem this solves. A traceback, a model that breaks, a measurement. -->

## How it was checked

<!--
Say what you actually ran, not what you believe. Both suites live in tests/:

    python3 tests/static_checks.py
    python3 tests/headless/run.py --blender /path/to/blender

If it touches Fix Model or the mesh helpers, say which model you ran it on and what
came out. Numbers beat adjectives.
-->

- [ ] `tests/static_checks.py` passes
- [ ] `tests/headless/run.py` passes on Blender 5.0, 5.1 and 5.2
- [ ] Ran it on a real model, and the result is what it was before the change

## Notes for the reviewer

<!-- Anything you are unsure about, a decision you made, something you left out. -->
