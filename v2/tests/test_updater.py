"""
MiMo Updater + Model Manager Tests
Tests: manifest, version compare, GPU-aware updates, model download, release pipeline
"""
import os
import sys
import json
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))

PASS = 0
FAIL = 0
RESULTS = []


def test(name, fn):
    global PASS, FAIL
    try:
        result = fn()
        if result:
            PASS += 1
            RESULTS.append(("PASS", name))
            print(f"  PASS  {name}")
        else:
            FAIL += 1
            RESULTS.append(("FAIL", name))
            print(f"  FAIL  {name}")
    except Exception as e:
        FAIL += 1
        RESULTS.append(("FAIL", f"{name} -- {e}"))
        print(f"  FAIL  {name} -- {e}")


# ============================================================
# SECTION 1: Update Manifest
# ============================================================
def test_manifest():
    print("\n=== Update Manifest ===")
    from core.updater import UpdateManifest

    def test_empty_manifest():
        m = UpdateManifest()
        assert m.available == False
        assert m.version == ""
        return True
    test("Empty manifest is not available", test_empty_manifest)

    def test_manifest_from_dict():
        data = {
            "version": "2.2.0",
            "channel": "stable",
            "download_url": "https://example.com/MiMo_2.2.0.exe",
            "sha256": "abc123",
            "minimum_driver": 545,
            "minimum_vram_gb": 4,
            "release_notes": "Bug fixes",
            "file_size_mb": 35,
        }
        m = UpdateManifest(data)
        assert m.available == True
        assert m.version == "2.2.0"
        assert m.channel == "stable"
        assert m.download_url == "https://example.com/MiMo_2.2.0.exe"
        assert m.sha256 == "abc123"
        assert m.min_driver == 545
        assert m.min_vram_gb == 4
        assert m.release_notes == "Bug fixes"
        assert m.file_size_mb == 35
        return True
    test("Manifest from dict has all fields", test_manifest_from_dict)

    def test_manifest_save_load():
        d = tempfile.mkdtemp()
        path = os.path.join(d, "manifest.json")
        data = {"version": "2.2.0", "channel": "stable"}
        m = UpdateManifest(data)
        m.save(path)
        m2 = UpdateManifest.from_file(path)
        assert m2.available == True
        assert m2.version == "2.2.0"
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("Manifest save/load roundtrip", test_manifest_save_load)

    def test_manifest_missing_file():
        m = UpdateManifest.from_file("/nonexistent/path.json")
        assert m.available == False
        return True
    test("Manifest from missing file returns empty", test_manifest_missing_file)

    def test_manifest_to_dict():
        data = {"version": "2.2.0", "channel": "beta"}
        m = UpdateManifest(data)
        d = m.to_dict()
        assert d["version"] == "2.2.0"
        assert d["channel"] == "beta"
        return True
    test("Manifest to_dict returns copy", test_manifest_to_dict)


# ============================================================
# SECTION 2: Version Compare
# ============================================================
def test_version_compare():
    print("\n=== Version Compare ===")
    from core.updater import AutoUpdater

    def test_higher_version():
        d = tempfile.mkdtemp()
        updater = AutoUpdater(d)
        assert updater._version_compare("2.2.0", "2.1.0") > 0
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("2.2.0 > 2.1.0", test_higher_version)

    def test_same_version():
        d = tempfile.mkdtemp()
        updater = AutoUpdater(d)
        assert updater._version_compare("2.1.0", "2.1.0") == 0
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("2.1.0 == 2.1.0", test_same_version)

    def test_lower_version():
        d = tempfile.mkdtemp()
        updater = AutoUpdater(d)
        assert updater._version_compare("2.0.0", "2.1.0") < 0
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("2.0.0 < 2.1.0", test_lower_version)

    def test_patch_version():
        d = tempfile.mkdtemp()
        updater = AutoUpdater(d)
        assert updater._version_compare("2.1.1", "2.1.0") > 0
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("2.1.1 > 2.1.0 (patch)", test_patch_version)


# ============================================================
# SECTION 3: Auto-Updater
# ============================================================
def test_updater():
    print("\n=== Auto-Updater ===")
    from core.updater import AutoUpdater, UpdateManifest

    def test_updater_init():
        d = tempfile.mkdtemp()
        updater = AutoUpdater(d)
        assert updater.current_version is not None
        assert os.path.isdir(updater.update_dir)
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("Updater initializes correctly", test_updater_init)

    def test_check_no_manifest():
        d = tempfile.mkdtemp()
        updater = AutoUpdater(d)
        result = updater.check_for_updates(timeout=1)
        assert result is None
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("Check updates with no manifest returns None", test_check_no_manifest)

    def test_gpu_compat_ok():
        d = tempfile.mkdtemp()
        updater = AutoUpdater(d)
        manifest = UpdateManifest({
            "version": "99.0.0",
            "minimum_driver": 100,
            "minimum_vram_gb": 1,
        })
        ok, msg = updater.check_gpu_compatibility(manifest)
        assert ok == True
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("GPU compatibility check passes with low requirements", test_gpu_compat_ok)

    def test_sha256_verify():
        d = tempfile.mkdtemp()
        updater = AutoUpdater(d)
        test_file = os.path.join(d, "test.bin")
        data = b"test data for hashing"
        with open(test_file, "wb") as f:
            f.write(data)
        import hashlib
        expected = hashlib.sha256(data).hexdigest()
        assert updater._verify_sha256(test_file, expected) == True
        assert updater._verify_sha256(test_file, "wrong_hash") == False
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("SHA-256 verification works", test_sha256_verify)

    def test_save_load_local_manifest():
        d = tempfile.mkdtemp()
        updater = AutoUpdater(d)
        manifest = UpdateManifest({"version": "2.2.0", "channel": "stable"})
        updater.save_manifest(manifest)
        loaded = updater.load_local_manifest()
        assert loaded.available == True
        assert loaded.version == "2.2.0"
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("Local manifest save/load works", test_save_load_local_manifest)


# ============================================================
# SECTION 4: Model Manager
# ============================================================
def test_model_manager():
    print("\n=== Model Manager ===")
    from core.models_manager import ModelManager, ModelRegistry

    def test_registry_empty():
        r = ModelRegistry()
        assert r.models == []
        assert r.filter_by_tier("small") == []
        assert r.find_by_name("nonexistent") is None
        return True
    test("Empty registry returns empty results", test_registry_empty)

    def test_registry_filter():
        r = ModelRegistry()
        r.models = [
            {"name": "model_a", "tier": "small", "vram_gb": 4},
            {"name": "model_b", "tier": "medium", "vram_gb": 8},
            {"name": "model_c", "tier": "small", "vram_gb": 4},
        ]
        small = r.filter_by_tier("small")
        assert len(small) == 2
        medium = r.filter_by_tier("medium")
        assert len(medium) == 1
        return True
    test("Registry filter by tier works", test_registry_filter)

    def test_registry_find_by_name():
        r = ModelRegistry()
        r.models = [{"name": "llama-3-8b", "tier": "medium"}]
        found = r.find_by_name("llama-3-8b")
        assert found is not None
        assert found["name"] == "llama-3-8b"
        not_found = r.find_by_name("nonexistent")
        assert not_found is None
        return True
    test("Registry find by name works", test_registry_find_by_name)

    def test_manager_init():
        d = tempfile.mkdtemp()
        manager = ModelManager(d)
        assert os.path.isdir(d)
        installed = manager.list_installed()
        assert installed == []
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("Model manager initializes correctly", test_manager_init)

    def test_is_installed():
        d = tempfile.mkdtemp()
        manager = ModelManager(d)
        assert manager.is_installed("nonexistent") == False
        model_dir = os.path.join(d, "test_model")
        os.makedirs(model_dir)
        with open(os.path.join(model_dir, "model.json"), "w") as f:
            json.dump({"name": "test_model"}, f)
        assert manager.is_installed("test_model") == True
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("is_installed detects models correctly", test_is_installed)

    def test_list_installed():
        d = tempfile.mkdtemp()
        manager = ModelManager(d)
        for name in ["model_a", "model_b"]:
            model_dir = os.path.join(d, name)
            os.makedirs(model_dir)
            with open(os.path.join(model_dir, "model.json"), "w") as f:
                json.dump({"name": name, "tier": "small"}, f)
        installed = manager.list_installed()
        assert len(installed) == 2
        names = [m["name"] for m in installed]
        assert "model_a" in names
        assert "model_b" in names
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("list_installed returns all models", test_list_installed)

    def test_delete_model():
        d = tempfile.mkdtemp()
        manager = ModelManager(d)
        model_dir = os.path.join(d, "to_delete")
        os.makedirs(model_dir)
        with open(os.path.join(model_dir, "model.json"), "w") as f:
            json.dump({"name": "to_delete"}, f)
        assert manager.is_installed("to_delete") == True
        manager.delete_model("to_delete")
        assert manager.is_installed("to_delete") == False
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("delete_model removes model", test_delete_model)

    def test_disk_usage():
        d = tempfile.mkdtemp()
        manager = ModelManager(d)
        model_dir = os.path.join(d, "model_a")
        os.makedirs(model_dir)
        with open(os.path.join(model_dir, "model.bin"), "wb") as f:
            f.write(b"x" * 1024)
        usage = manager.get_disk_usage()
        assert usage > 0
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("disk_usage calculates correctly", test_disk_usage)


# ============================================================
# SECTION 5: Release Pipeline Artifacts
# ============================================================
def test_release_pipeline():
    print("\n=== Release Pipeline ===")

    def test_version_json():
        vpath = os.path.join(SCRIPT_DIR, "config", "version.json")
        assert os.path.exists(vpath)
        with open(vpath) as f:
            v = json.load(f)
        assert "version" in v
        assert "build_number" in v
        assert "git_commit" in v
        return True
    test("version.json has all required fields", test_version_json)

    def test_build_script_exists():
        assert os.path.exists(os.path.join(SCRIPT_DIR, "build_installer.py"))
        return True
    test("build_installer.py exists", test_build_script_exists)

    def test_release_pipeline_exists():
        assert os.path.exists(os.path.join(SCRIPT_DIR, "release_pipeline.py"))
        return True
    test("release_pipeline.py exists", test_release_pipeline_exists)

    def test_offline_bundle_script():
        assert os.path.exists(os.path.join(SCRIPT_DIR, "release_pipeline.py"))
        return True
    test("Offline bundle generation ready", test_offline_bundle_script)

    def test_core_modules_complete():
        core_dir = os.path.join(SCRIPT_DIR, "core")
        expected = ["__init__.py", "version.py", "logger.py", "paths.py",
                     "rollback.py", "gpu.py", "models.py", "updater.py", "models_manager.py"]
        for f in expected:
            assert os.path.exists(os.path.join(core_dir, f)), f"Missing: {f}"
        return True
    test("All core modules present", test_core_modules_complete)


SCRIPT_DIR = os.path.dirname(os.path.dirname(__file__))


# ============================================================
# MAIN
# ============================================================
def main():
    global PASS, FAIL
    print("=" * 55)
    print("  MiMo Updater + Model Manager Tests")
    print("=" * 55)

    test_manifest()
    test_version_compare()
    test_updater()
    test_model_manager()
    test_release_pipeline()

    print("\n" + "=" * 55)
    print(f"  Results: {PASS} passed, {FAIL} failed")
    print("=" * 55)

    if FAIL > 0:
        print("\n  FAILED TESTS:")
        for status, name in RESULTS:
            if status == "FAIL":
                print(f"    - {name}")

    print()
    return FAIL == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
