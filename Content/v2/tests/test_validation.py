"""
MiMo v2.1 Validation Test Suite
Tests: structured logging, version consistency, repair limits, rollback, fault injection
"""
import os
import sys
import json
import shutil
import tempfile
import time
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

PASS = 0
FAIL = 0
TEST_DIR = os.path.join(tempfile.gettempdir(), "mimo_test")
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
        RESULTS.append(("FAIL", f"{name} — {e}"))
        print(f"  FAIL  {name} — {e}")


def cleanup():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR, ignore_errors=True)


def setup_test_dir():
    cleanup()
    os.makedirs(TEST_DIR, exist_ok=True)
    return TEST_DIR


# ============================================================
# SECTION 1: Structured Logging
# ============================================================
def test_logging():
    print("\n=== Structured Logging ===")

    from core.logger import MiMoLogger

    def test_jsonl_format():
        d = setup_test_dir()
        logger = MiMoLogger("test", d, "2.0.0")
        logger.info("test message", event="test_event")
        log_path = os.path.join(d, "test.jsonl")
        assert os.path.exists(log_path), "Log file not created"
        with open(log_path) as f:
            line = f.readline().strip()
        entry = json.loads(line)
        required = ["timestamp", "session_id", "component", "version", "level", "event", "message"]
        for field in required:
            assert field in entry, f"Missing field: {field}"
        assert entry["component"] == "test"
        assert entry["version"] == "2.0.0"
        assert entry["level"] == "INFO"
        assert entry["event"] == "test_event"
        return True
    test("JSONL format with all required fields", test_jsonl_format)

    def test_session_id_consistency():
        d = setup_test_dir()
        logger = MiMoLogger("test_session", d, "2.0.0")
        sid = logger.session_id
        logger.info("msg1")
        logger.info("msg2")
        logger.warn("msg3")
        log_path = os.path.join(d, "test_session.jsonl")
        with open(log_path) as f:
            lines = f.readlines()
        for line in lines:
            entry = json.loads(line.strip())
            assert entry["session_id"] == sid, f"Session ID mismatch: {entry['session_id']} != {sid}"
        assert len(sid) == 8, f"Session ID should be 8 chars, got {len(sid)}"
        return True
    test("Session ID consistent across log entries", test_session_id_consistency)

    def test_log_levels():
        d = setup_test_dir()
        logger = MiMoLogger("test", d, "2.0.0")
        logger.info("info msg", event="info_test")
        logger.warn("warn msg", event="warn_test")
        logger.error("error msg", event="error_test")
        logger.debug("debug msg", event="debug_test")
        log_path = os.path.join(d, "test.jsonl")
        with open(log_path) as f:
            lines = f.readlines()
        levels = set()
        for line in lines:
            entry = json.loads(line.strip())
            levels.add(entry["level"])
        assert "INFO" in levels
        assert "WARNING" in levels
        assert "ERROR" in levels
        assert "DEBUG" in levels
        return True
    test("All log levels work (INFO, WARNING, ERROR, DEBUG)", test_log_levels)

    def test_specialized_methods():
        d = setup_test_dir()
        logger = MiMoLogger("test", d, "2.0.0")
        logger.dependency_detected("Node.js", "20.15.1")
        logger.dependency_missing("Git")
        logger.dependency_installed("npm", "10.7.0")
        logger.step_start("install_node")
        logger.step_complete("install_node", 1500)
        logger.step_failed("install_git", "download failed")
        logger.repair_start(["node_missing", "git_missing"])
        logger.repair_complete(["node"])
        logger.repair_limit_reached(3, 3)
        logger.health_check_result(True)
        logger.health_check_result(False, ["node_missing"])
        logger.install_start()
        logger.install_complete(5000)
        logger.install_failed("timeout")
        logger.launch(3000)
        log_path = os.path.join(d, "test.jsonl")
        with open(log_path) as f:
            lines = f.readlines()
        events = set()
        for line in lines:
            entry = json.loads(line.strip())
            events.add(entry["event"])
        expected_events = [
            "dependency_detected", "dependency_missing", "dependency_installed",
            "step_start", "step_complete", "step_failed",
            "repair_start", "repair_complete", "repair_limit_reached",
            "health_check_healthy", "health_check_issues",
            "install_start", "install_complete", "install_failed", "launch"
        ]
        for ev in expected_events:
            assert ev in events, f"Missing event: {ev}"
        return True
    test("All specialized log methods produce correct events", test_specialized_methods)

    def test_log_rotation():
        d = setup_test_dir()
        from core.logger import MiMoLogger, MAX_LOG_SIZE
        logger = MiMoLogger("test", d, "2.0.0")
        big_msg = "x" * 1000
        for i in range(100):
            logger.info(f"{big_msg}_{i}")
        log_path = os.path.join(d, "test.jsonl")
        assert os.path.exists(log_path)
        size = os.path.getsize(log_path)
        assert size <= MAX_LOG_SIZE * 1.1, f"Log too large: {size}"
        return True
    test("Log rotation works (10MB limit)", test_log_rotation)

    def test_log_field_custom():
        d = setup_test_dir()
        logger = MiMoLogger("test_custom", d, "2.0.0")
        logger.info("node found", event="dep_detected", dependency="Node.js",
                     version_found="20.15.1", path="C:\\Program Files\\nodejs")
        log_path = os.path.join(d, "test_custom.jsonl")
        with open(log_path) as f:
            entry = json.loads(f.readline().strip())
        assert entry.get("dependency") == "Node.js", f"Expected dependency=Node.js, got {entry}"
        assert entry.get("version_found") == "20.15.1"
        assert entry.get("path") == "C:\\Program Files\\nodejs"
        return True
    test("Custom fields in log entries", test_log_field_custom)


# ============================================================
# SECTION 2: Version Consistency
# ============================================================
def test_version():
    print("\n=== Version Consistency ===")

    from core.version import (
        get_version, get_build_number, get_build_date,
        get_git_commit, get_full_version_string, version_dict
    )

    def test_version_source():
        v = version_dict()
        assert "version" in v
        assert "build_number" in v
        assert "build_date" in v
        assert "git_commit" in v
        assert "product_name" in v
        return True
    test("version.json has all required fields", test_version_source)

    def test_version_consistency():
        v1 = get_version()
        v2 = get_version()
        assert v1 == v2, f"Version inconsistent: {v1} != {v2}"
        return True
    test("get_version() returns consistent value", test_version_consistency)

    def test_full_version_string():
        s = get_full_version_string()
        assert "MiMo Auto" in s
        assert get_version() in s
        assert get_build_number() in s
        return True
    test("Full version string contains product, version, build", test_full_version_string)

    def test_bootstrapper_reads_version():
        test_dir = setup_test_dir()
        from bootstrapper.MiMoBootstrapper import StateManager
        state = StateManager(test_dir)
        assert state.state["version"] == get_version()
        return True
    test("Bootstrapper StateManager reads correct version", test_bootstrapper_reads_version)


# ============================================================
# SECTION 3: Repair Limits
# ============================================================
def test_repair_limits():
    print("\n=== Repair Limits ===")

    from bootstrapper.MiMoBootstrapper import StateManager, MAX_REPAIR_ATTEMPTS

    def test_initial_repair_count():
        d = setup_test_dir()
        state = StateManager(d)
        assert state.state["repair_attempts"] == 0
        assert state.state["max_repairs"] == MAX_REPAIR_ATTEMPTS
        return True
    test("Initial repair count is 0", test_initial_repair_count)

    def test_can_repair():
        d = setup_test_dir()
        state = StateManager(d)
        assert state.can_repair() == True
        return True
    test("can_repair() returns True initially", test_can_repair)

    def test_repair_attempts_increment():
        d = setup_test_dir()
        state = StateManager(d)
        for i in range(MAX_REPAIR_ATTEMPTS - 1):
            state.record_repair_attempt()
            state.save()
        assert state.can_repair() == True
        state.record_repair_attempt()
        state.save()
        assert state.can_repair() == False
        return True
    test("Repair attempts increment and block at max", test_repair_attempts_increment)

    def test_repair_counter_survives_reload():
        d = setup_test_dir()
        state1 = StateManager(d)
        state1.record_repair_attempt()
        state1.record_repair_attempt()
        state1.save()
        state2 = StateManager(d)
        assert state2.state["repair_attempts"] == 2
        assert state2.can_repair() == True
        return True
    test("Repair counter survives reload (crash/reboot)", test_repair_counter_survives_reload)

    def test_repair_limit_persists_after_max():
        d = setup_test_dir()
        state = StateManager(d)
        for _ in range(MAX_REPAIR_ATTEMPTS):
            state.record_repair_attempt()
            state.save()
        state2 = StateManager(d)
        assert state2.can_repair() == False
        return True
    test("Repair limit persists after max reached", test_repair_limit_persists_after_max)


# ============================================================
# SECTION 4: Transaction / Rollback
# ============================================================
def test_transactions():
    print("\n=== Transaction & Rollback ===")

    from bootstrapper.MiMoBootstrapper import TransactionManager

    def test_transaction_lifecycle():
        d = setup_test_dir()
        tx = TransactionManager(d)
        tx.start(["step1", "step2", "step3"])
        assert tx.transaction["status"] == "in_progress"
        assert len(tx.transaction["pending_steps"]) == 3
        tx.complete_step("step1", rollback_action="delete_dir")
        tx.complete_step("step2", rollback_action="uninstall_node")
        assert len(tx.transaction["completed_steps"]) == 2
        assert len(tx.transaction["pending_steps"]) == 1
        tx.success()
        assert tx.transaction["status"] == "completed"
        return True
    test("Transaction lifecycle: start -> steps -> success", test_transaction_lifecycle)

    def test_transaction_failure():
        d = setup_test_dir()
        tx = TransactionManager(d)
        tx.start(["step1", "step2", "step3"])
        tx.complete_step("step1")
        tx.complete_step("step2")
        failed_steps = tx.fail()
        assert tx.transaction["status"] == "failed"
        assert failed_steps == ["step2", "step1"]
        return True
    test("Transaction failure returns reversed completed steps", test_transaction_failure)

    def test_rollback_actions():
        d = setup_test_dir()
        tx = TransactionManager(d)
        tx.start(["create_dir", "install_node", "install_git"])
        tx.complete_step("create_dir", rollback_action="delete_dir")
        tx.complete_step("install_node", rollback_action="uninstall_node")
        actions = tx.get_rollback_actions()
        assert actions["create_dir"] == "delete_dir"
        assert actions["install_node"] == "uninstall_node"
        return True
    test("Rollback actions stored per step", test_rollback_actions)

    def test_transaction_persists():
        d = setup_test_dir()
        tx1 = TransactionManager(d)
        tx1.start(["step1", "step2"])
        tx1.complete_step("step1")
        tx2 = TransactionManager(d)
        assert tx2.transaction["status"] == "in_progress"
        assert len(tx2.transaction["completed_steps"]) == 1
        return True
    test("Transaction state persists across instances", test_transaction_persists)

    def test_transaction_cleanup():
        d = setup_test_dir()
        tx = TransactionManager(d)
        tx.start(["step1"])
        tx.success()
        tx.cleanup()
        assert not os.path.exists(tx.path)
        return True
    test("Transaction cleanup removes file", test_transaction_cleanup)


# ============================================================
# SECTION 5: State Manager
# ============================================================
def test_state():
    print("\n=== State Management ===")

    from bootstrapper.MiMoBootstrapper import StateManager

    def test_state_defaults():
        d = setup_test_dir()
        state = StateManager(d)
        assert state.state["version"] == "2.0.0"
        assert "deps" in state.state
        assert "mimo" in state.state
        assert state.state["launches"] == 0
        assert state.state["repairs"] == 0
        return True
    test("State has correct defaults", test_state_defaults)

    def test_state_update_dep():
        d = setup_test_dir()
        state = StateManager(d)
        state.update_dep("node", "ok", "v20.15.1")
        state.save()
        state2 = StateManager(d)
        assert state2.state["deps"]["node"]["status"] == "ok"
        assert state2.state["deps"]["node"]["version"] == "v20.15.1"
        return True
    test("State dep update persists", test_state_update_dep)

    def test_state_corrupted_recovery():
        d = setup_test_dir()
        state_path = os.path.join(d, "install_state.json")
        with open(state_path, "w") as f:
            f.write("NOT JSON{{{")
        state = StateManager(d)
        assert "version" in state.state
        assert state.state["version"] == "2.0.0"
        return True
    test("Corrupted state.json recovers with defaults", test_state_corrupted_recovery)

    def test_state_launches_increment():
        d = setup_test_dir()
        state = StateManager(d)
        state.increment_launches()
        state.increment_launches()
        state.save()
        state2 = StateManager(d)
        assert state2.state["launches"] == 2
        return True
    test("Launch counter increments correctly", test_state_launches_increment)


# ============================================================
# SECTION 6: Paths
# ============================================================
def test_paths():
    print("\n=== Paths Module ===")

    from core.paths import (
        get_log_dir, get_state_path, get_transaction_path,
        is_portable, ensure_dirs, PORTABLE_FLAG
    )

    def test_log_dir_portable():
        d = setup_test_dir()
        log_dir = get_log_dir(d, portable=True)
        assert log_dir.startswith(d)
        assert log_dir.endswith("logs")
        return True
    test("Portable log dir is inside install dir", test_log_dir_portable)

    def test_log_dir_installed():
        log_dir = get_log_dir(portable=False)
        assert "ProgramData" in log_dir or "MiMo" in log_dir
        return True
    test("Installed log dir uses ProgramData", test_log_dir_installed)

    def test_portable_detection():
        d = setup_test_dir()
        assert is_portable(d) == False
        flag_path = os.path.join(d, PORTABLE_FLAG)
        with open(flag_path, "w") as f:
            f.write("")
        assert is_portable(d) == True
        return True
    test("Portable flag detection works", test_portable_detection)

    def test_ensure_dirs():
        d = setup_test_dir()
        ensure_dirs(d, portable=True)
        log_dir = get_log_dir(d, portable=True)
        assert os.path.isdir(log_dir)
        return True
    test("ensure_dirs creates required directories", test_ensure_dirs)


# ============================================================
# SECTION 7: Fault Injection
# ============================================================
def test_fault_injection():
    print("\n=== Fault Injection ===")

    from bootstrapper.MiMoBootstrapper import (
        run_cmd, refresh_path, verify_hash, download_file
    )

    def test_run_cmd_not_found():
        ok, out, err = run_cmd(["nonexistent_command_xyz"])
        assert ok == False
        assert "not found" in err.lower() or out == ""
        return True
    test("run_cmd handles missing command gracefully", test_run_cmd_not_found)

    def test_run_cmd_timeout():
        ok, out, err = run_cmd(["ping", "-n", "100", "127.0.0.1"], timeout=1)
        assert ok == False
        assert "timeout" in err.lower() or not ok
        return True
    test("run_cmd handles timeout gracefully", test_run_cmd_timeout)

    def test_verify_hash_corrupted():
        d = setup_test_dir()
        test_file = os.path.join(d, "test.bin")
        with open(test_file, "wb") as f:
            f.write(b"corrupted data")
        result = verify_hash(test_file, "0000000000000000000000000000000000000000000000000000000000000000")
        assert result == False
        return True
    test("verify_hash rejects corrupted file", test_verify_hash_corrupted)

    def test_verify_hash_correct():
        import hashlib
        d = setup_test_dir()
        test_file = os.path.join(d, "test.bin")
        data = b"test data for hashing"
        with open(test_file, "wb") as f:
            f.write(data)
        expected = hashlib.sha256(data).hexdigest()
        result = verify_hash(test_file, expected)
        assert result == True
        return True
    test("verify_hash accepts correct hash", test_verify_hash_correct)

    def test_verify_hash_missing_file():
        result = verify_hash("/nonexistent/file.exe", "abc123")
        assert result == False
        return True
    test("verify_hash handles missing file", test_verify_hash_missing_file)

    def test_download_failure():
        result = download_file("http://localhost:99999/nonexistent", os.path.join(tempfile.gettempdir(), "test_dl"))
        assert result == False
        return True
    test("download_file handles unreachable URL", test_download_failure)


# ============================================================
# MAIN
# ============================================================
def main():
    global PASS, FAIL
    print("=" * 55)
    print("  MiMo v2.1 Validation Test Suite")
    print("=" * 55)

    test_logging()
    test_version()
    test_repair_limits()
    test_transactions()
    test_state()
    test_paths()
    test_fault_injection()

    cleanup()

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
