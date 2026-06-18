"""
MiMo Release Pipeline — Generates online/offline installers, SHA256SUMS, release notes.
"""
import os
import sys
import json
import hashlib
import shutil
import subprocess
import time
from datetime import datetime

SCRIPT_DIR = os.path.dirname(__file__)
BUILD_DIR = os.path.join(SCRIPT_DIR, "build")
RELEASES_DIR = os.path.join(SCRIPT_DIR, "releases")


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


def update_version():
    version = get_version()
    version["git_commit"] = get_git_commit()
    vpath = os.path.join(SCRIPT_DIR, "config", "version.json")
    with open(vpath, "w") as f:
        json.dump(version, f, indent=2)

    for subdir in ["core", "bootstrapper", "launcher"]:
        dest = os.path.join(SCRIPT_DIR, subdir, "version.json")
        with open(dest, "w") as f:
            json.dump(version, f, indent=2)

    return version


def file_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def build_online(version):
    print("  [1/5] Building online installer...")
    cmd = [sys.executable, "build_installer.py"]
    result = subprocess.run(cmd, cwd=SCRIPT_DIR, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"    FAILED: {result.stderr[-300:]}")
        return False
    print("    Done")
    return True


def build_offline_bundler(version):
    print("  [2/5] Creating offline bundle...")
    offline_dir = os.path.join(BUILD_DIR, "offline")
    os.makedirs(offline_dir, exist_ok=True)

    manifest = {
        "type": "offline_bundle",
        "version": version["version"],
        "build_number": version["build_number"],
        "build_date": version["build_date"],
        "git_commit": version["git_commit"],
        "created_at": datetime.now().isoformat(),
        "contents": [],
    }

    pytorch_wheel = os.path.join(offline_dir, "wheels")
    os.makedirs(pytorch_wheel, exist_ok=True)

    print("    Downloading PyTorch wheel...")
    pytorch_url = "https://download.pytorch.org/whl/cu118/torch-2.1.2%2Bcu118-cp310-cp310-win_amd64.whl"
    wheel_file = os.path.join(pytorch_wheel, "torch-2.1.2+cu118.whl")
    try:
        urllib.request.urlretrieve(pytorch_url, wheel_file)
        manifest["contents"].append({"name": "PyTorch", "file": "wheels/torch-2.1.2+cu118.whl"})
        print("    PyTorch downloaded")
    except Exception as e:
        print(f"    PyTorch download failed: {e}")
        print("    Continuing without bundled PyTorch...")

    for pkg_name in ["transformers", "accelerate"]:
        print(f"    Downloading {pkg_name} wheel...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "download", pkg_name, "-d", pytorch_wheel, "--no-deps"],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                manifest["contents"].append({"name": pkg_name, "file": f"wheels/{pkg_name}"})
                print(f"    {pkg_name} downloaded")
        except Exception:
            print(f"    {pkg_name} download failed")

    manifest_path = os.path.join(offline_dir, "offline_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print("    Done")
    return True


def generate_checksums(version):
    print("  [3/5] Generating SHA256SUMS.txt...")
    sums_path = os.path.join(BUILD_DIR, "SHA256SUMS.txt")
    lines = []

    for root, dirs, files in os.walk(BUILD_DIR):
        for f in files:
            if f.endswith((".exe", ".cmd", ".txt", ".json", ".zip")):
                fp = os.path.join(root, f)
                rel = os.path.relpath(fp, BUILD_DIR)
                try:
                    sha = file_sha256(fp)
                    lines.append(f"{sha}  {rel}")
                except Exception:
                    pass

    with open(sums_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"    {len(lines)} checksums written")
    return True


def generate_release_notes(version):
    print("  [4/5] Generating release_notes.md...")
    notes_path = os.path.join(BUILD_DIR, "release_notes.md")
    notes = f"""# MiMo Auto v{version['version']}

**Build:** {version['build_number']}
**Date:** {version['build_date']}
**Commit:** {version['git_commit']}

## What's New

- Structured JSON logging with session IDs
- Version visibility across all components
- Transaction-based rollback support
- GPU inference smoke test
- Model-aware VRAM recommendations
- Auto-updater with GPU compatibility checks
- Model manager for on-demand downloads
- Offline installer bundle
- Release pipeline with SHA256 checksums

## System Requirements

- Windows 10/11 (64-bit)
- NVIDIA GPU with 4GB+ VRAM
- NVIDIA driver 522.00+
- Internet connection (online installer only)

## Installation

1. Run `MiMoSetup.exe` as Administrator
2. Follow the installer prompts
3. MiMo will auto-detect and install dependencies

## Verification

Verify download integrity:
```
sha256sum -c SHA256SUMS.txt
```
"""
    with open(notes_path, "w") as f:
        f.write(notes)

    print("    Done")
    return True


def create_release_archive(version):
    print("  [5/5] Creating release archive...")
    release_name = f"MiMo_{version['version']}_build{version['build_number']}"
    release_dir = os.path.join(RELEASES_DIR, release_name)
    os.makedirs(release_dir, exist_ok=True)

    for f in ["MiMoSetup.exe", "preflight.cmd", "SHA256SUMS.txt",
              "release_notes.md", "mimo.ico"]:
        src = os.path.join(BUILD_DIR, f)
        if os.path.exists(src):
            shutil.copy2(src, release_dir)

    dist_dir = os.path.join(BUILD_DIR, "dist")
    if os.path.exists(os.path.join(dist_dir, "MiMoInstaller.exe")):
        shutil.copy2(os.path.join(dist_dir, "MiMoInstaller.exe"), release_dir)

    zip_path = os.path.join(RELEASES_DIR, f"{release_name}.zip")
    shutil.make_archive(zip_path.replace(".zip", ""), "zip", release_dir)

    print(f"    Archive: {zip_path}")
    return True


def main():
    version = update_version()

    print("=" * 55)
    print(f"  MiMo Release Pipeline — v{version['version']} ({version['git_commit']})")
    print("=" * 55)
    print()

    start = time.time()

    os.makedirs(BUILD_DIR, exist_ok=True)
    os.makedirs(RELEASES_DIR, exist_ok=True)

    ok1 = build_online(version)
    ok2 = build_offline_bundler(version)
    ok3 = generate_checksums(version)
    ok4 = generate_release_notes(version)
    ok5 = create_release_archive(version)

    elapsed = time.time() - start

    print()
    print("=" * 55)
    if all([ok1, ok2, ok3, ok4, ok5]):
        print(f"  Release COMPLETE — v{version['version']} ({elapsed:.1f}s)")
        print()
        print("  Output:")
        print(f"    {BUILD_DIR}\\SHA256SUMS.txt")
        print(f"    {BUILD_DIR}\\release_notes.md")
        print(f"    {BUILD_DIR}\\offline\\offline_manifest.json")
        print(f"    {RELEASES_DIR}\\MiMo_{version['version']}\\")
    else:
        print("  Release FAILED — check errors above")
    print("=" * 55)


if __name__ == "__main__":
    import urllib.request
    main()
