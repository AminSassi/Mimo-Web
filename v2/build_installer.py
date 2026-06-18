"""
MiMo Installer v2.1 — Build Script
Injects version from config/version.json into all builds.
"""
import os
import sys
import json
import subprocess
import shutil
import time

BUILD_DIR = os.path.join(os.path.dirname(__file__), "build")
DIST_DIR = os.path.join(BUILD_DIR, "dist")
BOOTSTRAPPER_DIR = os.path.join(BUILD_DIR, "bootstrapper")

SCRIPT_DIR = os.path.dirname(__file__)


def get_version():
    vpath = os.path.join(SCRIPT_DIR, "config", "version.json")
    if os.path.exists(vpath):
        with open(vpath) as f:
            return json.load(f)
    return {"version": "2.0.0", "build_number": "unknown", "build_date": "unknown", "git_commit": "dev"}


def get_git_commit():
    try:
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "dev"


def update_version_json():
    version = get_version()
    commit = get_git_commit()
    version["git_commit"] = commit

    for target_dir in [os.path.join(SCRIPT_DIR, "core"),
                       os.path.join(SCRIPT_DIR, "bootstrapper"),
                       os.path.join(SCRIPT_DIR, "launcher")]:
        dest = os.path.join(target_dir, "version.json")
        with open(dest, "w") as f:
            json.dump(version, f, indent=2)

    vpath = os.path.join(SCRIPT_DIR, "config", "version.json")
    with open(vpath, "w") as f:
        json.dump(version, f, indent=2)

    return version


def clean():
    print("[1/6] Cleaning build directory...")
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    os.makedirs(BUILD_DIR, exist_ok=True)
    os.makedirs(DIST_DIR, exist_ok=True)
    os.makedirs(BOOTSTRAPPER_DIR, exist_ok=True)
    print("  Done")


EXCLUDE_MODULES = [
    "torch", "torchvision", "torchaudio",
    "scipy", "numpy", "pandas",
    "matplotlib", "PIL", "cv2",
    "transformers", "accelerate", "sentencepiece",
    "timm", "einops", "safetensors",
    "gradio", "tensorboard",
    "tkinter", "customtkinter",
]


def build_bootstrapper(version):
    print("[2/6] Building MiMoBootstrapper.exe...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "MiMoBootstrapper",
        "--distpath", BOOTSTRAPPER_DIR,
        "--workpath", os.path.join(BUILD_DIR, "build_bootstrapper"),
        "--specpath", BUILD_DIR,
        "--clean",
        "--noconfirm",
        "--paths", SCRIPT_DIR,
    ]
    for mod in EXCLUDE_MODULES:
        cmd.extend(["--exclude-module", mod])
    cmd.append(os.path.join(SCRIPT_DIR, "bootstrapper", "MiMoBootstrapper.py"))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FAILED:\n{result.stderr[-500:]}")
        return False
    print(f"  Done (v{version['version']})")
    return True


def build_launcher(version):
    print("[3/6] Building mimo_launch.exe...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "mimo_launch",
        "--distpath", DIST_DIR,
        "--workpath", os.path.join(BUILD_DIR, "build_launcher"),
        "--specpath", BUILD_DIR,
        "--clean",
        "--noconfirm",
        "--paths", SCRIPT_DIR,
    ]
    for mod in EXCLUDE_MODULES:
        cmd.extend(["--exclude-module", mod])
    cmd.append(os.path.join(SCRIPT_DIR, "launcher", "mimo_launch.py"))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FAILED:\n{result.stderr[-500:]}")
        return False
    print(f"  Done (v{version['version']})")
    return True


def build_gui(version):
    print("[4/6] Building MiMoInstaller.exe (GUI)...")
    GUI_EXCLUDES = [m for m in EXCLUDE_MODULES if m not in ("tkinter", "customtkinter", "PIL")]
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "MiMoInstaller",
        "--distpath", DIST_DIR,
        "--workpath", os.path.join(BUILD_DIR, "build_gui"),
        "--specpath", BUILD_DIR,
        "--clean",
        "--noconfirm",
        "--hidden-import", "customtkinter",
        "--hidden-import", "core",
        "--paths", SCRIPT_DIR,
    ]
    for mod in GUI_EXCLUDES:
        cmd.extend(["--exclude-module", mod])
    cmd.append(os.path.join(SCRIPT_DIR, "mimo_installer_v2.py"))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FAILED:\n{result.stderr[-500:]}")
        return False
    print(f"  Done (v{version['version']})")
    return True


def copy_assets(version):
    print("[5/6] Copying assets...")
    for src_name in ["preflight.cmd", "MiMoSetup.iss"]:
        src = os.path.join(SCRIPT_DIR, src_name)
        dst = os.path.join(BUILD_DIR, src_name)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"  {src_name} copied")

    version_out = os.path.join(BUILD_DIR, "version.json")
    with open(version_out, "w") as f:
        json.dump(version, f, indent=2)
    print("  version.json copied")

    ico_src = os.path.join(SCRIPT_DIR, "mimo.ico")
    if os.path.exists(ico_src):
        shutil.copy2(ico_src, os.path.join(BUILD_DIR, "mimo.ico"))
        print("  mimo.ico copied")

    print("  Done")


def build_inno():
    print("[6/6] Building MiMoSetup.exe with Inno Setup...")
    iscc = None
    for p in [r"C:\Program Files (x86)\Inno Setup 6\iscc.exe",
              r"C:\Program Files\Inno Setup 6\iscc.exe"]:
        if os.path.exists(p):
            iscc = p
            break
    if not iscc:
        print("  SKIPPED — Inno Setup not found")
        return True

    iss_path = os.path.join(BUILD_DIR, "MiMoSetup.iss")
    if not os.path.exists(iss_path):
        print("  SKIPPED — MiMoSetup.iss not found")
        return True

    result = subprocess.run([iscc, iss_path], capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"  FAILED:\n{result.stdout[-500:]}")
        return False
    print("  Done")
    return True


def main():
    version = update_version_json()

    print("=" * 55)
    print(f"  MiMo Installer Build — v{version['version']} ({version['git_commit']})")
    print("=" * 55)
    print()

    start = time.time()

    clean()
    ok1 = build_bootstrapper(version)
    ok2 = build_launcher(version)
    ok3 = build_gui(version)
    copy_assets(version)
    ok4 = build_inno()

    elapsed = time.time() - start

    print()
    print("=" * 55)
    if all([ok1, ok2, ok3, ok4]):
        print(f"  Build SUCCESS — v{version['version']} ({elapsed:.1f}s)")
        print()
        print("  Output files:")
        for f in ["bootstrapper\\MiMoBootstrapper.exe", "dist\\mimo_launch.exe",
                   "dist\\MiMoInstaller.exe", "build\\MiMoSetup.exe",
                   "preflight.cmd", "version.json"]:
            print(f"    {BUILD_DIR}\\{f}")
    else:
        print("  Build FAILED — check errors above")
    print("=" * 55)


if __name__ == "__main__":
    main()
