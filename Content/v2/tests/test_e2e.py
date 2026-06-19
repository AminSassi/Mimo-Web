"""
MiMo E2E Update + Release Checklist Tests
Tests: upgrade scenarios, rollback, asset preservation, manifest signing, release checklist
"""
import os
import sys
import json
import tempfile
import shutil
import hashlib
import hmac

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
# SECTION 1: E2E Upgrade Scenarios
# ============================================================
def test_upgrade_scenarios():
    print("\n=== E2E Upgrade Scenarios ===")
    from bootstrapper.MiMoBootstrapper import StateManager
    from core.updater import UpdateManifest, AutoUpdater

    def test_200_to_210():
        d = tempfile.mkdtemp()
        state = StateManager(d)
        state.state["version"] = "2.0.0"
        state.state["deps"]["node"] = {"status": "ok", "version": "v20.15.1"}
        state.state["gpu"] = {"model": "RTX 4060 Ti", "vram_total_gb": 16}
        state.save()
        state2 = StateManager(d)
        assert state2.state["version"] == "2.0.0"
        state2.state["version"] = "2.1.0"
        state2.save()
        state3 = StateManager(d)
        assert state3.state["version"] == "2.1.0"
        assert state3.state["deps"]["node"]["version"] == "v20.15.1"
        assert state3.state["gpu"]["model"] == "RTX 4060 Ti"
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("Upgrade 2.0.0 -> 2.1.0 preserves state", test_200_to_210)

    def test_210_to_211():
        d = tempfile.mkdtemp()
        state = StateManager(d)
        state.state["version"] = "2.1.0"
        state.state["launches"] = 5
        state.state["repair_attempts"] = 1
        state.save()
        state2 = StateManager(d)
        state2.state["version"] = "2.1.1"
        state2.save()
        state3 = StateManager(d)
        assert state3.state["version"] == "2.1.1"
        assert state3.state["launches"] == 5
        assert state3.state["repair_attempts"] == 1
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("Upgrade 2.1.0 -> 2.1.1 preserves counters", test_210_to_211)

    def test_211_to_220():
        d = tempfile.mkdtemp()
        state = StateManager(d)
        state.state["version"] = "2.1.1"
        state.state["deps"]["node"] = {"status": "ok", "version": "v20.15.1"}
        state.state["deps"]["git"] = {"status": "ok", "version": "git 2.45.2"}
        state.state["mimo"] = {"status": "ok", "version": "2.1.0"}
        state.state["gpu"] = {"model": "RTX 4060 Ti", "tier": "excellent"}
        state.save()
        state2 = StateManager(d)
        state2.state["version"] = "2.2.0"
        state2.state["gpu"]["tier"] = "excellent"
        state2.save()
        state3 = StateManager(d)
        assert state3.state["version"] == "2.2.0"
        assert state3.state["deps"]["node"]["status"] == "ok"
        assert state3.state["gpu"]["tier"] == "excellent"
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("Upgrade 2.1.1 -> 2.2.0 preserves GPU info", test_211_to_220)

    def test_stable_to_beta():
        d = tempfile.mkdtemp()
        manifest = UpdateManifest({
            "version": "2.2.0-beta.1",
            "channel": "beta",
            "download_url": "https://example.com/beta.exe",
        })
        assert manifest.channel == "beta"
        assert "beta" in manifest.version
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("Beta manifest has correct channel", test_stable_to_beta)

    def test_failed_download():
        d = tempfile.mkdtemp()
        updater = AutoUpdater(d)
        manifest = UpdateManifest({
            "version": "99.0.0",
            "download_url": "http://localhost:99999/nonexistent.exe",
        })
        ok, path = updater.download_update(manifest)
        assert ok == False
        assert path == ""
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("Failed download returns False", test_failed_download)

    def test_invalid_sha256():
        d = tempfile.mkdtemp()
        updater = AutoUpdater(d)
        test_file = os.path.join(d, "test.bin")
        with open(test_file, "wb") as f:
            f.write(b"test data")
        assert updater._verify_sha256(test_file, "wrong_hash") == False
        correct = hashlib.sha256(b"test data").hexdigest()
        assert updater._verify_sha256(test_file, correct) == True
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("Invalid SHA-256 rejected, valid accepted", test_invalid_sha256)


# ============================================================
# SECTION 2: User Asset Preservation
# ============================================================
def test_asset_preservation():
    print("\n=== User Asset Preservation ===")
    from core.user_assets import UserAssetManager, USER_ASSET_DIRS

    def test_asset_dirs_defined():
        expected = ["models", "projects", "settings", "logs", "sessions", "memory"]
        for name in expected:
            assert name in USER_ASSET_DIRS
            assert "default" in USER_ASSET_DIRS[name]
            assert "preserve_on_update" in USER_ASSET_DIRS[name]
            assert "preserve_on_uninstall" in USER_ASSET_DIRS[name]
        return True
    test("All asset directories defined", test_asset_dirs_defined)

    def test_models_preserved_on_update():
        assert USER_ASSET_DIRS["models"]["preserve_on_update"] == True
        return True
    test("Models preserved on update", test_models_preserved_on_update)

    def test_projects_preserved_on_uninstall():
        assert USER_ASSET_DIRS["projects"]["preserve_on_uninstall"] == True
        return True
    test("Projects preserved on uninstall", test_projects_preserved_on_uninstall)

    def test_logs_not_preserved_on_uninstall():
        assert USER_ASSET_DIRS["logs"]["preserve_on_uninstall"] == False
        return True
    test("Logs not preserved on uninstall", test_logs_not_preserved_on_uninstall)

    def test_asset_manager_init():
        d = tempfile.mkdtemp()
        manager = UserAssetManager(d)
        assets = manager.get_all_assets()
        assert len(assets) == 6
        assert "models" in assets
        assert "projects" in assets
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("Asset manager initializes with all assets", test_asset_manager_init)

    def test_check_preservation_update():
        d = tempfile.mkdtemp()
        manager = UserAssetManager(d)
        for name in ["models", "projects", "logs", "memory"]:
            path = manager.assets[name]["current_path"]
            os.makedirs(path, exist_ok=True)
            manager.assets[name]["exists"] = True
        result = manager.check_preservation("update")
        assert "preserved" in result
        assert "models" in result["preserved"]
        assert "projects" in result["preserved"]
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("Check preservation: update preserves models/projects", test_check_preservation_update)

    def test_backup_restore():
        d = tempfile.mkdtemp()
        manager = UserAssetManager(d)
        models_dir = os.path.join(d, "user_models")
        os.makedirs(models_dir)
        with open(os.path.join(models_dir, "model.bin"), "wb") as f:
            f.write(b"model data")
        manager.assets["models"]["current_path"] = models_dir
        manager.assets["models"]["exists"] = True
        backup_dir = os.path.join(d, "backups")
        os.makedirs(backup_dir)
        ok = manager.backup_asset("models", backup_dir)
        assert ok == True
        assert os.path.exists(os.path.join(backup_dir, "models", "model.bin"))
        shutil.rmtree(models_dir)
        ok = manager.restore_asset("models", backup_dir)
        assert ok == True
        assert os.path.exists(os.path.join(models_dir, "model.bin"))
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("Backup and restore user models works", test_backup_restore)

    def test_disk_usage():
        d = tempfile.mkdtemp()
        manager = UserAssetManager(d)
        test_path = os.path.join(d, "test_models")
        os.makedirs(test_path)
        with open(os.path.join(test_path, "big.bin"), "wb") as f:
            f.write(b"x" * (2 * 1024 * 1024 * 1024))
        manager.assets["models"]["current_path"] = test_path
        manager.assets["models"]["exists"] = True
        usage = manager.get_disk_usage()
        assert usage["models"] >= 2.0
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("Disk usage calculation works", test_disk_usage)

    def test_to_dict():
        d = tempfile.mkdtemp()
        manager = UserAssetManager(d)
        d_dict = manager.to_dict()
        assert "models" in d_dict
        assert "path" in d_dict["models"]
        assert "exists" in d_dict["models"]
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("Asset manager serializes to dict", test_to_dict)


# ============================================================
# SECTION 3: Manifest Signing
# ============================================================
def test_manifest_signing():
    print("\n=== Manifest Signing ===")
    from core.signing import ManifestSigner

    def test_signer_init():
        signer = ManifestSigner()
        assert len(signer.key) == 64
        return True
    test("Signer generates 64-char hex key", test_signer_init)

    def test_sign_verify():
        signer = ManifestSigner()
        manifest = {"version": "2.2.0", "channel": "stable"}
        signed = signer.sign(manifest)
        assert signed["_signature"] is not None
        assert signed["_signed"] == True
        assert signed["version"] == "2.2.0"
        assert signer.verify(signed) == True
        return True
    test("Sign and verify manifest works", test_sign_verify)

    def test_tamper_detection():
        signer = ManifestSigner()
        manifest = {"version": "2.2.0", "sha256": "abc123"}
        signed = signer.sign(manifest)
        signed["version"] = "2.3.0"
        assert signer.verify(signed) == False
        return True
    test("Tampered manifest detected", test_tamper_detection)

    def test_wrong_key():
        signer1 = ManifestSigner()
        signer2 = ManifestSigner()
        manifest = {"version": "2.2.0"}
        signed = signer1.sign(manifest)
        assert signer2.verify(signed) == False
        return True
    test("Wrong key rejects manifest", test_wrong_key)

    def test_save_load_key():
        d = tempfile.mkdtemp()
        key_path = os.path.join(d, "key.json")
        signer1 = ManifestSigner()
        signer1.save_key(key_path)
        signer2 = ManifestSigner.load_key(key_path)
        manifest = {"version": "2.2.0"}
        signed = signer1.sign(manifest)
        assert signer2.verify(signed) == True
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("Key save/load roundtrip works", test_save_load_key)

    def test_sign_file():
        d = tempfile.mkdtemp()
        signer = ManifestSigner()
        test_file = os.path.join(d, "test.bin")
        with open(test_file, "wb") as f:
            f.write(b"file content")
        sig = signer.sign_file(test_file)
        assert len(sig) == 64
        assert signer.verify_file(test_file, sig) == True
        with open(test_file, "ab") as f:
            f.write(b"tampered")
        assert signer.verify_file(test_file, sig) == False
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("File signing and tamper detection works", test_sign_file)

    def test_unsigned_manifest_rejected():
        signer = ManifestSigner()
        unsigned = {"version": "2.2.0"}
        assert signer.verify(unsigned) == False
        return True
    test("Unsigned manifest rejected", test_unsigned_manifest_rejected)


# ============================================================
# SECTION 4: Release Checklist
# ============================================================
def test_release_checklist():
    print("\n=== Release Checklist ===")

    def test_build_script():
        assert os.path.exists(os.path.join(SCRIPT_DIR, "build_installer.py"))
        return True
    test("build_installer.py exists", test_build_script)

    def test_release_pipeline():
        assert os.path.exists(os.path.join(SCRIPT_DIR, "release_pipeline.py"))
        return True
    test("release_pipeline.py exists", test_release_pipeline)

    def test_version_json():
        vpath = os.path.join(SCRIPT_DIR, "config", "version.json")
        assert os.path.exists(vpath)
        with open(vpath) as f:
            v = json.load(f)
        assert "version" in v
        assert "build_number" in v
        assert "build_date" in v
        assert "git_commit" in v
        return True
    test("version.json complete", test_version_json)

    def test_core_modules():
        core_dir = os.path.join(SCRIPT_DIR, "core")
        expected = [
            "__init__.py", "version.py", "logger.py", "paths.py",
            "rollback.py", "gpu.py", "models.py", "updater.py",
            "models_manager.py", "user_assets.py", "signing.py"
        ]
        for f in expected:
            assert os.path.exists(os.path.join(core_dir, f)), f"Missing: {f}"
        return True
    test("All 11 core modules present", test_core_modules)

    def test_test_suites():
        test_dir = os.path.join(SCRIPT_DIR, "tests")
        expected = [
            "test_validation.py", "test_integration.py",
            "test_gpu.py", "test_models.py", "test_updater.py"
        ]
        for f in expected:
            assert os.path.exists(os.path.join(test_dir, f)), f"Missing: {f}"
        return True
    test("All 5 test suites present", test_test_suites)

    def test_preflight():
        assert os.path.exists(os.path.join(SCRIPT_DIR, "preflight.cmd"))
        return True
    test("preflight.cmd exists", test_preflight)

    def test_iss_script():
        assert os.path.exists(os.path.join(SCRIPT_DIR, "MiMoSetup.iss"))
        return True
    test("MiMoSetup.iss exists", test_iss_script)

    def test_config_dir():
        config_dir = os.path.join(SCRIPT_DIR, "config")
        assert os.path.exists(config_dir)
        assert os.path.exists(os.path.join(config_dir, "version.json"))
        return True
    test("config/ directory with version.json", test_config_dir)


SCRIPT_DIR = os.path.dirname(os.path.dirname(__file__))


# ============================================================
# SECTION 5: Rollback Validation
# ============================================================
def test_rollback_validation():
    print("\n=== Rollback Validation ===")
    from core.rollback import RollbackRegistry
    from bootstrapper.MiMoBootstrapper import TransactionManager

    def test_full_rollback_matrix():
        registry = RollbackRegistry()
        actions = [
            "create_install_dir", "install_node", "install_git",
            "add_path_entry", "create_shortcuts", "write_registry_keys",
            "create_state_file", "create_portable_flag", "install_mimo",
        ]
        for action in actions:
            assert registry.has_rollback(action), f"No rollback for: {action}"
        return True
    test("All 9 install actions have rollback handlers", test_full_rollback_matrix)

    def test_transaction_rollback_chain():
        d = tempfile.mkdtemp()
        tx = TransactionManager(d)
        tx.start(["step1", "step2", "step3", "step4"])
        tx.complete_step("step1", rollback_action="delete_dir")
        tx.complete_step("step2", rollback_action="uninstall_node")
        tx.complete_step("step3", rollback_action="uninstall_git")
        failed_steps = tx.fail()
        assert len(failed_steps) == 3
        assert failed_steps == ["step3", "step2", "step1"]
        actions = tx.get_rollback_actions()
        assert "step1" in actions
        assert "step2" in actions
        assert "step3" in actions
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("Transaction rollback chain is correct order", test_transaction_rollback_chain)

    def test_state_preserves_across_simulated_crash():
        from bootstrapper.MiMoBootstrapper import StateManager
        d = tempfile.mkdtemp()
        state1 = StateManager(d)
        state1.state["version"] = "2.1.0"
        state1.state["deps"]["node"] = {"status": "ok", "version": "v20.15.1"}
        state1.state["gpu"] = {"model": "RTX 4060 Ti", "vram_total_gb": 16}
        state1.state["launches"] = 10
        state1.save()
        state2 = StateManager(d)
        assert state2.state["version"] == "2.1.0"
        assert state2.state["deps"]["node"]["version"] == "v20.15.1"
        assert state2.state["gpu"]["model"] == "RTX 4060 Ti"
        assert state2.state["launches"] == 10
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("State survives simulated crash (reload)", test_state_preserves_across_simulated_crash)


# ============================================================
# MAIN
# ============================================================
def main():
    global PASS, FAIL
    print("=" * 55)
    print("  MiMo E2E Update + Release Checklist Tests")
    print("=" * 55)

    test_upgrade_scenarios()
    test_asset_preservation()
    test_manifest_signing()
    test_release_checklist()
    test_rollback_validation()

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
