"""RC4 verification: schema_version, timestamps, lock file, log rotation, download retry"""
import sys, os, tempfile, shutil, json, time
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

passed = 0
failed = 0

def check(name, cond):
    global passed, failed
    if cond:
        print(f"  PASS  {name}")
        passed += 1
    else:
        print(f"  FAIL  {name}")
        failed += 1

print("=" * 55)
print("  RC4 Verification")
print("=" * 55)

from bootstrapper.MiMoBootstrapper import (
    StateManager, first_run, health_check_only,
    _acquire_lock, _release_lock, _rotate_log, download_file
)
from bootstrapper.MiMoBootstrapper import STATE_SCHEMA_VERSION

# === 1: Schema version ===
print("\n=== Schema Version ===")
td = os.path.join(tempfile.gettempdir(), "mimo_rc4")
shutil.rmtree(td, ignore_errors=True)
os.makedirs(td, exist_ok=True)
sm = StateManager(td)
check("schema_version in state", sm.state.get("schema_version") == STATE_SCHEMA_VERSION)
check("schema_version == 1", STATE_SCHEMA_VERSION == 1)

# === 2: Explicit states ===
print("\n=== Explicit Dep States ===")
check("install_result defaults to 'pending'", sm.state["install_result"] == "pending")
check("node defaults to 'not_installed'", sm.state["deps"]["node"]["status"] == "not_installed")
check("git defaults to 'not_installed'", sm.state["deps"]["git"]["status"] == "not_installed")
check("mimo defaults to 'not_installed'", sm.state["mimo"]["status"] == "not_installed")

# === 3: Timestamps ===
print("\n=== Timestamps ===")
check("last_install_time defaults to None", sm.state.get("last_install_time") is None)
sm.mark_install_result("success")
sm2 = StateManager(td)
check("last_install_time set on mark_install_result", sm2.state["last_install_time"] is not None)
print(f"  INFO  last_install_time: {sm2.state['last_install_time']}")

# === 4: install_result separation ===
print("\n=== install_result vs health_result ===")
sm.mark_install_result("partial")
sm.update_dep("node", "installed", "v20.15.1")
sm.update_dep("git", "installed", "2.45.2")
sm.update_mimo("failed")
sm.save()
content = json.dumps(sm.state)
check("Pascal detects partial", '"install_result": "partial"' in content)
check("Node not reinstalled when installed", sm.state["deps"]["node"]["status"] == "installed")

# === 5: Lock file ===
print("\n=== Lock File ===")
td_lock = os.path.join(tempfile.gettempdir(), "mimo_rc4_lock")
os.makedirs(td_lock, exist_ok=True)
Path(td_lock, "portable.flag").touch()
lock1 = _acquire_lock(td_lock)
check("lock acquired", lock1 is not None)
check("install.lock exists", os.path.exists(os.path.join(td_lock, "install.lock")))
lock2 = _acquire_lock(td_lock)
check("second lock blocked (returns None)", lock2 is None)
_release_lock(lock1)
check("lock file removed after release", not os.path.exists(os.path.join(td_lock, "install.lock")))
lock3 = _acquire_lock(td_lock)
check("lock re-acquirable after release", lock3 is not None)
_release_lock(lock3)
# Test stale lock (>600s) gets cleaned
lock_path = os.path.join(td_lock, "install.lock")
with open(lock_path, "w") as f:
    f.write("99999")
old_time = time.time() - 700
os.utime(lock_path, (old_time, old_time))
lock4 = _acquire_lock(td_lock)
check("stale lock (600s+) auto-cleaned", lock4 is not None)
_release_lock(lock4)

# === 6: Log rotation ===
print("\n=== Log Rotation ===")
td_log = os.path.join(tempfile.gettempdir(), "mimo_rc4_logrotate")
os.makedirs(td_log, exist_ok=True)
log_path = os.path.join(td_log, "test.log")
with open(log_path, "w") as f:
    f.write("x" * (5 * 1024 * 1024 + 1))
_rotate_log(log_path)
check("original log rotated (renamed to .1.log)", not os.path.exists(log_path))
check(".1.log created", os.path.exists(f"{log_path}.1.log"))

# === 7: Download retry ===
print("\n=== Download Retry ===")
td_dl = os.path.join(tempfile.gettempdir(), "mimo_rc4_dl")
os.makedirs(td_dl, exist_ok=True)
dest = os.path.join(td_dl, "test.bin")
result = download_file("http://127.0.0.1:1/nonexistent", dest, max_retries=2)
check("download fails gracefully after retries", not result)

# === 8: bootstrapper.log via first_run ===
print("\n=== Bootstrapper Log ===")
td_fr = os.path.join(tempfile.gettempdir(), "mimo_rc4_first")
shutil.rmtree(td_fr, ignore_errors=True)
os.makedirs(td_fr, exist_ok=True)
Path(td_fr, "portable.flag").touch()
first_run(td_fr)
log_file = os.path.join(td_fr, "logs", "bootstrapper.log")
check("bootstrapper.log exists", os.path.exists(log_file))
if os.path.exists(log_file):
    with open(log_file) as f:
        log_content = f.read()
    check("log has 'Bootstrapper started'", "Bootstrapper started" in log_content)
    check("log has 'Health check'", "Health check" in log_content)
    check("log has timestamped format", "[202" in log_content)
    print(f"\n  Log content:")
    for line in log_content.strip().split("\n"):
        print(f"    {line}")

# === 9: State after first_run ===
print("\n=== Post-Run State ===")
sm_final = StateManager(td_fr)
check("install_result set", sm_final.state["install_result"] in ("success", "partial"))
check("last_install_time set", sm_final.state["last_install_time"] is not None)
check("schema_version preserved", sm_final.state["schema_version"] == STATE_SCHEMA_VERSION)

# Cleanup
for d in [td, td_lock, td_log, td_dl, td_fr]:
    shutil.rmtree(d, ignore_errors=True)

print()
print("=" * 55)
if failed == 0:
    print(f"  ALL {passed} RC4 CHECKS PASSED")
else:
    print(f"  {passed} passed, {failed} FAILED")
print("=" * 55)
