# GPL License
"""Shared helpers for the in-Blender test cases."""

import os
import sys
import importlib

import bpy

PACKAGE = os.environ.get("CATS_TEST_PACKAGE", "bl_ext.user_default.cats_blender_plugin")
_failures = []


def enable():
    bpy.ops.preferences.addon_enable(module=PACKAGE)
    return importlib.import_module(PACKAGE)


def module(name):
    return importlib.import_module(f"{PACKAGE}.{name}")


def _short(value, limit=90):
    text = repr(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... ({len(value)} items)" if hasattr(value, "__len__") else text[:limit] + "..."


def check(label, got, want):
    ok = got == want
    if not ok:
        _failures.append(label)
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label}: {_short(got)}" + ("" if ok else f" != {_short(want)}"))
    return ok


def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)


def done():
    if _failures:
        print("FAIL: " + ", ".join(_failures))
        sys.exit(1)
    print("PASS")
    sys.exit(0)
