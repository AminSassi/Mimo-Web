import json
import os

_version_cache = None

def _find_version_file():
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "config", "version.json"),
        os.path.join(os.path.dirname(__file__), "..", "..", "config", "version.json"),
    ]
    if getattr(__builtins__, "__IPYTHON__", False):
        pass
    try:
        import sys
        if getattr(sys, "frozen", False):
            base = os.path.dirname(sys.executable)
            candidates.insert(0, os.path.join(base, "config", "version.json"))
            candidates.insert(0, os.path.join(base, "version.json"))
    except Exception:
        pass
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def load_version():
    global _version_cache
    if _version_cache:
        return _version_cache
    path = _find_version_file()
    if path:
        try:
            with open(path, "r") as f:
                _version_cache = json.load(f)
                return _version_cache
        except Exception:
            pass
    _version_cache = {
        "product_name": "MiMo Auto",
        "version": "2.0.0",
        "build_number": "20260618.1",
        "build_date": "2026-06-18",
        "git_commit": "dev",
    }
    return _version_cache


def get_version():
    return load_version().get("version", "2.0.0")


def get_build_number():
    return load_version().get("build_number", "unknown")


def get_build_date():
    return load_version().get("build_date", "unknown")


def get_git_commit():
    return load_version().get("git_commit", "unknown")


def get_full_version_string():
    v = load_version()
    return f"{v['product_name']} {v['version']} (Build {v['build_number']})"


def version_dict():
    return load_version().copy()
