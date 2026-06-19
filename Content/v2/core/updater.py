"""
MiMo Auto-Updater — Version manifest, GPU-aware updates, rollback on failure.
Supports stable/beta/nightly channels.
"""
import os
import sys
import json
import hashlib
import urllib.request
import subprocess
import shutil
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.version import get_version
from core.logger import MiMoLogger
from core.gpu import check_compatibility


MANIFEST_URL = "https://releases.mimo.xiaomi.com/manifest.json"
MANIFEST_LOCAL = "update_manifest.json"
UPDATE_DIR = "updates"


class UpdateManifest:
    def __init__(self, data=None):
        self.data = data or {}

    @classmethod
    def from_url(cls, url=MANIFEST_URL, timeout=10):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"MiMo-AutoUpdater/{get_version()}"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
                return cls(data)
        except Exception:
            return cls(None)

    @classmethod
    def from_file(cls, path):
        if os.path.exists(path):
            with open(path) as f:
                return cls(json.load(f))
        return cls(None)

    @property
    def available(self):
        return bool(self.data and "version" in self.data)

    @property
    def version(self):
        return self.data.get("version", "")

    @property
    def channel(self):
        return self.data.get("channel", "stable")

    @property
    def download_url(self):
        return self.data.get("download_url", "")

    @property
    def sha256(self):
        return self.data.get("sha256", "")

    @property
    def min_driver(self):
        return self.data.get("minimum_driver", 0)

    @property
    def min_vram_gb(self):
        return self.data.get("minimum_vram_gb", 4)

    @property
    def release_notes(self):
        return self.data.get("release_notes", "")

    @property
    def file_size_mb(self):
        return self.data.get("file_size_mb", 0)

    def save(self, path):
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.data, f, indent=2)

    def to_dict(self):
        return self.data.copy()


class AutoUpdater:
    def __init__(self, install_dir, logger=None):
        self.install_dir = install_dir
        self.log = logger or MiMoLogger("updater", install_dir, get_version())
        self.current_version = get_version()
        self.update_dir = os.path.join(install_dir, UPDATE_DIR)
        os.makedirs(self.update_dir, exist_ok=True)

    def check_for_updates(self, channel="stable", timeout=10):
        self.log.step_start("check_update")
        manifest = UpdateManifest.from_url(timeout=timeout)
        if not manifest.available:
            self.log.info("No update manifest available")
            return None

        if manifest.channel != channel:
            self.log.info(f"Manifest channel '{manifest.channel}' != requested '{channel}'")
            return None

        if self._version_compare(manifest.version, self.current_version) <= 0:
            self.log.info(f"Already on latest version: {self.current_version}")
            return None

        self.log.info(f"Update available: {manifest.version} (current: {self.current_version})",
                      event="update_available")
        return manifest

    def check_gpu_compatibility(self, manifest):
        self.log.step_start("check_gpu_compat")
        if manifest.min_driver > 0 or manifest.min_vram_gb > 0:
            result = check_compatibility("2.1.x")
            gpu = result.get("selected_gpu")
            if gpu:
                try:
                    driver_num = float(gpu["driver_version"].split(".")[0])
                    if manifest.min_driver > 0 and driver_num < manifest.min_driver:
                        self.log.error(
                            f"Driver too old for update: {gpu['driver_version']} < {manifest.min_driver}",
                            event="update_blocked_driver"
                        )
                        return False, f"Driver {gpu['driver_version']} too old. Need {manifest.min_driver}+."
                except Exception:
                    pass

                if manifest.min_vram_gb > 0 and gpu["vram_total_gb"] < manifest.min_vram_gb:
                    self.log.error(
                        f"VRAM too low for update: {gpu['vram_total_gb']}GB < {manifest.min_vram_gb}GB",
                        event="update_blocked_vram"
                    )
                    return False, f"VRAM {gpu['vram_total_gb']}GB too low. Need {manifest.min_vram_gb}GB+."

        self.log.info("GPU compatible with update", event="gpu_compat_ok")
        return True, ""

    def download_update(self, manifest, progress_cb=None):
        self.log.step_start("download_update")
        url = manifest.download_url
        if not url:
            self.log.error("No download URL in manifest")
            return False, ""

        filename = f"MiMo_{manifest.version}.exe"
        dest = os.path.join(self.update_dir, filename)

        def report(block, block_size, total_size):
            if progress_cb and total_size > 0:
                pct = min(block * block_size / total_size * 100, 100)
                progress_cb(pct)

        try:
            urllib.request.urlretrieve(url, dest, reporthook=report)
        except Exception as e:
            self.log.error(f"Download failed: {e}", event="download_failed")
            return False, ""

        if manifest.sha256:
            if not self._verify_sha256(dest, manifest.sha256):
                self.log.error("SHA-256 verification failed", event="sha256_failed")
                try:
                    os.remove(dest)
                except Exception:
                    pass
                return False, ""

        self.log.info(f"Download complete: {filename}", event="download_complete")
        return True, dest

    def apply_update(self, installer_path, progress_cb=None):
        self.log.step_start("apply_update")
        try:
            if progress_cb:
                progress_cb("Applying update...")
            result = subprocess.run(
                [installer_path, "/SILENT", "/NORESTART"],
                capture_output=True, timeout=600,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            if result.returncode == 0:
                self.log.info("Update applied successfully", event="update_applied")
                return True
            else:
                self.log.error(f"Installer exit code: {result.returncode}",
                               event="update_failed")
                return False
        except Exception as e:
            self.log.error(f"Update failed: {e}", event="update_failed")
            return False

    def post_update_validation(self):
        self.log.step_start("post_update_validation")
        from core.gpu import run_inference_smoke_test
        smoke = run_inference_smoke_test(0)
        if not smoke["passed"]:
            self.log.error(f"Post-update smoke test failed: {smoke.get('error')}",
                           event="post_update_smoke_failed")
            return False
        self.log.info(f"Post-update smoke test passed ({smoke['elapsed_ms']}ms)",
                      event="post_update_smoke_ok")
        return True

    def rollback_update(self, backup_path=None):
        self.log.step_start("rollback_update")
        if backup_path and os.path.exists(backup_path):
            try:
                subprocess.run(
                    [backup_path, "/SILENT", "/NORESTART"],
                    capture_output=True, timeout=600,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
                self.log.info("Rollback complete", event="rollback_complete")
                return True
            except Exception as e:
                self.log.error(f"Rollback failed: {e}", event="rollback_failed")
        return False

    def save_manifest(self, manifest):
        path = os.path.join(self.install_dir, MANIFEST_LOCAL)
        manifest.save(path)

    def load_local_manifest(self):
        path = os.path.join(self.install_dir, MANIFEST_LOCAL)
        return UpdateManifest.from_file(path)

    def _verify_sha256(self, filepath, expected):
        try:
            h = hashlib.sha256()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest().lower() == expected.lower()
        except Exception:
            return False

    def _version_compare(self, v1, v2):
        try:
            p1 = [int(x) for x in v1.split(".") if x.isdigit()]
            p2 = [int(x) for x in v2.split(".") if x.isdigit()]
            for a, b in zip(p1, p2):
                if a != b:
                    return a - b
            return len(p1) - len(p2)
        except Exception:
            return 0
