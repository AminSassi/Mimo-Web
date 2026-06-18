"""
MiMo Rollback Handlers — Every action has an inverse.
No install action may exist without a rollback action.
"""
import os
import sys
import json
import shutil
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class RollbackRegistry:
    """Registry of all install actions and their inverse rollback actions."""

    def __init__(self, logger=None):
        self.log = logger
        self._handlers = {}
        self._register_defaults()

    def _register_defaults(self):
        self.register("create_install_dir", self._rollback_create_dir)
        self.register("delete_install_dir", self._rollback_delete_dir)
        self.register("install_node", self._rollback_uninstall_node)
        self.register("install_git", self._rollback_uninstall_git)
        self.register("add_path_entry", self._rollback_restore_path)
        self.register("create_shortcuts", self._rollback_remove_shortcuts)
        self.register("write_registry_keys", self._rollback_restore_registry)
        self.register("create_state_file", self._rollback_restore_state)
        self.register("create_portable_flag", self._rollback_remove_portable_flag)
        self.register("install_mimo", self._rollback_uninstall_mimo)

    def register(self, action_name, handler):
        self._handlers[action_name] = handler

    def get_rollback(self, action_name):
        return self._handlers.get(action_name)

    def has_rollback(self, action_name):
        return action_name in self._handlers

    def execute_rollback(self, action_name, context):
        handler = self._handlers.get(action_name)
        if not handler:
            if self.log:
                self.log.error(f"No rollback handler for: {action_name}")
            return False
        try:
            result = handler(context)
            if self.log:
                self.log.info(f"Rollback executed: {action_name}",
                              event="rollback_executed", step=action_name)
            return result
        except Exception as e:
            if self.log:
                self.log.error(f"Rollback failed: {action_name} — {e}",
                               event="rollback_failed", step=action_name, error=str(e))
            return False

    def verify_all_actions_have_rollback(self):
        """Build-time check: fail if any action lacks a rollback handler."""
        install_actions = [
            "create_install_dir", "install_node", "install_git",
            "add_path_entry", "create_shortcuts", "write_registry_keys",
            "create_state_file", "create_portable_flag", "install_mimo",
        ]
        missing = [a for a in install_actions if not self.has_rollback(a)]
        return missing

    def _rollback_create_dir(self, ctx):
        install_dir = ctx.get("install_dir", "")
        if install_dir and os.path.exists(install_dir):
            try:
                shutil.rmtree(install_dir)
                return True
            except Exception:
                return False
        return True

    def _rollback_delete_dir(self, ctx):
        install_dir = ctx.get("install_dir", "")
        backup = ctx.get("backup_path", "")
        if backup and os.path.exists(backup):
            shutil.copytree(backup, install_dir)
            return True
        return True

    def _rollback_uninstall_node(self, ctx):
        node_msi = ctx.get("node_msi_path", "")
        if node_msi and os.path.exists(node_msi):
            try:
                subprocess.run(
                    ["msiexec", "/x", node_msi, "/quiet", "/norestart"],
                    capture_output=True, timeout=120,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
            except Exception:
                pass
        path_dirs = ctx.get("node_path_dirs", [])
        self._remove_from_path(path_dirs)
        return True

    def _rollback_uninstall_git(self, ctx):
        git_exe = ctx.get("git_exe_path", "")
        if git_exe:
            uninstaller = os.path.join(os.path.dirname(git_exe), "..", "unins000.exe")
            if os.path.exists(uninstaller):
                try:
                    subprocess.run(
                        [uninstaller, "/VERYSILENT", "/NORESTART"],
                        capture_output=True, timeout=120,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    )
                except Exception:
                    pass
        path_dirs = ctx.get("git_path_dirs", [])
        self._remove_from_path(path_dirs)
        return True

    def _rollback_restore_path(self, ctx):
        original_path = ctx.get("original_path", "")
        if not original_path:
            return True
        try:
            subprocess.run(
                ["reg", "add",
                 "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
                 "/v", "Path", "/t", "REG_EXPAND_SZ",
                 "/d", original_path, "/f"],
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            os.environ["PATH"] = original_path
            return True
        except Exception:
            return False

    def _rollback_remove_shortcuts(self, ctx):
        shortcuts = ctx.get("shortcuts_created", [])
        for shortcut in shortcuts:
            try:
                if os.path.exists(shortcut):
                    os.remove(shortcut)
            except Exception:
                pass
        return True

    def _rollback_restore_registry(self, ctx):
        backups = ctx.get("registry_backups", {})
        for (hive, key, value_name), original_value in backups.items():
            try:
                if original_value is None:
                    subprocess.run(
                        ["reg", "delete", f"{hive}\\{key}", "/v", value_name, "/f"],
                        capture_output=True,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    )
                else:
                    subprocess.run(
                        ["reg", "add", f"{hive}\\{key}", "/v", value_name,
                         "/t", "REG_EXPAND_SZ", "/d", original_value, "/f"],
                        capture_output=True,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    )
            except Exception:
                pass
        return True

    def _rollback_restore_state(self, ctx):
        state_path = ctx.get("state_path", "")
        backup = ctx.get("state_backup_path", "")
        if backup and os.path.exists(backup):
            shutil.copy2(backup, state_path)
            return True
        elif state_path and os.path.exists(state_path):
            os.remove(state_path)
            return True
        return True

    def _rollback_remove_portable_flag(self, ctx):
        flag_path = ctx.get("portable_flag_path", "")
        if flag_path and os.path.exists(flag_path):
            os.remove(flag_path)
        return True

    def _rollback_uninstall_mimo(self, ctx):
        npm_ok, _, _ = _run_cmd(["npm", "uninstall", "-g", "@mimo-ai/cli"], timeout=60)
        return True

    def _remove_from_path(self, dirs):
        try:
            result = subprocess.run(
                ["reg", "query",
                 "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
                 "/v", "Path"],
                capture_output=True, text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            current_path = ""
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "Path" in line and "REG_" in line:
                        parts = line.split("REG_EXPAND_SZ")
                        if len(parts) == 2:
                            current_path = parts[1].strip()
                            break
            if not current_path:
                return
            parts = current_path.split(";")
            new_parts = [p for p in parts if p not in dirs]
            new_path = ";".join(new_parts)
            subprocess.run(
                ["reg", "add",
                 "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
                 "/v", "Path", "/t", "REG_EXPAND_SZ",
                 "/d", new_path, "/f"],
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            os.environ["PATH"] = new_path
        except Exception:
            pass


def _run_cmd(cmd, timeout=30):
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception:
        return False, "", ""
