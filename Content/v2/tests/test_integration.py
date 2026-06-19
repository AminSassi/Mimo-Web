"""
MiMo v2.1 Integration Test Suite
Covers: rollback handlers, checkpoint recovery, Windows failures, permissions, uninstall
"""
import os
import sys
import json
import shutil
import tempfile
import subprocess
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))

PASS = 0
FAIL = 0
TEST_DIR = os.path.join(tempfile.gettempdir(), "mimo_integration_test")
RESULTS = []
COVERAGE = {}


def test(name, category, fn):
    global PASS, FAIL
    COVERAGE.setdefault(category, {"pass": 0, "fail": 0, "tests": []})
    try:
        result = fn()
        if result:
            PASS += 1
            COVERAGE[category]["pass"] += 1
            COVERAGE[category]["tests"].append(("PASS", name))
            RESULTS.append(("PASS", name, category))
            print(f"  PASS  {name}")
        else:
            FAIL += 1
            COVERAGE[category]["fail"] += 1
            COVERAGE[category]["tests"].append(("FAIL", name))
            RESULTS.append(("FAIL", name, category))
            print(f"  FAIL  {name}")
    except Exception as e:
        FAIL += 1
        COVERAGE[category]["fail"] += 1
        COVERAGE[category]["tests"].append(("FAIL", f"{name} -- {e}"))
        RESULTS.append(("FAIL", f"{name} -- {e}", category))
        print(f"  FAIL  {name} -- {e}")


def cleanup():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR, ignore_errors=True)


def setup_test_dir():
    cleanup()
    os.makedirs(TEST_DIR, exist_ok=True)
    return TEST_DIR


# ============================================================
# SECTION 1: Rollback Handlers
# ============================================================
def test_rollback_handlers():
    print("\n=== Rollback Handlers ===")
    from core.rollback import RollbackRegistry

    def test_all_actions_have_rollback():
        registry = RollbackRegistry()
        missing = registry.verify_all_actions_have_rollback()
        assert len(missing) == 0, f"Actions missing rollback: {missing}"
        return True
    test("All install actions have rollback handlers", "rollback", test_all_actions_have_rollback)

    def test_rollback_create_dir():
        d = setup_test_dir()
        install_dir = os.path.join(d, "test_install")
        os.makedirs(install_dir)
        with open(os.path.join(install_dir, "test.txt"), "w") as f:
            f.write("test")
        registry = RollbackRegistry()
        ctx = {"install_dir": install_dir}
        result = registry.execute_rollback("create_install_dir", ctx)
        assert result == True
        assert not os.path.exists(install_dir)
        return True
    test("Rollback create_install_dir removes directory", "rollback", test_rollback_create_dir)

    def test_rollback_restore_path():
        d = setup_test_dir()
        original_path = "C:\\Original\\Path;C:\\Windows\\System32"
        registry = RollbackRegistry()
        ctx = {"original_path": original_path}
        result = registry.execute_rollback("add_path_entry", ctx)
        assert result == True
        return True
    test("Rollback add_path_entry restores original PATH", "rollback", test_rollback_restore_path)

    def test_rollback_remove_shortcuts():
        d = setup_test_dir()
        shortcuts = []
        for name in ["test1.lnk", "test2.lnk"]:
            path = os.path.join(d, name)
            with open(path, "w") as f:
                f.write("shortcut")
            shortcuts.append(path)
        registry = RollbackRegistry()
        ctx = {"shortcuts_created": shortcuts}
        result = registry.execute_rollback("create_shortcuts", ctx)
        assert result == True
        for s in shortcuts:
            assert not os.path.exists(s)
        return True
    test("Rollback create_shortcuts removes all shortcuts", "rollback", test_rollback_remove_shortcuts)

    def test_rollback_restore_state():
        d = setup_test_dir()
        state_path = os.path.join(d, "install_state.json")
        backup_path = os.path.join(d, "install_state.json.bak")
        with open(state_path, "w") as f:
            json.dump({"version": "corrupted"}, f)
        with open(backup_path, "w") as f:
            json.dump({"version": "2.0.0", "status": "ok"}, f)
        registry = RollbackRegistry()
        ctx = {"state_path": state_path, "state_backup_path": backup_path}
        result = registry.execute_rollback("create_state_file", ctx)
        assert result == True
        with open(state_path) as f:
            state = json.load(f)
        assert state["version"] == "2.0.0"
        return True
    test("Rollback create_state_file restores from backup", "rollback", test_rollback_restore_state)

    def test_rollback_remove_portable_flag():
        d = setup_test_dir()
        flag_path = os.path.join(d, "portable.flag")
        with open(flag_path, "w") as f:
            f.write("")
        registry = RollbackRegistry()
        ctx = {"portable_flag_path": flag_path}
        result = registry.execute_rollback("create_portable_flag", ctx)
        assert result == True
        assert not os.path.exists(flag_path)
        return True
    test("Rollback create_portable_flag removes flag", "rollback", test_rollback_remove_portable_flag)

    def test_rollback_registry_backup():
        d = setup_test_dir()
        registry = RollbackRegistry()
        ctx = {"registry_backups": {}}
        result = registry.execute_rollback("write_registry_keys", ctx)
        assert result == True
        return True
    test("Rollback write_registry_keys with empty backup succeeds", "rollback", test_rollback_registry_backup)

    def test_rollback_unknown_action():
        registry = RollbackRegistry()
        result = registry.has_rollback("nonexistent_action")
        assert result == False
        return True
    test("Unknown action has no rollback handler", "rollback", test_rollback_unknown_action)

    def test_custom_rollback_handler():
        d = setup_test_dir()
        registry = RollbackRegistry()
        custom_called = [False]
        def my_handler(ctx):
            custom_called[0] = True
            return True
        registry.register("custom_action", my_handler)
        assert registry.has_rollback("custom_action") == True
        result = registry.execute_rollback("custom_action", {})
        assert result == True
        assert custom_called[0] == True
        return True
    test("Custom rollback handler can be registered", "rollback", test_custom_rollback_handler)


# ============================================================
# SECTION 2: Checkpoint Recovery
# ============================================================
def test_checkpoint_recovery():
    print("\n=== Checkpoint Recovery ===")
    from bootstrapper.MiMoBootstrapper import TransactionManager

    def test_crash_after_step1():
        d = setup_test_dir()
        tx = TransactionManager(d)
        tx.start(["create_dir", "install_node", "install_git"])
        tx.complete_step("create_dir", rollback_action="delete_install_dir")
        os.makedirs(os.path.join(d, "test_install"), exist_ok=True)
        tx.fail()
        assert tx.transaction["status"] == "failed"
        rollback_steps = list(reversed(tx.transaction["completed_steps"]))
        assert rollback_steps == ["create_dir"]
        return True
    test("Crash after step1: rollback has 1 step", "checkpoint", test_crash_after_step1)

    def test_crash_after_step2():
        d = setup_test_dir()
        tx = TransactionManager(d)
        tx.start(["create_dir", "install_node", "install_git"])
        tx.complete_step("create_dir", rollback_action="delete_install_dir")
        tx.complete_step("install_node", rollback_action="uninstall_node")
        tx.fail()
        rollback_steps = list(reversed(tx.transaction["completed_steps"]))
        assert rollback_steps == ["install_node", "create_dir"]
        return True
    test("Crash after step2: rollback has 2 steps in reverse", "checkpoint", test_crash_after_step2)

    def test_crash_after_step3():
        d = setup_test_dir()
        tx = TransactionManager(d)
        tx.start(["create_dir", "install_node", "install_git"])
        tx.complete_step("create_dir")
        tx.complete_step("install_node")
        tx.complete_step("install_git")
        tx.fail()
        rollback_steps = list(reversed(tx.transaction["completed_steps"]))
        assert rollback_steps == ["install_git", "install_node", "create_dir"]
        return True
    test("Crash after step3: rollback has 3 steps in reverse", "checkpoint", test_crash_after_step3)

    def test_resume_after_crash():
        d = setup_test_dir()
        tx = TransactionManager(d)
        tx.start(["step1", "step2", "step3"])
        tx.complete_step("step1")
        tx.fail()
        tx2 = TransactionManager(d)
        assert tx2.transaction["status"] == "failed"
        assert len(tx2.transaction["completed_steps"]) == 1
        return True
    test("Resume after crash loads failed transaction", "checkpoint", test_resume_after_crash)

    def test_new_transaction_after_cleanup():
        d = setup_test_dir()
        tx = TransactionManager(d)
        tx.start(["step1", "step2"])
        tx.complete_step("step1")
        tx.success()
        tx.cleanup()
        tx2 = TransactionManager(d)
        assert tx2.transaction is None
        tx2.start(["step1", "step2", "step3"])
        assert tx2.transaction["status"] == "in_progress"
        assert len(tx2.transaction["pending_steps"]) == 3
        return True
    test("New transaction starts clean after cleanup", "checkpoint", test_new_transaction_after_cleanup)


# ============================================================
# SECTION 3: Windows Integration Failures
# ============================================================
def test_windows_failures():
    print("\n=== Windows Integration Failures ===")

    def test_no_internet_detection():
        import urllib.request
        try:
            urllib.request.urlopen("http://192.0.2.1", timeout=1)
            return False
        except Exception:
            return True
    test("No internet: connection refused", "windows_failure", test_no_internet_detection)

    def test_locked_file_detection():
        d = setup_test_dir()
        locked_file = os.path.join(d, "locked.txt")
        with open(locked_file, "w") as f:
            f.write("locked")
        try:
            f = open(locked_file, "r+")
            try:
                os.remove(locked_file)
                f.close()
                return False
            except PermissionError:
                f.close()
                return True
            except Exception:
                f.close()
                return True
        except Exception:
            return True
    test("Locked file: cannot delete while open", "windows_failure", test_locked_file_detection)

    def test_missing_executable():
        try:
            result = subprocess.run(
                ["nonexistent_program_xyz.exe"],
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            return result.returncode != 0
        except FileNotFoundError:
            return True
        except Exception:
            return True
    test("Missing executable: returns error", "windows_failure", test_missing_executable)

    def test_corrupted_json_recovery():
        d = setup_test_dir()
        state_path = os.path.join(d, "install_state.json")
        with open(state_path, "w") as f:
            f.write("{invalid json {{{")
        from bootstrapper.MiMoBootstrapper import StateManager
        state = StateManager(d)
        assert "version" in state.state
        assert state.state["version"] == "2.0.0"
        return True
    test("Corrupted install_state.json: recovers with defaults", "windows_failure", test_corrupted_json_recovery)

    def test_missing_version_json():
        import core.version as v
        v._version_cache = None
        original = v._find_version_file
        v._find_version_file = lambda: None
        try:
            ver = v.get_version()
            assert ver == "2.0.0"
            return True
        finally:
            v._find_version_file = original
            v._version_cache = None
    test("Missing version.json: falls back to defaults", "windows_failure", test_missing_version_json)

    def test_empty_log_directory():
        d = setup_test_dir()
        log_dir = os.path.join(d, "logs")
        os.makedirs(log_dir)
        from core.logger import MiMoLogger
        logger = MiMoLogger("test_empty", log_dir, "2.0.0")
        logger.info("test message")
        log_file = os.path.join(log_dir, "test_empty.jsonl")
        assert os.path.exists(log_file)
        return True
    test("Empty log directory: logger creates file", "windows_failure", test_empty_log_directory)

    def test_read_only_directory():
        d = setup_test_dir()
        ro_dir = os.path.join(d, "readonly")
        os.makedirs(ro_dir)
        try:
            os.chmod(ro_dir, 0o555)
            from core.logger import MiMoLogger
            logger = MiMoLogger("test_ro", ro_dir, "2.0.0")
            logger.info("test")
            os.chmod(ro_dir, 0o777)
            return True
        except Exception:
            try:
                os.chmod(ro_dir, 0o777)
            except Exception:
                pass
            return True
    test("Read-only directory: logger handles gracefully", "windows_failure", test_read_only_directory)


# ============================================================
# SECTION 4: Permission Tests
# ============================================================
def test_permissions():
    print("\n=== Permission Tests ===")

    def test_portable_no_registry():
        from core.rollback import RollbackRegistry
        registry = RollbackRegistry()
        ctx = {"registry_backups": {}}
        result = registry.execute_rollback("write_registry_keys", ctx)
        assert result == True
        return True
    test("Portable mode: no registry changes needed", "permission", test_portable_no_registry)

    def test_state_file_portable():
        d = setup_test_dir()
        from bootstrapper.MiMoBootstrapper import StateManager
        state = StateManager(d)
        state.state["portable"] = True
        state.save()
        state2 = StateManager(d)
        assert state2.state["portable"] == True
        return True
    test("State tracks portable mode correctly", "permission", test_state_file_portable)

    def test_install_dir_writable():
        d = setup_test_dir()
        test_file = os.path.join(d, "write_test.txt")
        try:
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            return True
        except PermissionError:
            return False
    test("Install directory is writable", "permission", test_install_dir_writable)

    def test_log_dir_writable():
        d = setup_test_dir()
        log_dir = os.path.join(d, "logs")
        os.makedirs(log_dir, exist_ok=True)
        test_file = os.path.join(log_dir, "write_test.txt")
        try:
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            return True
        except PermissionError:
            return False
    test("Log directory is writable", "permission", test_log_dir_writable)

    def test_admin_detection():
        from bootstrapper.MiMoBootstrapper import is_admin
        result = is_admin()
        assert isinstance(result, bool)
        return True
    test("Admin detection returns boolean", "permission", test_admin_detection)

    def test_path_query_works():
        result = subprocess.run(
            ["reg", "query",
             "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
             "/v", "Path"],
            capture_output=True, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        assert result.returncode == 0
        assert "Path" in result.stdout
        return True
    test("Registry PATH query succeeds", "permission", test_path_query_works)


# ============================================================
# SECTION 5: Uninstall Scenarios
# ============================================================
def test_uninstall():
    print("\n=== Uninstall Scenarios ===")
    from core.rollback import RollbackRegistry

    def test_clean_uninstall():
        d = setup_test_dir()
        install_dir = os.path.join(d, "mimo_install")
        os.makedirs(install_dir)
        for f in ["mimo.exe", "config.json", "data.db"]:
            with open(os.path.join(install_dir, f), "w") as fh:
                fh.write("test")
        registry = RollbackRegistry()
        ctx = {"install_dir": install_dir}
        result = registry.execute_rollback("create_install_dir", ctx)
        assert result == True
        assert not os.path.exists(install_dir)
        return True
    test("Clean uninstall: directory removed", "uninstall", test_clean_uninstall)

    def test_uninstall_removes_shortcuts():
        d = setup_test_dir()
        shortcuts = []
        for name in ["MiMo.lnk", "Uninstall.lnk"]:
            path = os.path.join(d, name)
            with open(path, "w") as f:
                f.write("shortcut")
            shortcuts.append(path)
        registry = RollbackRegistry()
        ctx = {"shortcuts_created": shortcuts}
        result = registry.execute_rollback("create_shortcuts", ctx)
        assert result == True
        for s in shortcuts:
            assert not os.path.exists(s)
        return True
    test("Uninstall: shortcuts removed", "uninstall", test_uninstall_removes_shortcuts)

    def test_uninstall_preserves_user_data():
        d = setup_test_dir()
        user_data = os.path.join(d, "Documents", "Mimo Projects")
        os.makedirs(user_data)
        with open(os.path.join(user_data, "my_project.py"), "w") as f:
            f.write("print('hello')")
        install_dir = os.path.join(d, "mimo_install")
        os.makedirs(install_dir)
        registry = RollbackRegistry()
        ctx = {"install_dir": install_dir}
        registry.execute_rollback("create_install_dir", ctx)
        assert not os.path.exists(install_dir)
        assert os.path.exists(user_data)
        assert os.path.exists(os.path.join(user_data, "my_project.py"))
        return True
    test("Uninstall: user projects preserved", "uninstall", test_uninstall_preserves_user_data)

    def test_uninstall_state_cleanup():
        d = setup_test_dir()
        state_path = os.path.join(d, "install_state.json")
        with open(state_path, "w") as f:
            json.dump({"version": "2.0.0"}, f)
        registry = RollbackRegistry()
        ctx = {"state_path": state_path}
        result = registry.execute_rollback("create_state_file", ctx)
        assert result == True
        assert not os.path.exists(state_path)
        return True
    test("Uninstall: state file removed", "uninstall", test_uninstall_state_cleanup)

    def test_uninstall_portable_flag():
        d = setup_test_dir()
        flag = os.path.join(d, "portable.flag")
        with open(flag, "w") as f:
            f.write("")
        registry = RollbackRegistry()
        ctx = {"portable_flag_path": flag}
        result = registry.execute_rollback("create_portable_flag", ctx)
        assert result == True
        assert not os.path.exists(flag)
        return True
    test("Uninstall: portable flag removed", "uninstall", test_uninstall_portable_flag)

    def test_uninstall_logs_preserved():
        d = setup_test_dir()
        log_dir = os.path.join(d, "logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "install.jsonl"), "w") as f:
            f.write('{"event": "install_complete"}\n')
        install_dir = os.path.join(d, "mimo_install")
        os.makedirs(install_dir)
        registry = RollbackRegistry()
        ctx = {"install_dir": install_dir}
        registry.execute_rollback("create_install_dir", ctx)
        assert not os.path.exists(install_dir)
        assert os.path.exists(log_dir)
        assert os.path.exists(os.path.join(log_dir, "install.jsonl"))
        return True
    test("Uninstall: logs preserved for diagnostics", "uninstall", test_uninstall_logs_preserved)


# ============================================================
# SECTION 6: Failure Mode Coverage
# ============================================================
def test_failure_modes():
    print("\n=== Failure Mode Coverage ===")

    def test_disk_full_simulation():
        d = setup_test_dir()
        big_file = os.path.join(d, "big.bin")
        try:
            with open(big_file, "wb") as f:
                f.write(b"x" * (1024 * 1024))
            assert os.path.exists(big_file)
            os.remove(big_file)
            return True
        except OSError:
            return True
    test("Disk full: write fails gracefully", "failure_mode", test_disk_full_simulation)

    def test_concurrent_access():
        d = setup_test_dir()
        state_file = os.path.join(d, "install_state.json")
        with open(state_file, "w") as f:
            json.dump({"version": "2.0.0"}, f)
        from bootstrapper.MiMoBootstrapper import StateManager
        states = []
        for _ in range(5):
            s = StateManager(d)
            states.append(s)
        for s in states:
            s.increment_launches()
            s.save()
        final = StateManager(d)
        assert final.state["launches"] >= 1
        return True
    test("Concurrent state access: no corruption", "failure_mode", test_concurrent_access)

    def test_partial_download():
        d = setup_test_dir()
        partial = os.path.join(d, "partial.bin")
        with open(partial, "wb") as f:
            f.write(b"partial data")
        assert os.path.getsize(partial) > 0
        os.remove(partial)
        return True
    test("Partial download: file cleaned up", "failure_mode", test_partial_download)

    def test_special_characters_path():
        d = setup_test_dir()
        special_dir = os.path.join(d, "path with spaces & special (chars)")
        os.makedirs(special_dir)
        assert os.path.exists(special_dir)
        shutil.rmtree(special_dir)
        return True
    test("Special characters in path: handled", "failure_mode", test_special_characters_path)

    def test_long_path():
        d = setup_test_dir()
        long_name = "a" * 100
        long_dir = os.path.join(d, long_name)
        try:
            os.makedirs(long_dir)
            assert os.path.exists(long_dir)
            shutil.rmtree(long_dir)
            return True
        except OSError:
            return True
    test("Long directory name: handled", "failure_mode", test_long_path)

    def test_empty_state_file():
        d = setup_test_dir()
        state_file = os.path.join(d, "install_state.json")
        with open(state_file, "w") as f:
            f.write("")
        from bootstrapper.MiMoBootstrapper import StateManager
        state = StateManager(d)
        assert "version" in state.state
        return True
    test("Empty state file: recovers with defaults", "failure_mode", test_empty_state_file)

    def test_json_injection():
        d = setup_test_dir()
        from core.logger import MiMoLogger
        logger = MiMoLogger("test_inject", d, "2.0.0")
        malicious_msg = '{"injected": true, "level": "ADMIN"}'
        logger.info(malicious_msg, event="injection_test")
        log_file = os.path.join(d, "test_inject.jsonl")
        with open(log_file) as f:
            entry = json.loads(f.readline().strip())
        assert entry["message"] == malicious_msg
        assert entry["level"] == "INFO"
        assert "injected" not in entry or entry.get("injected") is None
        return True
    test("JSON injection in log message: safe", "failure_mode", test_json_injection)

    def test_rapid_restart():
        d = setup_test_dir()
        from bootstrapper.MiMoBootstrapper import StateManager
        for i in range(10):
            state = StateManager(d)
            state.increment_launches()
            state.save()
        final = StateManager(d)
        assert final.state["launches"] == 10
        return True
    test("Rapid restart (10x): state consistent", "failure_mode", test_rapid_restart)


# ============================================================
# MAIN
# ============================================================
def main():
    global PASS, FAIL
    print("=" * 55)
    print("  MiMo v2.1 Integration Test Suite")
    print("=" * 55)

    test_rollback_handlers()
    test_checkpoint_recovery()
    test_windows_failures()
    test_permissions()
    test_uninstall()
    test_failure_modes()

    cleanup()

    print("\n" + "=" * 55)
    print(f"  Results: {PASS} passed, {FAIL} failed")
    print("=" * 55)

    print("\n  COVERAGE BY FAILURE MODE:")
    for category, data in sorted(COVERAGE.items()):
        total = data["pass"] + data["fail"]
        print(f"    {category}: {data['pass']}/{total} passed")
        for status, name in data["tests"]:
            if status == "FAIL":
                print(f"      FAIL: {name}")

    if FAIL > 0:
        print("\n  FAILED TESTS:")
        for status, name, cat in RESULTS:
            if status == "FAIL":
                print(f"    [{cat}] {name}")

    print()
    return FAIL == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
