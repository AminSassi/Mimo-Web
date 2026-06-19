"""
MiMo Manifest Signing — HMAC-SHA256 for update manifests.
Provides integrity + authenticity without external CA.
For full code signing, use Authenticode certificates.
"""
import os
import sys
import json
import hashlib
import hmac
import secrets

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DEFAULT_KEY_FILE = "update_key.json"


class ManifestSigner:
    def __init__(self, key=None):
        self.key = key or self._generate_key()

    def _generate_key(self):
        return secrets.token_hex(32)

    def sign(self, manifest_data):
        """Sign a manifest dict, return signed version with signature."""
        payload = json.dumps(manifest_data, sort_keys=True, separators=(",", ":"))
        signature = hmac.new(
            self.key.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        signed = dict(manifest_data)
        signed["_signature"] = signature
        signed["_signed"] = True
        return signed

    def verify(self, signed_manifest):
        """Verify manifest signature. Returns True if valid."""
        if not signed_manifest.get("_signed"):
            return False
        signature = signed_manifest.get("_signature", "")
        payload_data = {k: v for k, v in signed_manifest.items()
                        if not k.startswith("_")}
        payload = json.dumps(payload_data, sort_keys=True, separators=(",", ":"))
        expected = hmac.new(
            self.key.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected)

    def save_key(self, path):
        with open(path, "w") as f:
            json.dump({"key": self.key}, f)

    @classmethod
    def load_key(cls, path):
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            return cls(key=data.get("key", ""))
        return cls()

    def sign_file(self, filepath):
        """Sign a file's contents."""
        with open(filepath, "rb") as f:
            content = f.read()
        return hmac.new(
            self.key.encode(), content, hashlib.sha256
        ).hexdigest()

    def verify_file(self, filepath, expected_signature):
        """Verify a file's signature."""
        actual = self.sign_file(filepath)
        return hmac.compare_digest(actual, expected_signature)
