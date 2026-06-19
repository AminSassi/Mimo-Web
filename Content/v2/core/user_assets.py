"""
MiMo User Asset Preservation — Never delete user data on update/uninstall.
Defines where user assets live and protects them.
"""
import os
import sys
import json
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


USER_ASSET_DIRS = {
    "models": {
        "default": os.path.join(os.path.expanduser("~"), "MimoAuto", "models"),
        "description": "Downloaded AI models",
        "preserve_on_update": True,
        "preserve_on_uninstall": True,
        "ask_before_delete": True,
    },
    "projects": {
        "default": os.path.join(os.path.expanduser("~"), "Documents", "Mimo Projects"),
        "description": "User projects and code",
        "preserve_on_update": True,
        "preserve_on_uninstall": True,
        "ask_before_delete": True,
    },
    "settings": {
        "default": os.path.join(os.path.expanduser("~"), ".mimocode", "settings"),
        "description": "User preferences and configuration",
        "preserve_on_update": True,
        "preserve_on_uninstall": True,
        "ask_before_delete": True,
    },
    "logs": {
        "default": os.path.join(os.path.expanduser("~"), ".mimocode", "logs"),
        "description": "Application logs",
        "preserve_on_update": True,
        "preserve_on_uninstall": False,
        "ask_before_delete": False,
    },
    "sessions": {
        "default": os.path.join(os.path.expanduser("~"), ".local", "share", "mimocode", "sessions"),
        "description": "Chat session history",
        "preserve_on_update": True,
        "preserve_on_uninstall": True,
        "ask_before_delete": True,
    },
    "memory": {
        "default": os.path.join(os.path.expanduser("~"), ".local", "share", "mimocode", "memory"),
        "description": "AI memory and context",
        "preserve_on_update": True,
        "preserve_on_uninstall": True,
        "ask_before_delete": True,
    },
}


class UserAssetManager:
    def __init__(self, install_dir=None):
        self.install_dir = install_dir
        self.assets = {}
        for name, config in USER_ASSET_DIRS.items():
            self.assets[name] = {
                **config,
                "current_path": config["default"],
                "exists": os.path.exists(config["default"]),
            }

    def get_asset_info(self, name):
        return self.assets.get(name)

    def get_all_assets(self):
        return self.assets.copy()

    def get_protected_assets(self):
        return {k: v for k, v in self.assets.items() if v["preserve_on_update"]}

    def check_preservation(self, action="update"):
        preserved = []
        deleted = []
        needs_ask = []

        for name, info in self.assets.items():
            if not info["exists"]:
                continue

            if action == "update" and info["preserve_on_update"]:
                preserved.append(name)
            elif action == "uninstall":
                if info["preserve_on_uninstall"]:
                    preserved.append(name)
                else:
                    deleted.append(name)
                    if info["ask_before_delete"]:
                        needs_ask.append(name)

        return {
            "preserved": preserved,
            "deleted": deleted,
            "needs_ask": needs_ask,
        }

    def backup_asset(self, name, backup_dir):
        info = self.assets.get(name)
        if not info or not info["exists"]:
            return False

        src = info["current_path"]
        dst = os.path.join(backup_dir, name)
        try:
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
            return True
        except Exception:
            return False

    def restore_asset(self, name, backup_dir):
        info = self.assets.get(name)
        if not info:
            return False

        src = os.path.join(backup_dir, name)
        dst = info["current_path"]
        if not os.path.exists(src):
            return False

        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            return True
        except Exception:
            return False

    def get_disk_usage(self):
        usage = {}
        for name, info in self.assets.items():
            if info["exists"]:
                total = 0
                path = info["current_path"]
                if os.path.isdir(path):
                    for root, dirs, files in os.walk(path):
                        for f in files:
                            fp = os.path.join(root, f)
                            try:
                                total += os.path.getsize(fp)
                            except Exception:
                                pass
                elif os.path.isfile(path):
                    total = os.path.getsize(path)
                usage[name] = round(total / (1024**3), 2)
            else:
                usage[name] = 0
        return usage

    def to_dict(self):
        return {
            name: {
                "path": info["current_path"],
                "exists": info["exists"],
                "preserve_on_update": info["preserve_on_update"],
                "preserve_on_uninstall": info["preserve_on_uninstall"],
            }
            for name, info in self.assets.items()
        }
