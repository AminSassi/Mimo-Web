"""
MiMo Model Manager — On-demand model downloads.
Avoids bundling large models in the installer.
"""
import os
import sys
import json
import hashlib
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.version import get_version
from core.models import MODEL_TIERS


MODEL_REGISTRY_URL = "https://releases.mimo.xiaomi.com/models.json"

DEFAULT_MODEL_DIR = os.path.join(os.path.expanduser("~"), "MimoAuto", "models")


class ModelRegistry:
    def __init__(self):
        self.models = []

    @classmethod
    def from_url(cls, url=MODEL_REGISTRY_URL, timeout=10):
        registry = cls()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"MiMo-ModelManager/{get_version()}"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
                registry.models = data.get("models", [])
        except Exception:
            pass
        return registry

    def filter_by_tier(self, tier_name):
        tier = MODEL_TIERS.get(tier_name)
        if not tier:
            return []
        return [m for m in self.models if m.get("tier") == tier_name]

    def filter_by_vram(self, total_vram_gb, free_vram_gb):
        compatible = []
        for model in self.models:
            tier = MODEL_TIERS.get(model.get("tier", ""), {})
            min_vram = tier.get("min_vram_gb", 999)
            min_free = tier.get("min_free_vram_gb", 999)
            if total_vram_gb >= min_vram and free_vram_gb >= min_free:
                compatible.append(model)
        return compatible

    def find_by_name(self, name):
        for m in self.models:
            if m.get("name", "").lower() == name.lower():
                return m
        return None


class ModelManager:
    def __init__(self, model_dir=None):
        self.model_dir = model_dir or DEFAULT_MODEL_DIR
        os.makedirs(self.model_dir, exist_ok=True)

    def list_installed(self):
        installed = []
        if not os.path.exists(self.model_dir):
            return installed
        for name in os.listdir(self.model_dir):
            model_path = os.path.join(self.model_dir, name)
            if os.path.isdir(model_path):
                manifest = os.path.join(model_path, "model.json")
                if os.path.exists(manifest):
                    with open(manifest) as f:
                        info = json.load(f)
                    info["local_path"] = model_path
                    installed.append(info)
        return installed

    def is_installed(self, model_name):
        model_path = os.path.join(self.model_dir, model_name)
        return os.path.isdir(model_path) and os.path.exists(
            os.path.join(model_path, "model.json")
        )

    def download_model(self, model_info, progress_cb=None):
        name = model_info.get("name", "unknown")
        url = model_info.get("download_url", "")
        if not url:
            return False, "No download URL"

        model_path = os.path.join(self.model_dir, name)
        os.makedirs(model_path, exist_ok=True)

        filename = model_info.get("filename", f"{name}.gguf")
        dest = os.path.join(model_path, filename)

        def report(block, block_size, total_size):
            if progress_cb and total_size > 0:
                pct = min(block * block_size / total_size * 100, 100)
                progress_cb(pct)

        try:
            urllib.request.urlretrieve(url, dest, reporthook=report)
        except Exception as e:
            return False, f"Download failed: {e}"

        expected_hash = model_info.get("sha256")
        if expected_hash:
            if not self._verify_hash(dest, expected_hash):
                return False, "SHA-256 verification failed"

        manifest = {
            "name": name,
            "tier": model_info.get("tier", "unknown"),
            "size_gb": model_info.get("size_gb", 0),
            "sha256": expected_hash or "",
            "download_url": url,
            "installed_at": __import__("datetime").datetime.now().isoformat(),
            "version": get_version(),
        }
        with open(os.path.join(model_path, "model.json"), "w") as f:
            json.dump(manifest, f, indent=2)

        return True, model_path

    def delete_model(self, model_name):
        model_path = os.path.join(self.model_dir, model_name)
        if os.path.exists(model_path):
            import shutil
            shutil.rmtree(model_path)
            return True
        return False

    def get_model_path(self, model_name):
        model_path = os.path.join(self.model_dir, model_name)
        if os.path.isdir(model_path):
            for f in os.listdir(model_path):
                if f.endswith((".gguf", ".bin", ".safetensors")):
                    return os.path.join(model_path, f)
        return None

    def get_disk_usage(self):
        total = 0
        for name in os.listdir(self.model_dir):
            model_path = os.path.join(self.model_dir, name)
            if os.path.isdir(model_path):
                for f in os.listdir(model_path):
                    fp = os.path.join(model_path, f)
                    if os.path.isfile(fp):
                        total += os.path.getsize(fp)
        return total / (1024**3)

    def _verify_hash(self, filepath, expected):
        try:
            h = hashlib.sha256()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest().lower() == expected.lower()
        except Exception:
            return False
