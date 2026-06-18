"""
MiMo Launch Wrapper v2.1 — Self-Healing Runtime
Uses shared core module for logging, version, and paths.
"""
import os
import sys
import json
import subprocess
import time
import socket

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core import (
    MiMoLogger, get_version, get_log_dir, get_state_path,
    ensure_dirs, is_portable, STATE_FILE, PORTABLE_FLAG
)


def get_install_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def load_state(install_dir):
    state_path = get_state_path(install_dir)
    if os.path.exists(state_path):
        try:
            with open(state_path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_state(install_dir, state):
    state_path = get_state_path(install_dir)
    try:
        with open(state_path, "w") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


def run_cmd(cmd, timeout=15):
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception:
        return False, "", ""


def refresh_path():
    try:
        result = subprocess.run(
            ["reg", "query",
             "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
             "/v", "Path"],
            capture_output=True, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        hklm_path = ""
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "Path" in line and "REG_" in line:
                    parts = line.split("REG_EXPAND_SZ")
                    if len(parts) == 2:
                        hklm_path = parts[1].strip()
                        break
        result = subprocess.run(
            ["reg", "query", "HKCU\\Environment", "/v", "Path"],
            capture_output=True, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        hkcu_path = ""
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
    except Exception:
        pass


def find_mimo_exe(install_dir):
    candidates = [
        os.path.join(install_dir, "mimo.exe"),
        os.path.join(install_dir, "mimo_launch.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    mimo_bin = os.path.join(os.path.expanduser("~"), ".mimocode", "bin", "mimo.exe")
    if os.path.exists(mimo_bin):
        return mimo_bin
    ok, out, _ = run_cmd(["where", "mimo"])
    if ok and out.strip():
        return out.strip().split("\n")[0].strip()
    return None


def launch_health_check(install_dir):
    bootstrapper = os.path.join(install_dir, "bootstrapper", "MiMoBootstrapper.exe")
    if not os.path.exists(bootstrapper):
        bootstrapper_py = os.path.join(install_dir, "bootstrapper", "MiMoBootstrapper.py")
        if os.path.exists(bootstrapper_py):
            bootstrapper = f'python "{bootstrapper_py}"'
        else:
            return []
    cmd = f'"{bootstrapper}" --health-check --json --install-dir "{install_dir}"'
    ok, out, err = run_cmd(cmd, timeout=30)
    if ok and out:
        try:
            result = json.loads(out)
            return result.get("issues", [])
        except Exception:
            pass
    return []


def auto_repair(install_dir, issues):
    bootstrapper = os.path.join(install_dir, "bootstrapper", "MiMoBootstrapper.exe")
    if not os.path.exists(bootstrapper):
        bootstrapper_py = os.path.join(install_dir, "bootstrapper", "MiMoBootstrapper.py")
        if os.path.exists(bootstrapper_py):
            bootstrapper = f'python "{bootstrapper_py}"'
        else:
            return False
    cmd = f'"{bootstrapper}" --repair --json --install-dir "{install_dir}"'
    ok, out, err = run_cmd(cmd, timeout=120)
    if ok and out:
        try:
            result = json.loads(out)
            return result.get("success", False)
        except Exception:
            pass
    return False


def launch_mimo(install_dir, logger):
    mimo_exe = find_mimo_exe(install_dir)
    if not mimo_exe:
        logger.error("MiMo executable not found")
        return False

    state = load_state(install_dir)
    port = 3000

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0

    try:
        subprocess.Popen(
            [mimo_exe, "web", "--port", str(port)],
            cwd=os.path.join(os.path.expanduser("~"), "Documents", "Mimo Projects"),
            startupinfo=startupinfo,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    except Exception as e:
        logger.error(f"Failed to launch MiMo: {e}")
        return False

    for _ in range(30):
        time.sleep(1)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                s.close()
                state["launches"] = state.get("launches", 0) + 1
                state["last_launch"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                save_state(install_dir, state)
                logger.launch(port)
                return True
            s.close()
        except Exception:
            pass

    logger.warn("MiMo started but web server not responding yet")
    return True


def main():
    install_dir = get_install_dir()
    portable = is_portable(install_dir)

    ensure_dirs(install_dir, portable)
    logger = MiMoLogger("launcher", get_log_dir(install_dir, portable), get_version())

    logger.info(f"MiMo Launcher v{get_version()}" + (" (Portable)" if portable else ""))

    refresh_path()

    logger.step_start("health_check")
    issues = launch_health_check(install_dir)

    if issues:
        logger.warn(f"Found {len(issues)} issue(s): {', '.join(issues)}")
        logger.step_start("auto_repair")
        repaired = auto_repair(install_dir, issues)
        if repaired:
            logger.info("Repair complete")
        else:
            logger.warn("Some issues could not be auto-repaired")
    else:
        logger.health_check_result(True)

    launch_mimo(install_dir, logger)


if __name__ == "__main__":
    main()
