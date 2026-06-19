"""
MiMo Bootstrapper v2.1 — The Brain
Uses shared core module for logging, version, and paths.
"""
import os
import sys
import json
import shutil
import subprocess
import hashlib
import time
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core import (
    MiMoLogger, get_version, get_log_dir, get_state_path,
    get_transaction_path, ensure_dirs, is_portable,
    STATE_FILE, TRANSACTION_FILE, PORTABLE_FLAG
)

DEFAULT_INSTALL_DIR = os.path.join(os.path.expanduser("~"), "MiMo Auto")

DEPENDENCIES = {
    "node": {
        "name": "Node.js LTS",
        "check_cmd": ["node", "--version"],
        "download": "https://nodejs.org/dist/v20.15.1/node-v20.15.1-x64.msi",
        "installer_args": ["/quiet", "/norestart"],
        "path_dirs": [
            os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "nodejs"),
            os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "Nodejs"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "nodejs"),
        ],
        "verify_cmd": ["node", "--version"],
        "exe_names": ["node.exe", "node"],
        "size_mb": 32,
    },
    "npm": {
        "name": "npm",
        "check_cmd": ["npm", "--version"],
        "download": None,
        "path_dirs": [],
        "verify_cmd": ["npm", "--version"],
        "exe_names": ["npm.cmd", "npm.exe", "npm"],
        "size_mb": 0,
    },
    "git": {
        "name": "Git",
        "check_cmd": ["git", "--version"],
        "download": "https://github.com/git-for-windows/git/releases/download/v2.45.2.windows.1/Git-2.45.2-64-bit.exe",
        "installer_args": ["/VERYSILENT", "/NORESTART", "/NOCANCEL"],
        "path_dirs": [
            os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "Git", "cmd"),
            os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "Git", "bin"),
        ],
        "verify_cmd": ["git", "--version"],
        "exe_names": ["git.exe", "git"],
        "size_mb": 55,
    },
}

DEP_HASHES = {
    "node": {"20.15.1": "b139ba1b82807918af40fbed49a5b529f67ba198e87bcabdac907b734ff83ab5"},
    "git": {"2.45.2": "ce022a6a19e58bbbd4823f51cf798b006b4a683b93b0616a7bb5beeee901da98"},
}

MAX_REPAIR_ATTEMPTS = 3


STATE_SCHEMA_VERSION = 1


def _migrate_0_to_1(state):
    state["install_result"] = state.get("install_result", "pending")
    state["last_install_time"] = state.get("last_install_time")
    if "deps" in state:
        for key in ["node", "npm", "git"]:
            if key in state["deps"]:
                old = state["deps"][key]
                if isinstance(old, dict):
                    status = old.get("status", "unknown")
                    if status in ("ok", "installed"):
                        old["status"] = "installed"
                    elif status == "missing":
                        old["status"] = "not_installed"
                    else:
                        old["status"] = status
    if "mimo" in state and isinstance(state["mimo"], dict):
        status = state["mimo"].get("status", "unknown")
        if status in ("ok", "installed"):
            state["mimo"]["status"] = "installed"
        elif status == "missing":
            state["mimo"]["status"] = "not_installed"
    state["schema_version"] = 1
    return state


MIGRATIONS = {
    0: _migrate_0_to_1,
}


def _migrate_state(state):
    current = state.get("schema_version", 0)
    if current > STATE_SCHEMA_VERSION:
        return state, False, "newer"
    if current == STATE_SCHEMA_VERSION:
        return state, False, "current"
    if current in MIGRATIONS:
        state = MIGRATIONS[current](state)
    state["schema_version"] = STATE_SCHEMA_VERSION
    return state, True, "migrated"


class StateManager:
    def __init__(self, install_dir):
        self.install_dir = install_dir
        self.state_path = get_state_path(install_dir)
        self.state = self._load()

    def _load(self):
        default = {
            "version": get_version(),
            "install_dir": self.install_dir,
            "installed_at": None,
            "install_result": "pending",
            "last_health_check": None,
            "last_health_result": "unknown",
            "last_install_time": None,
            "deps": {
                "node": {"status": "not_installed", "version": ""},
                "npm": {"status": "not_installed", "version": ""},
                "git": {"status": "not_installed", "version": ""},
            },
            "mimo": {"status": "not_installed", "version": ""},
            "portable": os.path.exists(os.path.join(self.install_dir, PORTABLE_FLAG)),
            "launches": 0,
            "repairs": 0,
            "repair_attempts": 0,
            "last_repair": None,
            "max_repairs": MAX_REPAIR_ATTEMPTS,
        }
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r") as f:
                    saved = json.load(f)
                saved, changed, status = _migrate_state(saved)
                if status == "newer":
                    raise ValueError("State created by newer version")
                if changed:
                    bak = self.state_path + ".bak"
                    try:
                        import shutil as _shutil
                        _shutil.copy2(self.state_path, bak)
                    except Exception:
                        pass
                for k, v in default.items():
                    if k not in saved:
                        saved[k] = v
                return saved
            except ValueError:
                pass
            except Exception:
                pass
        default["schema_version"] = STATE_SCHEMA_VERSION
        return default

    def save(self):
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(self.state_path, "w") as f:
            json.dump(self.state, f, indent=2)

    def update_dep(self, key, status, version=""):
        if key in self.state["deps"]:
            self.state["deps"][key] = {"status": status, "version": version}

    def update_mimo(self, status, version=""):
        self.state["mimo"] = {"status": status, "version": version}

    def record_health_check(self, result):
        self.state["last_health_check"] = datetime.now().isoformat()
        self.state["last_health_result"] = result

    def increment_launches(self):
        self.state["launches"] = self.state.get("launches", 0) + 1

    def can_repair(self):
        return self.state.get("repair_attempts", 0) < self.state.get("max_repairs", MAX_REPAIR_ATTEMPTS)

    def record_repair_attempt(self):
        self.state["repair_attempts"] = self.state.get("repair_attempts", 0) + 1
        self.state["last_repair"] = datetime.now().isoformat()

    def mark_installed(self):
        self.state["installed_at"] = self.state.get("installed_at") or datetime.now().isoformat()
        self.save()

    def mark_install_result(self, result):
        self.state["install_result"] = result
        self.state["last_install_time"] = datetime.now().isoformat()
        self.save()


class TransactionManager:
    def __init__(self, install_dir):
        self.path = get_transaction_path(install_dir)
        self.transaction = self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def start(self, steps):
        self.transaction = {
            "transaction_id": f"tx_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "status": "in_progress",
            "started_at": datetime.now().isoformat(),
            "completed_steps": [],
            "pending_steps": list(steps),
            "rollback_actions": {},
        }
        self._save()

    def complete_step(self, step, rollback_action=None):
        if not self.transaction:
            return
        if step in self.transaction["pending_steps"]:
            self.transaction["pending_steps"].remove(step)
        self.transaction["completed_steps"].append(step)
        if rollback_action:
            self.transaction["rollback_actions"][step] = rollback_action
        self._save()

    def fail(self):
        if not self.transaction:
            return []
        self.transaction["status"] = "failed"
        self._save()
        return list(reversed(self.transaction["completed_steps"]))

    def success(self):
        if not self.transaction:
            return
        self.transaction["status"] = "completed"
        self.transaction["completed_at"] = datetime.now().isoformat()
        self._save()

    def get_rollback_actions(self):
        if not self.transaction:
            return {}
        return self.transaction.get("rollback_actions", {})

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.transaction, f, indent=2)

    def cleanup(self):
        try:
            if os.path.exists(self.path):
                os.remove(self.path)
        except Exception:
            pass


def run_cmd(cmd, timeout=30):
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, shell=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return False, "", "not found"
    except subprocess.TimeoutExpired:
        return False, "", "timeout"
    except Exception as e:
        return False, "", str(e)


def refresh_path():
    try:
        hklm_path = ""
        result = subprocess.run(
            ["reg", "query",
             "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
             "/v", "Path"],
            capture_output=True, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "Path" in line and "REG_" in line:
                    parts = line.split("REG_EXPAND_SZ")
                    if len(parts) == 2:
                        hklm_path = parts[1].strip()
                        break
        hkcu_path = ""
        result = subprocess.run(
            ["reg", "query", "HKCU\\Environment", "/v", "Path"],
            capture_output=True, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "Path" in line and "REG_" in line:
                    parts = line.split("REG_EXPAND_SZ") if "REG_EXPAND_SZ" in line else line.split("REG_SZ")
                    if len(parts) == 2:
                        hkcu_path = parts[1].strip()
                        break
        combined = ";".join(filter(None, [hkcu_path, hklm_path]))
        if combined:
            os.environ["PATH"] = combined
            return True
    except Exception:
        pass
    return False


def add_to_path(dirs):
    try:
        current_path = os.environ.get("PATH", "")
        result = subprocess.run(
            ["reg", "query",
             "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
             "/v", "Path"],
            capture_output=True, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "Path" in line and "REG_" in line:
                    parts = line.split("REG_EXPAND_SZ")
                    if len(parts) == 2:
                        current_path = parts[1].strip()
                        break
        new_dirs = [d for d in dirs if d and os.path.isdir(d) and d not in current_path]
        if not new_dirs:
            return True
        new_path = current_path + ";" + ";".join(new_dirs)
        reg_cmd = [
            "reg", "add",
            "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
            "/v", "Path", "/t", "REG_EXPAND_SZ",
            "/d", new_path, "/f"
        ]
        result = subprocess.run(reg_cmd, capture_output=True,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode == 0:
            os.environ["PATH"] = new_path
            return True
        return False
    except Exception:
        return False


def download_file(url, dest, progress_cb=None, max_retries=3):
    tmp_path = dest + ".tmp"
    for attempt in range(max_retries):
        try:
            def report(block, block_size, total_size):
                if progress_cb and total_size > 0:
                    pct = min(block * block_size / total_size * 100, 100)
                    progress_cb(pct)
            urllib.request.urlretrieve(url, tmp_path, reporthook=report)
            os.replace(tmp_path, dest)
            return True
        except Exception:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            continue
    return False


def cleanup_stale_tmp(install_dir, max_age_hours=24):
    temp_dir = os.path.join(
        os.environ.get("TEMP", os.path.join(install_dir, "temp")), "mimo_install"
    )
    if not os.path.exists(temp_dir):
        return
    cutoff = time.time() - (max_age_hours * 3600)
    for fname in os.listdir(temp_dir):
        if fname.endswith(".tmp"):
            fpath = os.path.join(temp_dir, fname)
            try:
                if os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
            except Exception:
                pass


def verify_hash(filepath, expected_sha256):
    if not expected_sha256:
        return True
    try:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest().lower() == expected_sha256.lower()
    except Exception:
        return False


def silent_install(installer_path, args):
    try:
        quoted_path = f'"{installer_path}"'
        if installer_path.lower().endswith(".msi"):
            cmd = f'msiexec /i {quoted_path} {" ".join(args)}'
        else:
            cmd = f'{quoted_path} {" ".join(args)}'
        result = subprocess.run(cmd, capture_output=True, timeout=600, shell=True,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return result.returncode in (0, 3010)
    except Exception:
        return False


def is_admin():
    try:
        return os.getuid() == 0 or subprocess.run(
            ["net", "session"], capture_output=True
        ).returncode == 0
    except Exception:
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False


class HealthChecker:
    def __init__(self, install_dir, logger):
        self.install_dir = install_dir
        self.log = logger
        self.state = StateManager(install_dir)

    def check_dep(self, key):
        dep = DEPENDENCIES[key]
        ok, out, err = run_cmd(dep["check_cmd"])
        if not ok:
            exe_name = dep["exe_names"][0].replace(".exe", "")
            which_path = shutil.which(exe_name)
            if which_path:
                found_dir = os.path.dirname(which_path)
                os.environ["PATH"] = found_dir + ";" + os.environ.get("PATH", "")
                ok, out, err = run_cmd(dep["check_cmd"])
        if not ok:
            for pd in dep.get("path_dirs", []):
                for exe in dep["exe_names"]:
                    full = os.path.join(pd, exe)
                    if os.path.exists(full):
                        os.environ["PATH"] = pd + ";" + os.environ.get("PATH", "")
                        ok, out, err = run_cmd(dep["check_cmd"])
                        if ok:
                            break
                if ok:
                    break
        if not ok:
            ok, where_out, _ = run_cmd(["where", dep["exe_names"][0]])
            if ok and where_out.strip():
                found_path = where_out.strip().split("\n")[0].strip()
                found_dir = os.path.dirname(found_path)
                os.environ["PATH"] = found_dir + ";" + os.environ.get("PATH", "")
                ok, out, err = run_cmd(dep["check_cmd"])
        return ok, out

    def health_check(self):
        issues = []
        refresh_path()
        for key in ["node", "git"]:
            ok, version = self.check_dep(key)
            if ok:
                self.state.update_dep(key, "ok", version)
                self.log.dependency_detected(DEPENDENCIES[key]["name"], version)
            else:
                self.state.update_dep(key, "missing")
                issues.append(f"{key}_missing")
                self.log.dependency_missing(DEPENDENCIES[key]["name"])
        ok, version = self.check_dep("npm")
        if ok:
            self.state.update_dep("npm", "ok", version)
        else:
            node_ok = self.state.state["deps"]["node"]["status"] == "ok"
            if node_ok:
                issues.append("npm_missing")
                self.log.dependency_missing("npm")
        mimo_ok, mimo_ver, _ = run_cmd(["mimo", "--version"])
        if not mimo_ok:
            mimo_bin = os.path.join(os.path.expanduser("~"), ".mimocode", "bin", "mimo.exe")
            if os.path.exists(mimo_bin):
                mimo_ok = True
                mimo_ver = "found (no --version)"
        if mimo_ok:
            self.state.update_mimo("ok", mimo_ver)
            self.log.dependency_detected("MiMo", mimo_ver)
        else:
            self.state.update_mimo("missing")
            issues.append("mimo_missing")
            self.log.dependency_missing("MiMo")
        if not os.path.exists(self.install_dir):
            issues.append("install_dir_missing")
            self.log.warn(f"Install directory missing: {self.install_dir}")
        result = "healthy" if not issues else "issues_found"
        self.state.record_health_check(result)
        self.state.save()
        self.log.health_check_result(len(issues) == 0, issues)
        return issues

    def auto_repair(self, issues, progress_cb=None):
        if not self.state.can_repair():
            self.log.repair_limit_reached(
                self.state.state["repair_attempts"],
                self.state.state["max_repairs"]
            )
            return []

        self.state.record_repair_attempt()
        self.log.repair_start(issues)
        repaired = []
        for issue in issues:
            if issue == "node_missing":
                self.log.step_start("install_node")
                if self._install_dep("node", progress_cb):
                    repaired.append("node")
                    self.log.step_complete("install_node")
                    self.log.step_start("verify_npm_after_node")
                    refresh_path()
                    for pd in DEPENDENCIES["node"].get("path_dirs", []):
                        if os.path.isdir(pd):
                            os.environ["PATH"] = pd + ";" + os.environ.get("PATH", "")
                    npm_ok, npm_ver = self.check_dep("npm")
                    if npm_ok:
                        self.state.update_dep("npm", "ok", npm_ver)
                        self.log.step_complete("verify_npm_after_node")
                    else:
                        self.log.step_failed("verify_npm_after_node", "npm not found after Node install")
            elif issue == "git_missing":
                self.log.step_start("install_git")
                if self._install_dep("git", progress_cb):
                    repaired.append("git")
                    self.log.step_complete("install_git")
            elif issue == "npm_missing":
                self.log.step_start("verify_npm")
                refresh_path()
                for pd in DEPENDENCIES["node"].get("path_dirs", []):
                    if os.path.isdir(pd):
                        os.environ["PATH"] = pd + ";" + os.environ.get("PATH", "")
                ok, version = self.check_dep("npm")
                if ok:
                    self.state.update_dep("npm", "ok", version)
                    repaired.append("npm")
                    self.log.step_complete("verify_npm")
            elif issue == "mimo_missing":
                self.log.step_start("install_mimo")
                if self._install_mimo(progress_cb):
                    repaired.append("mimo")
                    self.log.step_complete("install_mimo")
        self.state.save()
        self.log.repair_complete(repaired)
        return repaired

    def _install_dep(self, key, progress_cb=None):
        dep = DEPENDENCIES[key]
        url = dep.get("download")
        if not url:
            return False
        temp_dir = os.path.join(os.environ.get("TEMP", os.path.join(self.install_dir, "temp")), "mimo_install")
        os.makedirs(temp_dir, exist_ok=True)
        ext = os.path.splitext(url)[1]
        installer_path = os.path.join(temp_dir, f"{key}{ext}")
        if progress_cb:
            progress_cb(f"Downloading {dep['name']}...")
        if not download_file(url, installer_path):
            self.log.step_failed(f"download_{key}", "download failed")
            return False
        hashes = DEP_HASHES.get(key, {})
        expected = None
        for ver, h in hashes.items():
            if ver in url:
                expected = h
                break
        if expected and not verify_hash(installer_path, expected):
            self.log.step_failed(f"verify_{key}", "hash mismatch")
            try:
                os.remove(installer_path)
            except Exception:
                pass
            return False
        if progress_cb:
            progress_cb(f"Installing {dep['name']}...")
        args = dep.get("installer_args", [])
        install_ok = silent_install(installer_path, args)
        self.log.info(f"{dep['name']} installer exit={install_ok}")
        refresh_path()
        if dep.get("path_dirs"):
            add_to_path(dep["path_dirs"])
        ok, version = self.check_dep(key)
        if ok:
            self.state.update_dep(key, "installed", version)
            self.log.dependency_installed(dep["name"], version)
        else:
            self.state.update_dep(key, "installed_pending")
            self.log.warn(f"{dep['name']} may need restart")
        try:
            os.remove(installer_path)
        except Exception:
            pass
        return ok

    def _install_mimo(self, progress_cb=None):
        refresh_path()
        for pd in DEPENDENCIES.get("node", {}).get("path_dirs", []):
            if os.path.isdir(pd):
                os.environ["PATH"] = pd + ";" + os.environ.get("PATH", "")
        npm_ok, _, _ = run_cmd(["npm", "--version"])
        if npm_ok:
            if progress_cb:
                progress_cb("Installing MiMo via npm...")
            for attempt in range(3):
                ok, _, err = run_cmd(["npm", "install", "-g", "@mimo-ai/cli@0.1.0"], timeout=300)
                if ok:
                    self.state.update_mimo("installed")
                    self.log.dependency_installed("MiMo", "npm")
                    return True
                self.log.step_failed(f"npm_install_attempt_{attempt+1}", err)
                if attempt < 2:
                    run_cmd(["npm", "cache", "clean", "--force"], timeout=30)
        if progress_cb:
            progress_cb("Trying git clone fallback...")
        mimo_repo = "https://github.com/XiaomiMiMo/MiMo-Code.git"
        mimo_install_dir = os.path.join(os.path.expanduser("~"), "MimoCode")
        if os.path.exists(mimo_install_dir):
            ok, _, _ = run_cmd(["git", "-C", mimo_install_dir, "pull"], timeout=60)
        else:
            ok, _, _ = run_cmd(["git", "clone", mimo_repo, mimo_install_dir], timeout=120)
        if ok:
            self.state.update_mimo("installed")
            self.log.dependency_installed("MiMo", "git")
            return True
        self.log.step_failed("install_mimo", "all methods failed")
        return False


MAX_BOOTSTRAP_LOG_SIZE = 5 * 1024 * 1024
MAX_BOOTSTRAP_LOG_BACKUPS = 3


def _rotate_log(log_path):
    if not os.path.exists(log_path):
        return
    if os.path.getsize(log_path) < MAX_BOOTSTRAP_LOG_SIZE:
        return
    for i in range(MAX_BOOTSTRAP_LOG_BACKUPS - 1, 0, -1):
        src = f"{log_path}.{i}.log"
        dst = f"{log_path}.{i+1}.log"
        if os.path.exists(src):
            if os.path.exists(dst):
                os.remove(dst)
            os.rename(src, dst)
    dst = f"{log_path}.1.log"
    if os.path.exists(dst):
        os.remove(dst)
    os.rename(log_path, dst)


def _write_bootstrap_log(install_dir, entries):
    log_dir = os.path.join(install_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "bootstrapper.log")
    try:
        _rotate_log(log_path)
        with open(log_path, "a", encoding="utf-8") as f:
            for ts, level, msg in entries:
                f.write(f"[{ts}] [{level}] {msg}\n")
    except Exception:
        pass


def _acquire_lock(install_dir):
    lock_path = os.path.join(install_dir, "install.lock")
    try:
        if os.path.exists(lock_path):
            age = time.time() - os.path.getmtime(lock_path)
            if age > 600:
                os.remove(lock_path)
            else:
                return None
        with open(lock_path, "w") as f:
            f.write(str(os.getpid()))
        return lock_path
    except Exception:
        return None


def _release_lock(lock_path):
    try:
        if lock_path and os.path.exists(lock_path):
            os.remove(lock_path)
    except Exception:
        pass


def _ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def first_run(install_dir, progress_cb=None):
    portable = is_portable(install_dir)
    ensure_dirs(install_dir, portable=portable)
    log_dir = get_log_dir(install_dir, portable=portable)
    logger = MiMoLogger("bootstrapper", log_dir, get_version())

    lock_path = _acquire_lock(install_dir)
    if lock_path is None:
        logger.error("Another installation is running (install.lock exists)")
        return False

    cleanup_stale_tmp(install_dir)
    logger.install_start()
    log_entries = [(_ts(), "INFO", "Bootstrapper started")]
    state = StateManager(install_dir)
    state.mark_install_result("installing")
    state.save()

    try:
        checker = HealthChecker(install_dir, logger)
        issues = checker.health_check()
        log_entries.append((_ts(), "INFO", f"Health check: {len(issues)} issue(s) — {issues}"))

        if issues:
            repaired = checker.auto_repair(issues, progress_cb)
            log_entries.append((_ts(), "INFO", f"Repaired: {repaired}"))
            issues_after = checker.health_check()
            log_entries.append((_ts(), "INFO", f"Post-repair health: {len(issues_after)} issue(s) — {issues_after}"))
        else:
            issues_after = []
            log_entries.append((_ts(), "INFO", "All components healthy"))

        if issues_after:
            state.mark_install_result("partial")
            log_entries.append((_ts(), "WARNING", f"Install partial — remaining: {issues_after}"))
        else:
            state.mark_install_result("success")
            log_entries.append((_ts(), "INFO", "Install success"))

        state.mark_installed()
        state.increment_launches()
        state.save()
        _write_bootstrap_log(install_dir, log_entries)
        logger.install_complete()
        return len(issues_after) == 0
    finally:
        _release_lock(lock_path)


def health_check_only(install_dir):
    portable = is_portable(install_dir)
    ensure_dirs(install_dir, portable=portable)
    logger = MiMoLogger("bootstrapper", get_log_dir(install_dir, portable=portable), get_version())
    checker = HealthChecker(install_dir, logger)
    issues = checker.health_check()
    return issues


def repair_only(install_dir, progress_cb=None):
    portable = is_portable(install_dir)
    ensure_dirs(install_dir, portable=portable)
    logger = MiMoLogger("repair", get_log_dir(install_dir, portable=portable), get_version())
    checker = HealthChecker(install_dir, logger)
    issues = checker.health_check()
    if issues:
        repaired = checker.auto_repair(issues, progress_cb)
        issues_after = checker.health_check()
        return issues_after
    else:
        logger.info("No issues found")
        return []


def main():
    import argparse
    parser = argparse.ArgumentParser(description="MiMo Bootstrapper v2.1")
    parser.add_argument("--first-run", action="store_true", help="Run first-time setup")
    parser.add_argument("--health-check", action="store_true", help="Run health check only")
    parser.add_argument("--repair", action="store_true", help="Run repair only")
    parser.add_argument("--install-dir", type=str, help="Installation directory")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()
    install_dir = args.install_dir or DEFAULT_INSTALL_DIR
    if args.first_run:
        ok = first_run(install_dir)
        sys.exit(0 if ok else 1)
    elif args.health_check:
        issues = health_check_only(install_dir)
        if args.json:
            print(json.dumps({"healthy": len(issues) == 0, "issues": issues,
                              "version": get_version()}))
        else:
            if issues:
                print(f"Issues found: {', '.join(issues)}")
            else:
                print("System healthy")
        sys.exit(0 if not issues else 1)
    elif args.repair:
        remaining = repair_only(install_dir)
        if args.json:
            print(json.dumps({"success": len(remaining) == 0, "remaining": remaining,
                              "version": get_version()}))
        else:
            if remaining:
                print(f"Remaining issues: {', '.join(remaining)}")
            else:
                print("Repair complete")
        sys.exit(0 if not remaining else 1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
