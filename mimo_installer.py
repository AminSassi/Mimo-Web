import customtkinter as ctk
import subprocess
import os
import sys
import threading
import time
import json
import shutil
import urllib.request
import ctypes
import socket
import webbrowser
import hashlib
from datetime import datetime
from pathlib import Path

ctk.set_appearance_mode("light")

APP_VERSION = "1.0.0"
BUILD_DATE = "2026.06.17"

MIMO_HOME = os.path.join(os.path.expanduser("~"), ".mimocode")
MIMO_BIN = os.path.join(MIMO_HOME, "bin", "mimo.exe")
MIMO_REPO = "https://github.com/XiaomiMiMo/MiMo-Code.git"
MIMO_INSTALL_DIR = os.path.join(os.path.expanduser("~"), "MimoCode")
LOG_DIR = os.path.join(os.path.expanduser("~"), ".mimocode", "logs")
REPORT_PATH = os.path.join(LOG_DIR, "install_report.json")

TEST_MODE = "--test" in sys.argv
PREFLIGHT = "--preflight" in sys.argv

DEP_HASHES = {
    "node": {
        "20.15.1": "b139ba1b82807918af40fbed49a5b529f67ba198e87bcabdac907b734ff83ab5",
    },
    "git": {
        "2.45.2": "ce022a6a19e58bbbd4823f51cf798b006b4a683b93b0616a7bb5beeee901da98",
    },
}

DEPENDENCIES = {
    "node": {
        "name": "Node.js LTS",
        "check": ["node", "--version"],
        "download": "https://nodejs.org/dist/v20.15.1/node-v20.15.1-x64.msi",
        "installer_args": ["/quiet", "/norestart"],
        "path_dirs": [os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "nodejs")],
        "verify": ["node", "--version"],
        "size_mb": 32
    },
    "npm": {
        "name": "npm",
        "check": ["npm", "--version"],
        "download": None,
        "path_dirs": [],
        "verify": ["npm", "--version"],
        "size_mb": 0
    },
    "git": {
        "name": "Git",
        "check": ["git", "--version"],
        "download": "https://github.com/git-for-windows/git/releases/download/v2.45.2.windows.1/Git-2.45.2-64-bit.exe",
        "installer_args": ["/VERYSILENT", "/NORESTART", "/NOCANCEL"],
        "path_dirs": [os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "Git", "cmd")],
        "verify": ["git", "--version"],
        "size_mb": 55
    },
    "python": {
        "name": "Python 3",
        "check": ["python", "--version"],
        "download": None,
        "verify": ["python", "--version"],
        "size_mb": 0
    }
}

COLORS = {
    "bg": "#FAFBFC",
    "surface": "#FFFFFF",
    "surface_hover": "#F5F5F7",
    "border": "#E5E5EA",
    "border_light": "#F0F0F5",
    "text_primary": "#1D1D1F",
    "text_secondary": "#6E6E73",
    "text_tertiary": "#AEAEB2",
    "accent": "#007AFF",
    "accent_hover": "#0066D6",
    "accent_light": "#E8F4FD",
    "success": "#34C759",
    "success_light": "#E8F9ED",
    "warning": "#FF9500",
    "warning_light": "#FFF4E5",
    "error": "#FF3B30",
    "error_light": "#FFEDE8",
    "progress_bg": "#F0F0F5",
    "progress_fill": "#007AFF",
}

PHASE_TIMES = {
    0: 10,
    1: 5,
    2: 60,
    3: 90,
    4: 30,
    5: 5,
    6: 15,
    7: 2
}


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_cmd(cmd, timeout=30):
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return False, "", "not found"
    except subprocess.TimeoutExpired:
        return False, "", "timeout"
    except Exception as e:
        return False, "", str(e)


def check_internet():
    for url in ["https://www.google.com", "https://1.1.1.1"]:
        try:
            urllib.request.urlopen(url, timeout=5)
            return True
        except Exception:
            continue
    return False


def check_disk_space(drive="C:\\"):
    try:
        usage = shutil.disk_usage(drive)
        free_gb = usage.free / (1024 ** 3)
        return free_gb >= 2, free_gb
    except Exception:
        return False, 0


def get_windows_version():
    try:
        v = sys.getwindowsversion()
        return v.major, v.minor, v.build
    except Exception:
        return 0, 0, 0


def find_port(start=3000, end=9999):
    for port in range(start, end):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.bind(("127.0.0.1", port))
            s.close()
            return port
        except OSError:
            continue
    return 4096


def add_to_path(dirs):
    try:
        result = subprocess.run(
            ["reg", "query",
             "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
             "/v", "Path"],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
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
            current_path = os.environ.get("PATH", "")
        new_dirs = [d for d in dirs if d and os.path.isdir(d) and d not in current_path]
        if not new_dirs:
            return True
        reg_cmd = [
            "reg", "add",
            "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
            "/v", "Path", "/t", "REG_EXPAND_SZ",
            "/d", current_path + ";" + ";".join(new_dirs), "/f"
        ]
        result = subprocess.run(reg_cmd, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode == 0:
            os.environ["PATH"] = current_path + ";" + ";".join(new_dirs)
            return True
        return False
    except Exception:
        return False


def refresh_path():
    try:
        hklm_path = ""
        result = subprocess.run(
            ["reg", "query",
             "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
             "/v", "Path"],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
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
            ["reg", "query",
             "HKCU\\Environment",
             "/v", "Path"],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
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


def download_file(url, dest, progress_callback=None):
    try:
        def report(block, block_size, total_size):
            if progress_callback and total_size > 0:
                pct = min(block * block_size / total_size * 100, 100)
                progress_callback(pct)
        urllib.request.urlretrieve(url, dest, reporthook=report)
        return True
    except Exception:
        return False


def verify_file_hash(filepath, expected_sha256):
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
        if installer_path.lower().endswith(".msi"):
            cmd = ["msiexec", "/i", installer_path] + args
        else:
            cmd = [installer_path] + args
        result = subprocess.run(cmd, capture_output=True, timeout=600,
                               creationflags=subprocess.CREATE_NO_WINDOW)
        return result.returncode == 0
    except Exception:
        return False


def kill_mimo():
    try:
        subprocess.run(["taskkill", "/F", "/IM", "mimo.exe"], capture_output=True,
                      creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        pass


def check_nvidia_gpu():
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0 and result.stdout.strip():
            return True, result.stdout.strip()
        return False, ""
    except Exception:
        return False, ""


def check_cuda():
    try:
        result = subprocess.run(
            ["python", "-c", "import torch; print(torch.cuda.is_available())"],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0 and "True" in result.stdout:
            return True
        return False
    except Exception:
        return False


def open_folder(path):
    try:
        os.startfile(path)
    except Exception:
        pass


def copy_to_clipboard(text):
    try:
        r = subprocess.run(["clip"], input=text.encode("utf-16le"), capture_output=True,
                          creationflags=subprocess.CREATE_NO_WINDOW)
        return r.returncode == 0
    except Exception:
        return False


class InstallerEngine:
    def __init__(self):
        self.log_lines = []
        self.errors = []
        self.repaired = []
        self.found_deps = []
        self.cancelled = False
        self.last_log_path = ""
        self.install_outcome = {
            "status": "UNKNOWN",
            "phase": "",
            "reason": "",
            "install_dir": ""
        }
        self.summary = {
            "nodejs": {"installed": False, "version": ""},
            "npm": {"installed": False, "version": ""},
            "git": {"installed": False, "version": ""},
            "python": {"installed": False, "version": ""},
            "mimo": {"installed": False, "version": ""},
            "launched": False,
            "port": 0,
        }
        self.report = {
            "timestamp": datetime.now().isoformat(),
            "version": APP_VERSION,
            "windows_version": "",
            "admin": False,
            "internet": False,
            "dependencies": {},
            "mimo_installed": False,
            "errors": []
        }

    def log(self, msg, level="INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_lines.append(f"[{ts}] [{level}] {msg}")
        if level == "ERROR":
            self.errors.append(msg)

    def save_report(self):
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            self.report["errors"] = self.errors
            with open(REPORT_PATH, "w") as f:
                json.dump(self.report, f, indent=2)
        except Exception:
            pass

    def save_log(self):
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            path = os.path.join(LOG_DIR, f"install_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(self.log_lines))
            self.last_log_path = path
            return path
        except Exception:
            return ""

    def check_system(self, cb):
        major, minor, build = get_windows_version()
        self.report["windows_version"] = f"Windows {major}.{minor} Build {build}"
        if major < 10:
            return False, "Windows 10 or later required"
        self.report["admin"] = is_admin()
        if not self.report["admin"]:
            return False, "Administrator privileges required"
        self.report["internet"] = check_internet()
        if not self.report["internet"]:
            return False, "Internet connection required"
        disk_ok, free_gb = check_disk_space()
        if not disk_ok:
            return False, "Need at least 2 GB free space"
        gpu_ok, gpu_name = check_nvidia_gpu()
        self.report["gpu"] = gpu_name if gpu_ok else "not found"
        if not gpu_ok:
            return False, "NVIDIA GPU with CUDA support required. MiMo Auto runs locally on your GPU."
        return True, "System check passed"

    def _summary_key(self, dep_key):
        return "nodejs" if dep_key == "node" else dep_key

    def detect_deps(self, cb):
        refresh_path()
        missing = []
        found = []
        for key, dep in DEPENDENCIES.items():
            if key == "npm":
                node_ok = any(k == "node" for k, _, _ in found)
                if not node_ok and not any(k == "node" for k, _, _ in missing):
                    continue
            if dep["check"]:
                ok, out, _ = run_cmd(dep["check"])
                if not ok:
                    exe_name = "node" if key == "node" else "git" if key == "git" else key
                    which_path = shutil.which(exe_name)
                    if which_path:
                        found_dir = os.path.dirname(which_path)
                        if found_dir not in os.environ.get("PATH", ""):
                            os.environ["PATH"] = found_dir + ";" + os.environ.get("PATH", "")
                        ok, out, _ = run_cmd(dep["check"])
                if not ok:
                    path_dirs = dep.get("path_dirs", [])
                    progfiles = os.environ.get("PROGRAMFILES", "C:\\Program Files")
                    progfiles86 = os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")
                    search_dirs = list(path_dirs)
                    if key == "node":
                        search_dirs += [
                            os.path.join(progfiles, "nodejs"),
                            os.path.join(progfiles, "Nodejs"),
                            os.path.join(progfiles, "node.js"),
                            os.path.join(progfiles86, "nodejs"),
                            os.path.join(progfiles86, "Nodejs"),
                            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "nodejs"),
                        ]
                    elif key == "git":
                        search_dirs += [
                            os.path.join(progfiles, "Git", "cmd"),
                            os.path.join(progfiles, "Git", "bin"),
                            os.path.join(progfiles86, "Git", "cmd"),
                        ]
                    exe_name = "node.exe" if key == "node" else "git.exe" if key == "git" else f"{key}.exe"
                    for pd in search_dirs:
                        full_path = os.path.join(pd, exe_name)
                        if os.path.exists(full_path):
                            os.environ["PATH"] = pd + ";" + os.environ.get("PATH", "")
                            ok, out, _ = run_cmd(dep["check"])
                            if ok:
                                break
                    if not ok:
                        where_ok, where_out, _ = run_cmd(["where", exe_name])
                        if where_ok and where_out.strip():
                            found_path = where_out.strip().split("\n")[0].strip()
                            found_dir = os.path.dirname(found_path)
                            os.environ["PATH"] = found_dir + ";" + os.environ.get("PATH", "")
                            ok, out, _ = run_cmd(dep["check"])
                if ok:
                    found.append((key, dep["name"], out))
                    self.report["dependencies"][key] = {"status": "found", "version": out}
                    sk = self._summary_key(key)
                    if sk in self.summary:
                        self.summary[sk]["installed"] = True
                        self.summary[sk]["version"] = out
                else:
                    missing.append((key, dep["name"], dep.get("download")))
                    self.report["dependencies"][key] = {"status": "missing"}
        self.found_deps = found
        return found, missing

    def install_deps(self, cb, missing, approve_callback=None):
        all_ok = True
        for key, name, url in missing:
            if self.cancelled:
                return False
            if not url:
                continue
            if approve_callback and not approve_callback(name):
                continue
            cb(f"Downloading {name}...")
            temp_dir = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "mimo_install")
            os.makedirs(temp_dir, exist_ok=True)
            ext = os.path.splitext(url)[1]
            installer_path = os.path.join(temp_dir, f"{key}{ext}")
            if not download_file(url, installer_path):
                cb(f"Failed to download {name}")
                self.log(f"{name}: download failed", "ERROR")
                all_ok = False
                continue
            expected_hash = None
            dep_hashes = DEP_HASHES.get(key, {})
            if isinstance(dep_hashes, dict) and url:
                for ver, h in dep_hashes.items():
                    if ver in url:
                        expected_hash = h
                        break
            elif isinstance(dep_hashes, str):
                expected_hash = dep_hashes
            if expected_hash and not verify_file_hash(installer_path, expected_hash):
                cb(f"Download corrupted: {name}")
                self.log(f"{name}: SHA-256 hash mismatch", "ERROR")
                all_ok = False
                try:
                    os.remove(installer_path)
                except Exception:
                    pass
                continue
            cb(f"Installing {name}...")
            args = DEPENDENCIES[key].get("installer_args", [])
            install_ok = silent_install(installer_path, args)
            self.log(f"{name}: installer exit={install_ok}")
            refresh_path()
            path_dirs = DEPENDENCIES[key].get("path_dirs", [])
            if path_dirs:
                add_to_path(path_dirs)
            ok, out, _ = run_cmd(DEPENDENCIES[key]["verify"])
            if not ok:
                search_dirs = list(path_dirs) if path_dirs else []
                progfiles = os.environ.get("PROGRAMFILES", "C:\\Program Files")
                progfiles86 = os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")
                if key == "node":
                    search_dirs += [
                        os.path.join(progfiles, "nodejs"),
                        os.path.join(progfiles, "Nodejs"),
                        os.path.join(progfiles, "node.js"),
                        os.path.join(progfiles86, "nodejs"),
                        os.path.join(progfiles86, "Nodejs"),
                        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "nodejs"),
                    ]
                elif key == "git":
                    search_dirs += [
                        os.path.join(progfiles, "Git", "cmd"),
                        os.path.join(progfiles, "Git", "bin"),
                        os.path.join(progfiles86, "Git", "cmd"),
                    ]
                exe_name = "node.exe" if key == "node" else "git.exe" if key == "git" else f"{key}.exe"
                for pd in search_dirs:
                    full_path = os.path.join(pd, exe_name)
                    if os.path.exists(full_path):
                        self.log(f"{name}: found at {full_path}")
                        new_path = pd + ";" + os.environ.get("PATH", "")
                        os.environ["PATH"] = new_path
                        ok, out, _ = run_cmd(DEPENDENCIES[key]["verify"])
                        if ok:
                            break
                if not ok:
                    where_ok, where_out, _ = run_cmd(["where", exe_name])
                    if where_ok and where_out.strip():
                        found_path = where_out.strip().split("\n")[0].strip()
                        found_dir = os.path.dirname(found_path)
                        self.log(f"{name}: found via 'where' at {found_dir}")
                        os.environ["PATH"] = found_dir + ";" + os.environ.get("PATH", "")
                        ok, out, _ = run_cmd(DEPENDENCIES[key]["verify"])
            sk = self._summary_key(key)
            if ok:
                cb(f"{name} installed")
                self.repaired.append(key)
                if sk in self.summary:
                    self.summary[sk]["installed"] = True
                    self.summary[sk]["version"] = out
            else:
                cb(f"{name} may need restart")
                self.log(f"{name}: verification failed", "ERROR")
                all_ok = False
            try:
                os.remove(installer_path)
            except Exception:
                pass
        return all_ok

    def install_mimo(self, cb):
        ok, out, _ = run_cmd(["mimo", "--version"])
        if ok:
            self.report["mimo_installed"] = True
            self.summary["mimo"]["installed"] = True
            self.summary["mimo"]["version"] = out
            cb(f"MiMo {out} found")
            return True
        if os.path.exists(MIMO_BIN):
            self.report["mimo_installed"] = True
            self.summary["mimo"]["installed"] = True
            cb("MiMo found")
            return True
        npm_ok, _, _ = run_cmd(["npm", "--version"])
        if npm_ok:
            cb("Installing via npm...")
            for attempt in range(3):
                ok, _, err = run_cmd(["npm", "install", "-g", "@mimo-ai/cli"], timeout=300)
                if ok:
                    self.report["mimo_installed"] = True
                    self.summary["mimo"]["installed"] = True
                    cb("MiMo installed")
                    return True
                self.log(f"npm install attempt {attempt+1} failed: {err}", "ERROR")
                if attempt < 2:
                    run_cmd(["npm", "cache", "clean", "--force"], timeout=30)
        cb("Trying git clone...")
        if os.path.exists(MIMO_INSTALL_DIR):
            ok, _, _ = run_cmd(["git", "-C", MIMO_INSTALL_DIR, "pull"], timeout=60)
            if ok:
                self.report["mimo_installed"] = True
                self.summary["mimo"]["installed"] = True
                return True
        else:
            ok, _, _ = run_cmd(["git", "clone", MIMO_REPO, MIMO_INSTALL_DIR], timeout=120)
            if ok:
                self.report["mimo_installed"] = True
                self.summary["mimo"]["installed"] = True
                return True
        self.log("MiMo install failed", "ERROR")
        return False

    def validate(self, cb):
        passed = 0
        total = 0
        for name, cmd in [("mimo", ["mimo", "--version"]), ("node", ["node", "--version"]),
                          ("npm", ["npm", "--version"]), ("git", ["git", "--version"])]:
            total += 1
            ok, out, _ = run_cmd(cmd)
            if ok:
                passed += 1
                sk = self._summary_key(name)
                if sk in self.summary:
                    self.summary[sk]["installed"] = True
                    self.summary[sk]["version"] = out
            elif name == "mimo" and os.path.exists(MIMO_BIN):
                passed += 1
                sk = self._summary_key(name)
                if sk in self.summary:
                    self.summary[sk]["installed"] = True
        return passed, total

    def launch(self, cb, port=3000):
        kill_mimo()
        try:
            os.makedirs(os.path.join(os.path.expanduser("~"), "Documents", "Mimo Projects"), exist_ok=True)
        except Exception:
            pass
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        try:
            subprocess.Popen(
                ["cmd", "/c", "mimo", "web", "--port", str(port)],
                cwd=os.path.join(os.path.expanduser("~"), "Documents", "Mimo Projects"),
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception:
            return False, 0
        for _ in range(30):
            time.sleep(1)
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    s.close()
                    self.summary["launched"] = True
                    self.summary["port"] = port
                    return True, port
                s.close()
            except Exception:
                pass
        return False, 0


class ModernButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        defaults = {
            "height": 44,
            "corner_radius": 10,
            "font": ctk.CTkFont(size=14, weight="bold"),
            "cursor": "hand2",
        }
        defaults.update(kwargs)
        super().__init__(master, **defaults)


class InstallerWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MiMo Installer")
        self.geometry("700x580")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])
        self.engine = InstallerEngine()
        self.running = False
        self.install_dir = os.path.join(os.path.expanduser("~"), "MimoCode")
        self.phase_start_time = 0
        self.total_elapsed = 0
        self.screens = []
        self._build_screens()
        self._show_screen(0)

    def _build_screens(self):
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)
        self.screens = [
            self._build_welcome(),
            self._build_location(),
            self._build_progress(),
            self._build_complete()
        ]
        version_bar = ctk.CTkLabel(self, text=f"MiMo Installer v{APP_VERSION} \u00b7 Build {BUILD_DATE}",
                                   font=ctk.CTkFont(size=10), text_color=COLORS["text_tertiary"])
        version_bar.pack(side="bottom", pady=(0, 6))

    def _make_card(self, parent):
        return ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=16,
                           border_width=1, border_color=COLORS["border"])

    def _build_welcome(self):
        screen = ctk.CTkFrame(self.container, fg_color="transparent")
        ctk.CTkFrame(screen, fg_color="transparent", height=40).pack()

        card = self._make_card(screen)
        card.pack(padx=40, fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=40, pady=35)

        logo = ctk.CTkFrame(inner, fg_color=COLORS["accent_light"], width=72, height=72, corner_radius=18)
        logo.pack(pady=(0, 16))
        logo.pack_propagate(False)
        ctk.CTkLabel(logo, text="M", font=ctk.CTkFont(size=32, weight="bold"),
                    text_color=COLORS["accent"]).pack(expand=True)

        ctk.CTkLabel(inner, text="Install MiMo", font=ctk.CTkFont(size=26, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(0, 6))
        ctk.CTkLabel(inner, text="AI-powered coding assistant for your terminal",
                    font=ctk.CTkFont(size=14), text_color=COLORS["text_secondary"]).pack(pady=(0, 24))

        features_frame = ctk.CTkFrame(inner, fg_color="transparent")
        features_frame.pack(fill="x", pady=(0, 24))
        for feat in ["Automatically installs all required dependencies",
                     "Works with VS Code, terminal, and web browser",
                     "Regular updates and security patches"]:
            row = ctk.CTkFrame(features_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text="  \u2713  ", font=ctk.CTkFont(size=13),
                        text_color=COLORS["success"]).pack(side="left")
            ctk.CTkLabel(row, text=feat, font=ctk.CTkFont(size=13),
                        text_color=COLORS["text_secondary"]).pack(side="left")

        if TEST_MODE:
            ctk.CTkLabel(inner, text="TEST MODE \u2014 No changes will be made",
                        font=ctk.CTkFont(size=12, weight="bold"), text_color=COLORS["warning"],
                        fg_color=COLORS["warning_light"], corner_radius=6, padx=12, pady=4).pack(pady=(0, 12))

        btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
        btn_frame.pack(fill="x")

        ModernButton(btn_frame, text="Begin Installation", fg_color=COLORS["accent"],
                    hover_color=COLORS["accent_hover"], command=self._start_install).pack(side="right")
        ModernButton(btn_frame, text="Repair", width=80, fg_color=COLORS["surface"],
                    hover_color=COLORS["surface_hover"], text_color=COLORS["success"],
                    border_width=1, border_color=COLORS["success"],
                    command=self._start_repair).pack(side="right", padx=(0, 8))
        ModernButton(btn_frame, text="Test Mode", width=90, fg_color=COLORS["surface"],
                    hover_color=COLORS["surface_hover"], text_color=COLORS["text_secondary"],
                    border_width=1, border_color=COLORS["border"],
                    command=self._start_test).pack(side="right", padx=(0, 8))

        return screen

    def _build_location(self):
        screen = ctk.CTkFrame(self.container, fg_color="transparent")
        ctk.CTkFrame(screen, fg_color="transparent", height=50).pack()
        card = self._make_card(screen)
        card.pack(padx=40, fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=40, pady=35)

        ctk.CTkLabel(inner, text="Installation Location", font=ctk.CTkFont(size=22, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(anchor="w", pady=(0, 6))
        ctk.CTkLabel(inner, text="Choose where to install MiMo on your computer.",
                    font=ctk.CTkFont(size=13), text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(0, 20))

        path_frame = ctk.CTkFrame(inner, fg_color=COLORS["bg"], corner_radius=10,
                                 border_width=1, border_color=COLORS["border"])
        path_frame.pack(fill="x", pady=(0, 16))
        self.path_label = ctk.CTkLabel(path_frame, text=self.install_dir,
                                      font=ctk.CTkFont(family="Consolas", size=12),
                                      text_color=COLORS["text_primary"])
        self.path_label.pack(side="left", padx=14, pady=10)
        ModernButton(path_frame, text="Change...", width=80, height=30, font=ctk.CTkFont(size=12),
                    fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
                    text_color=COLORS["text_primary"], border_width=1, border_color=COLORS["border"],
                    command=self._pick_folder).pack(side="right", padx=10, pady=10)

        disk_ok, free_gb = check_disk_space()
        ctk.CTkLabel(inner, text=f"{free_gb:.1f} GB available on C:\\",
                    font=ctk.CTkFont(size=12), text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(0, 24))

        btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
        btn_frame.pack(fill="x")
        ModernButton(btn_frame, text="Install", width=120, fg_color=COLORS["accent"],
                    hover_color=COLORS["accent_hover"], command=self._do_install).pack(side="right")
        ModernButton(btn_frame, text="Back", width=80, fg_color=COLORS["surface"],
                    hover_color=COLORS["surface_hover"], text_color=COLORS["text_primary"],
                    border_width=1, border_color=COLORS["border"],
                    command=lambda: self._show_screen(0)).pack(side="right", padx=(0, 8))
        return screen

    def _build_progress(self):
        screen = ctk.CTkFrame(self.container, fg_color="transparent")
        ctk.CTkFrame(screen, fg_color="transparent", height=40).pack()
        card = self._make_card(screen)
        card.pack(padx=40, fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=40, pady=35)

        self.progress_title = ctk.CTkLabel(inner, text="Installing MiMo",
                                          font=ctk.CTkFont(size=22, weight="bold"),
                                          text_color=COLORS["text_primary"])
        self.progress_title.pack(anchor="w", pady=(0, 4))

        self.progress_subtitle = ctk.CTkLabel(inner, text="This may take a few minutes",
                                             font=ctk.CTkFont(size=13),
                                             text_color=COLORS["text_secondary"])
        self.progress_subtitle.pack(anchor="w", pady=(0, 20))

        self.progress_bar_bg = ctk.CTkFrame(inner, fg_color=COLORS["progress_bg"],
                                           height=6, corner_radius=3)
        self.progress_bar_bg.pack(fill="x", pady=(0, 4))
        self.progress_bar_bg.pack_propagate(False)
        self.progress_bar_fill = ctk.CTkFrame(self.progress_bar_bg, fg_color=COLORS["progress_fill"], corner_radius=3)
        self.progress_bar_fill.place(relx=0, rely=0, relwidth=0, relheight=1)

        eta_frame = ctk.CTkFrame(inner, fg_color="transparent")
        eta_frame.pack(fill="x", pady=(2, 14))
        self.progress_pct = ctk.CTkLabel(eta_frame, text="0%",
                                        font=ctk.CTkFont(size=11), text_color=COLORS["text_tertiary"])
        self.progress_pct.pack(side="left")
        self.progress_eta = ctk.CTkLabel(eta_frame, text="Estimating time...",
                                        font=ctk.CTkFont(size=11), text_color=COLORS["text_tertiary"])
        self.progress_eta.pack(side="right")

        self.log_frame = ctk.CTkFrame(inner, fg_color=COLORS["bg"], corner_radius=8,
                                      border_width=1, border_color=COLORS["border_light"])
        self.log_frame.pack(fill="x")
        self.log_box = ctk.CTkTextbox(self.log_frame, font=ctk.CTkFont(family="Consolas", size=11),
                                      fg_color="transparent", text_color=COLORS["text_secondary"],
                                      border_width=0, height=100, state="disabled")
        self.log_box.pack(padx=12, pady=10, fill="x")

        self.cancel_btn = ModernButton(inner, text="Cancel", width=80,
                                      fg_color=COLORS["surface"], hover_color=COLORS["error_light"],
                                      text_color=COLORS["error"], border_width=1, border_color=COLORS["border"],
                                      command=self._cancel_install)
        self.cancel_btn.pack(anchor="e", pady=(14, 0))
        return screen

    def _build_complete(self):
        screen = ctk.CTkFrame(self.container, fg_color="transparent")
        ctk.CTkFrame(screen, fg_color="transparent", height=30).pack()
        card = self._make_card(screen)
        card.pack(padx=40, fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=40, pady=30)

        self.complete_icon_frame = ctk.CTkFrame(inner, fg_color=COLORS["success_light"], width=64, height=64, corner_radius=32)
        self.complete_icon_frame.pack(pady=(0, 12))
        self.complete_icon_frame.pack_propagate(False)
        self.complete_icon_label = ctk.CTkLabel(self.complete_icon_frame, text="\u2713",
                    font=ctk.CTkFont(size=28, weight="bold"), text_color=COLORS["success"])
        self.complete_icon_label.pack(expand=True)

        self.complete_title = ctk.CTkLabel(inner, text="Installation Complete",
                                          font=ctk.CTkFont(size=24, weight="bold"),
                                          text_color=COLORS["text_primary"])
        self.complete_title.pack(pady=(0, 4))

        self.complete_subtitle = ctk.CTkLabel(inner, text="MiMo is ready to use",
                                             font=ctk.CTkFont(size=13),
                                             text_color=COLORS["text_secondary"])
        self.complete_subtitle.pack(pady=(0, 8))

        self.summary_frame = ctk.CTkFrame(inner, fg_color=COLORS["bg"], corner_radius=8,
                                         border_width=1, border_color=COLORS["border_light"])
        self.summary_items = {}
        for key, label in [("nodejs", "Node.js"), ("git", "Git"), ("mimo", "MiMo")]:
            row = ctk.CTkFrame(self.summary_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=3)
            icon = ctk.CTkLabel(row, text="\u2713", font=ctk.CTkFont(size=12, weight="bold"),
                               text_color=COLORS["success"], width=20)
            icon.pack(side="left")
            name_lbl = ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=12, weight="bold"),
                                   text_color=COLORS["text_primary"], width=80, anchor="w")
            name_lbl.pack(side="left")
            ver_lbl = ctk.CTkLabel(row, text="...", font=ctk.CTkFont(size=11),
                                  text_color=COLORS["text_tertiary"])
            ver_lbl.pack(side="left", padx=(4, 0))
            self.summary_items[key] = {"icon": icon, "ver": ver_lbl}

        self.complete_error_box = ctk.CTkFrame(inner, fg_color=COLORS["error_light"], corner_radius=8)
        self.complete_error_label = ctk.CTkLabel(self.complete_error_box, text="",
                                                font=ctk.CTkFont(size=11), text_color=COLORS["error"],
                                                wraplength=420, justify="left")
        self.complete_error_label.pack(padx=14, pady=10, anchor="w")

        self.tips_frame = ctk.CTkFrame(inner, fg_color=COLORS["accent_light"], corner_radius=8)
        self.tips_label = ctk.CTkLabel(self.tips_frame, text="Try these commands:\n  mimo web\n  mimo help\n  mimo --version",
                                      font=ctk.CTkFont(family="Consolas", size=11),
                                      text_color=COLORS["text_primary"], justify="left")
        self.tips_label.pack(padx=14, pady=10, anchor="w")

        self.complete_btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
        self.complete_btn_frame.pack(fill="x", pady=(14, 0))

        self.launch_btn = ModernButton(self.complete_btn_frame, text="Launch MiMo", width=140,
                    fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                    command=self._launch_mimo)
        self.close_btn = ModernButton(self.complete_btn_frame, text="Close", width=80,
                    fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
                    text_color=COLORS["text_primary"], border_width=1, border_color=COLORS["border"],
                    command=self.destroy)
        self.retry_btn = ModernButton(self.complete_btn_frame, text="Retry", width=80,
                    fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                    command=lambda: self._show_screen(0))
        self.copy_err_btn = ModernButton(self.complete_btn_frame, text="Copy Error", width=90,
                    fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
                    text_color=COLORS["text_secondary"], border_width=1, border_color=COLORS["border"],
                    command=self._copy_error)
        self.open_logs_btn = ModernButton(self.complete_btn_frame, text="Open Logs", width=90,
                    fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
                    text_color=COLORS["text_secondary"], border_width=1, border_color=COLORS["border"],
                    command=self._open_logs)
        self.export_btn = ModernButton(self.complete_btn_frame, text="Export Report", width=100,
                    fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
                    text_color=COLORS["text_secondary"], border_width=1, border_color=COLORS["border"],
                    command=self._pick_export_path)

        return screen

    def _show_screen(self, idx):
        for s in self.screens:
            s.pack_forget()
        self.current_screen = idx
        self.screens[idx].pack(fill="both", expand=True)

    def _pick_folder(self):
        try:
            from tkinter import filedialog
            folder = filedialog.askdirectory(initialdir=self.install_dir)
            if folder:
                self.install_dir = folder
                self.path_label.configure(text=folder)
        except Exception:
            pass

    def _pick_export_path(self):
        try:
            from tkinter import filedialog
            save_path = filedialog.asksaveasfilename(
                defaultextension=".zip",
                filetypes=[("ZIP files", "*.zip")],
                initialfile=f"MiMo_Diagnostic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            )
            if save_path:
                threading.Thread(target=self._export_diagnostic, args=(save_path,), daemon=True).start()
        except Exception:
            pass

    def _export_diagnostic(self, save_path):
        try:
            import zipfile

            with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zf:

                zf.writestr("manifest.txt",
                    f"MiMo Installer Version: {APP_VERSION}\n"
                    f"Build Date: {BUILD_DATE}\n"
                    f"Python Version: {sys.version.split()[0]}\n"
                    f"Export Format Version: 1\n"
                    f"Report Generated: {datetime.now().isoformat()}\n")

                outcome = self.engine.install_outcome
                zf.writestr("install_outcome.txt",
                    f"Status: {outcome['status']}\n"
                    f"Phase: {outcome['phase'] or 'N/A'}\n"
                    f"Reason: {outcome['reason'] or 'N/A'}\n"
                    f"Install Directory: {outcome.get('install_dir', 'N/A')}\n")

                zf.writestr("installer_settings.txt",
                    f"Run As Admin: {is_admin()}\n"
                    f"Internet Available: {check_internet()}\n"
                    f"Install Directory: {self.install_dir}\n"
                    f"Test Mode: {TEST_MODE}\n")

                if self.engine.last_log_path and os.path.exists(self.engine.last_log_path):
                    zf.write(self.engine.last_log_path, "install.log")
                else:
                    zf.writestr("install.log", "\n".join(self.engine.log_lines) if self.engine.log_lines else "No log available")

                if os.path.exists(REPORT_PATH):
                    zf.write(REPORT_PATH, "install_report.json")
                else:
                    zf.writestr("install_report.json", json.dumps(self.engine.report, indent=2))

                major, minor, build = get_windows_version()
                disk_ok, free_gb = check_disk_space()
                zf.writestr("system_info.txt",
                    f"Windows: {major}.{minor} Build {build}\n"
                    f"Disk: {free_gb:.1f} GB free ({'OK' if disk_ok else 'LOW'})\n")

                gpu_ok, gpu_name = check_nvidia_gpu()
                cuda_ok = check_cuda()
                zf.writestr("gpu_info.txt",
                    f"NVIDIA GPU: {gpu_name if gpu_ok else 'Not detected'}\n"
                    f"CUDA Available: {cuda_ok}\n")

                dep_lines = []
                for key, dep in DEPENDENCIES.items():
                    if dep["check"]:
                        ok, out, err = run_cmd(dep["check"])
                        dep_lines.append(f"{dep['name']}: {out if ok else 'NOT FOUND'}")
                zf.writestr("dependency_versions.txt", "\n".join(dep_lines) + "\n")

                val_lines = []
                for name, cmd in [("mimo", ["mimo", "--version"]), ("node", ["node", "--version"]),
                                  ("npm", ["npm", "--version"]), ("git", ["git", "--version"])]:
                    ok, out, err = run_cmd(cmd)
                    if ok:
                        val_lines.append(f"{name}: {out}")
                    elif name == "mimo" and os.path.exists(MIMO_BIN):
                        val_lines.append(f"{name}: found (no --version)")
                    else:
                        val_lines.append(f"{name}: NOT FOUND")
                zf.writestr("validation_results.txt", "\n".join(val_lines) + "\n")

            open_folder(os.path.dirname(save_path))

        except Exception:
            pass

    def _log_progress(self, msg):
        self.after(0, self._append_log, msg)

    def _append_log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _set_progress(self, pct, text=None):
        def _update():
            w = max(pct / 100, 0.01)
            self.progress_bar_fill.place(relx=0, rely=0, relwidth=w, relheight=1)
            self.progress_pct.configure(text=f"{int(pct)}%")
            if text:
                self.progress_subtitle.configure(text=text)
            elapsed = time.time() - self.phase_start_time if self.phase_start_time else 0
            if pct > 5:
                estimated_total = elapsed / (pct / 100)
                remaining = max(estimated_total - elapsed, 0)
                if remaining < 60:
                    self.progress_eta.configure(text=f"~{int(remaining)}s remaining")
                else:
                    self.progress_eta.configure(text=f"~{int(remaining/60)}m {int(remaining%60)}s remaining")
            else:
                self.progress_eta.configure(text="Estimating time...")
        self.after(0, _update)

    def _approve_dialog(self, name):
        result = [False]
        event = threading.Event()
        def show():
            try:
                dialog = ctk.CTkToplevel(self)
                dialog.title("Install Component")
                dialog.geometry("380x200")
                dialog.configure(fg_color=COLORS["bg"])
                dialog.transient(self)
                dialog.grab_set()
                dialog.attributes("-topmost", True)
                inner = ctk.CTkFrame(dialog, fg_color="transparent")
                inner.pack(fill="both", expand=True, padx=24, pady=24)
                ctk.CTkLabel(inner, text=f"Install {name}?", font=ctk.CTkFont(size=16, weight="bold"),
                            text_color=COLORS["text_primary"]).pack(anchor="w", pady=(0, 8))
                ctk.CTkLabel(inner, text="Required component not found on your system.",
                            font=ctk.CTkFont(size=12), text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(0, 20))
                bf = ctk.CTkFrame(inner, fg_color="transparent")
                bf.pack(fill="x")
                ModernButton(bf, text="Install", width=100, fg_color=COLORS["accent"],
                            hover_color=COLORS["accent_hover"],
                            command=lambda: (result.__setitem__(0, True), dialog.destroy(), event.set())).pack(side="right")
                ModernButton(bf, text="Skip", width=80, fg_color=COLORS["surface"],
                            hover_color=COLORS["surface_hover"], text_color=COLORS["text_secondary"],
                            border_width=1, border_color=COLORS["border"],
                            command=lambda: (dialog.destroy(), event.set())).pack(side="right", padx=(0, 8))
            except Exception:
                event.set()
        self.after(0, show)
        event.wait(timeout=120)
        return result[0]

    def _update_summary(self):
        for key in ["nodejs", "git", "mimo"]:
            s = self.engine.summary[key]
            item = self.summary_items[key]
            if s["installed"]:
                item["icon"].configure(text="\u2713", text_color=COLORS["success"])
                item["ver"].configure(text=s["version"] if s["version"] else "installed",
                                     text_color=COLORS["text_secondary"])
            else:
                item["icon"].configure(text="\u2717", text_color=COLORS["error"])
                item["ver"].configure(text="not installed", text_color=COLORS["error"])

    def _copy_error(self):
        text = f"MiMo Installer Error Report\n{'='*40}\n"
        text += f"Version: {APP_VERSION}\n"
        text += f"Time: {datetime.now().isoformat()}\n\n"
        text += "Log:\n" + "\n".join(self.engine.log_lines[-20:])
        if self.engine.last_log_path:
            text += f"\n\nFull log: {self.engine.last_log_path}"
        copy_to_clipboard(text)

    def _open_logs(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        open_folder(LOG_DIR)

    def _start_test(self):
        if self.running:
            return
        self.running = True
        self.engine = InstallerEngine()
        self._show_screen(2)
        self.progress_title.configure(text="Testing System")
        self.summary_frame.pack_forget()
        self.tips_frame.pack_forget()
        self.complete_error_box.pack_forget()
        threading.Thread(target=self._run_test, daemon=True).start()

    def _start_repair(self):
        if self.running:
            return
        self.running = True
        self.engine = InstallerEngine()
        self._show_screen(2)
        self.progress_title.configure(text="Repairing Installation")
        self.summary_frame.pack_forget()
        self.tips_frame.pack_forget()
        self.complete_error_box.pack_forget()
        threading.Thread(target=self._run_repair, daemon=True).start()

    def _start_install(self):
        self._show_screen(1)

    def _do_install(self):
        if self.running:
            return
        self.running = True
        self.engine = InstallerEngine()
        self._show_screen(2)
        self.progress_title.configure(text="Installing MiMo")
        self.summary_frame.pack_forget()
        self.tips_frame.pack_forget()
        self.complete_error_box.pack_forget()
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        threading.Thread(target=self._run_install, daemon=True).start()

    def _cancel_install(self):
        if self.running:
            self.engine.cancelled = True
            self._log_progress("Cancelling...")

    def _finish(self, success=True, msg="Installation Complete", error_detail="", phase=""):
        self.running = False
        self.engine.install_outcome["status"] = "SUCCESS" if success else "FAILED"
        if phase:
            self.engine.install_outcome["phase"] = phase
        if error_detail:
            self.engine.install_outcome["reason"] = error_detail.split("\n")[0]
        self.engine.install_outcome["install_dir"] = self.install_dir
        for w in self.complete_btn_frame.winfo_children():
            w.pack_forget()

        self._update_summary()

        if success:
            self.complete_icon_frame.configure(fg_color=COLORS["success_light"])
            self.complete_icon_label.configure(text="\u2713", text_color=COLORS["success"])
            self.complete_title.configure(text=msg, text_color=COLORS["text_primary"])
            self.complete_subtitle.configure(text="", text_color=COLORS["text_secondary"])
            self.complete_error_box.pack_forget()
            self.summary_frame.pack(fill="x", pady=(0, 8))
            self.tips_frame.pack(fill="x", pady=(0, 4))
            self.export_btn.pack(side="right", padx=(0, 6))
            self.launch_btn.pack(side="right")
            self.close_btn.pack(side="right", padx=(0, 8))
        else:
            self.complete_icon_frame.configure(fg_color=COLORS["error_light"])
            self.complete_icon_label.configure(text="\u2717", text_color=COLORS["error"])
            self.complete_title.configure(text=msg, text_color=COLORS["error"])
            self.complete_subtitle.configure(
                text="Installation could not be completed. See details below.",
                text_color=COLORS["text_secondary"])
            if error_detail:
                self.complete_error_label.configure(text=error_detail)
                self.complete_error_box.pack(fill="x", pady=(0, 4))
            self.summary_frame.pack(fill="x", pady=(0, 4))
            self.tips_frame.pack_forget()
            self.retry_btn.pack(side="right")
            self.export_btn.pack(side="right", padx=(0, 6))
            self.copy_err_btn.pack(side="right", padx=(0, 6))
            self.open_logs_btn.pack(side="right", padx=(0, 6))
            self.close_btn.pack(side="left")

        self.after(500, lambda: self._show_screen(3))

    def _run_test(self):
        try:
            self.phase_start_time = time.time()
            self._log_progress("Checking system...")
            self._set_progress(10, "Checking system requirements...")
            time.sleep(0.5)
            ok, msg = self.engine.check_system(self._log_progress)
            self._set_progress(30, "Detecting dependencies...")
            self._log_progress(msg)
            time.sleep(0.3)
            found, missing = self.engine.detect_deps(self._log_progress)
            self._set_progress(60, "Analyzing results...")
            time.sleep(0.5)
            if missing:
                self._log_progress(f"\nMissing: {', '.join([m[1] for m in missing])}")
                self._log_progress("The installer will download these automatically.")
            else:
                self._log_progress("\nAll dependencies found!")
            self._set_progress(80, "Validating...")
            passed, total = self.engine.validate(self._log_progress)
            self._set_progress(100, "Test complete")
            self._log_progress(f"\nValidation: {passed}/{total} checks passed")
            self.engine.save_log()
            if not ok:
                self._log_progress(f"\nIssue: {msg}")
                self.after(1000, lambda: self._finish(False, "System Not Ready"))
            else:
                self._log_progress("\nYour system is ready for installation.")
                self.after(1000, lambda: self._finish(True, "System Ready"))
        except Exception as e:
            self._log_progress(f"\nError: {e}")
            self.after(1000, lambda: self._finish(False, "Test Failed"))

    def _run_repair(self):
        try:
            self.phase_start_time = time.time()
            self._log_progress("Checking system...")
            self._set_progress(10, "Checking system...")
            ok, msg = self.engine.check_system(self._log_progress)
            if not ok:
                self.after(1000, lambda m=msg: self._finish(False, "System Check Failed", m))
                return
            self._set_progress(30, "Detecting dependencies...")
            found, missing = self.engine.detect_deps(self._log_progress)
            if missing:
                self._set_progress(50, "Installing missing components...")
                deps_ok = self.engine.install_deps(self._log_progress, missing, self._approve_dialog)
            else:
                deps_ok = True
            self._set_progress(80, "Validating...")
            passed, total = self.engine.validate(self._log_progress)
            self._set_progress(100, "Repair complete")
            self.engine.save_log()
            if deps_ok and passed == total:
                self.after(1000, lambda: self._finish(True, "Repair Complete"))
            elif passed > 0:
                self.after(1000, lambda: self._finish(True, "Installed with Warnings"))
            else:
                self.after(1000, lambda: self._finish(False, "Repair Failed",
                    "Could not verify any components. A reboot may be required."))
        except Exception as e:
            self._log_progress(f"\nError: {e}")
            self.after(1000, lambda: self._finish(False, "Repair Failed"))

    def _run_install(self):
        try:
            self.phase_start_time = time.time()
            self._log_progress("Checking system...")
            self._set_progress(5, "Checking system requirements...")
            time.sleep(0.3)
            ok, msg = self.engine.check_system(self._log_progress)
            if not ok:
                self._log_progress(f"Error: {msg}")
                self.after(1000, lambda m=msg: self._finish(False, "System Check Failed",
                    f"{m}\n\nFix: Right-click MiMo Installer.exe and select 'Run as administrator'.",
                    phase="System Check"))
                return
            self._set_progress(15, "Detecting dependencies...")
            self._log_progress("Scanning for dependencies...")
            time.sleep(0.3)
            found, missing = self.engine.detect_deps(self._log_progress)
            if missing:
                self._set_progress(25, "Installing dependencies...")
                self.engine.install_deps(self._log_progress, missing, self._approve_dialog)
            else:
                self._log_progress("All dependencies found")
            if self.engine.cancelled:
                self.after(500, lambda: self._finish(False, "Installation Cancelled"))
                return
            self._set_progress(45, "Installing MiMo...")
            self._log_progress("\nInstalling MiMo...")
            if not self.engine.install_mimo(self._log_progress):
                err = "\n".join(self.engine.errors[-3:]) if self.engine.errors else "Unknown error"
                self.after(1000, lambda e=err: self._finish(False, "MiMo Installation Failed",
                    f"Failed to install MiMo.\n\nDetails: {e}\n\nFix: Check your internet connection, then click Retry.",
                    phase="MiMo Installation"))
                return
            self._set_progress(70, "Validating installation...")
            self._log_progress("\nValidating...")
            passed, total = self.engine.validate(self._log_progress)
            self._log_progress(f"Checks passed: {passed}/{total}")
            self._set_progress(85, "Launching MiMo...")
            self._log_progress("\nStarting MiMo web server...")
            port = find_port(3000, 4096)
            launched, actual_port = self.engine.launch(self._log_progress, port)
            self._set_progress(95, "Saving logs...")
            self.engine.save_report()
            self.engine.save_log()
            self._set_progress(100, "Complete")
            time.sleep(0.3)
            if launched:
                self.complete_subtitle.configure(
                    text=f"\U0001f680 MiMo is ready! Opening browser to http://localhost:{actual_port}...")
                self.after(500, lambda: self._finish(True, "Installation Complete", phase="Complete"))
            else:
                self.complete_subtitle.configure(
                    text="MiMo was installed but the web server didn't start automatically.")
                self.after(500, lambda: self._finish(True, "Installed with Warnings"))
        except Exception as e:
            self._log_progress(f"\nError: {e}")
            self.after(1000, lambda err=str(e): self._finish(False, "Installation Failed",
                f"An unexpected error occurred.\n\nDetails: {err}\n\nFix: Try running as administrator, or click Retry.",
                phase="Unexpected Error"))

    def _launch_mimo(self):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        port = self.engine.summary['port'] or 3000
        try:
            subprocess.Popen(
                ["cmd", "/c", "mimo", "web", "--port", str(port)],
                cwd=os.path.join(os.path.expanduser("~"), "Documents", "Mimo Projects"),
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            time.sleep(3)
            webbrowser.open(f"http://localhost:{port}")
        except Exception:
            pass


if __name__ == "__main__":
    if PREFLIGHT:
        print("\n  MiMo Pre-Flight Check\n")
        print("  " + "=" * 40)
        major, minor, build = get_windows_version()
        print(f"  OS:       Windows {major}.{minor} Build {build}")
        print(f"  Admin:    {'Yes' if is_admin() else 'No'}")
        print(f"  Internet: {'Connected' if check_internet() else 'Disconnected'}")
        disk_ok, free_gb = check_disk_space()
        print(f"  Disk:     {free_gb:.1f} GB free")
        for key, dep in DEPENDENCIES.items():
            if dep["check"]:
                ok, out, _ = run_cmd(dep["check"])
                print(f"  {dep['name']}: {'Found' if ok else 'Missing'}")
        print("  " + "=" * 40)
        input("\n  Press Enter to close...")
    else:
        app = InstallerWindow()
        app.mainloop()
