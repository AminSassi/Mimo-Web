"""RC4 final: atomic downloads, state migration, all hardening verified"""
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
print("  RC4 Final Verification")
print("=" * 55)

from bootstrapper.MiMoBootstrapper import (
    StateManager, first_run, health_check_only,
    _acquire_lock, _release_lock, _rotate_log,
    download_file, cleanup_stale_tmp,
    _migrate_state, MIGRATIONS, STATE_SCHEMA_VERSION
)

# === 1: Atomic Downloads ===
print("\n=== Atomic Downloads ===")
td_dl = os.path.join(tempfile.gettempdir(), "mimo_rc4_atomic")
shutil.rmtree(td_dl, ignore_errors=True)
os.makedirs(td_dl, exist_ok=True)

dest = os.path.join(td_dl, "node.msi")
tmp = dest + ".tmp"
ok = download_file("http://127.0.0.1:1/nonexistent", dest, max_retries=2)
check("failed download returns False", not ok)
check("no .tmp file left after failure", not os.path.exists(tmp))
check("no final file created on failure", not os.path.exists(dest))

dest2 = os.path.join(td_dl, "git.exe")
ok2 = download_file("http://127.0.0.1:1/nonexistent", dest2, max_retries=1)
check("single retry download fails gracefully", not ok2)

td_stale = os.path.join(td_dl, "stale_tmp")
temp_install = os.environ.get("TEMP", os.path.join(td_dl, "temp")) 
target = os.path.join(temp_install, "mimo_install")
os.makedirs(target, exist_ok=True)
stale_file = os.path.join(target, "old.tmp")
with open(stale_file, "w") as f:
    f.write("old")
old_time = time.time() - 86401
os.utime(stale_file, (old_time, old_time))
fresh_file = os.path.join(target, "fresh.tmp")
with open(fresh_file, "w") as f:
    f.write("fresh")

cleanup_stale_tmp(td_dl)
check("stale .tmp (>24h) cleaned up", not os.path.exists(stale_file))
check("fresh .tmp preserved", os.path.exists(fresh_file))

shutil.rmtree(td_dl, ignore_errors=True)

# === 2: State Migration ===
print("\n=== State Migration ===")

# 2a: schema 0 -> 1
state_v0 = {
    "version": "2.0.0",
    "install_dir": "/tmp/test",
    "installed_at": None,
    "last_health_check": None,
    "last_health_result": "unknown",
    "deps": {
        "node": {"status": "ok", "version": "20.15.1"},
        "npm": {"status": "ok", "version": "10.7.0"},
        "git": {"status": "missing", "version": ""},
    },
    "mimo": {"status": "missing", "version": ""},
    "portable": False,
    "launches": 3,
    "repairs": 1,
    "repair_attempts": 1,
    "last_repair": None,
    "max_repairs": 3,
}
migrated, changed, status = _migrate_state(state_v0)
check("schema 0->1 status='migrated'", status == "migrated")
check("schema 0->1 changed=True", changed)
check("node 'ok' -> 'installed'", migrated["deps"]["node"]["status"] == "installed")
check("git 'missing' -> 'not_installed'", migrated["deps"]["git"]["status"] == "not_installed")
check("mimo 'missing' -> 'not_installed'", migrated["mimo"]["status"] == "not_installed")
check("install_result added", migrated.get("install_result") == "pending")
check("last_install_time added", migrated.get("last_install_time") is None)
check("schema_version=1 after migration", migrated["schema_version"] == 1)
print(f"  INFO  Migrated state: node={migrated['deps']['node']['status']}, git={migrated['deps']['git']['status']}, mimo={migrated['mimo']['status']}")

# 2b: missing schema_version -> 1
state_no_schema = {
    "version": "2.0.0",
    "install_dir": "/tmp/test",
    "deps": {"node": {"status": "ok", "version": ""}, "npm": {"status": "unknown", "version": ""}, "git": {"status": "ok", "version": ""}},
    "mimo": {"status": "ok", "version": ""},
}
migrated2, _, status2 = _migrate_state(state_no_schema)
check("missing schema_version -> migrated", status2 == "migrated")
check("schema_version=1 after migration", migrated2["schema_version"] == 1)

# 2c: current schema -> no migration needed
state_v1 = {"schema_version": 1, "install_dir": "/tmp"}
_, changed1, status1 = _migrate_state(state_v1)
check("current schema -> status='current'", status1 == "current")
check("current schema -> changed=False", not changed1)

# 2d: future schema -> rejected
state_future = {"schema_version": 99, "install_dir": "/tmp"}
_, _, status_f = _migrate_state(state_future)
check("future schema -> status='newer'", status_f == "newer")

# 2e: migration is idempotent
state_v0_copy = json.loads(json.dumps(state_v0))
m1, _, _ = _migrate_state(state_v0_copy)
m2, _, _ = _migrate_state(json.loads(json.dumps(m1)))
check("idempotent: re-migrate same result", m1 == m2)

# 2f: backup created during load
td_mig = os.path.join(tempfile.gettempdir(), "mimo_rc4_migrate")
shutil.rmtree(td_mig, ignore_errors=True)
os.makedirs(td_mig, exist_ok=True)
state_file = os.path.join(td_mig, "install_state.json")
state_v0_fresh = {
    "version": "2.0.0",
    "install_dir": td_mig,
    "installed_at": None,
    "last_health_check": None,
    "last_health_result": "unknown",
    "deps": {
        "node": {"status": "ok", "version": "20.15.1"},
        "npm": {"status": "ok", "version": "10.7.0"},
        "git": {"status": "missing", "version": ""},
    },
    "mimo": {"status": "missing", "version": ""},
    "portable": False,
    "launches": 3,
    "repairs": 1,
    "repair_attempts": 1,
    "max_repairs": 3,
}
with open(state_file, "w") as f:
    json.dump(state_v0_fresh, f)
sm = StateManager(td_mig)
check("backup created during migration", os.path.exists(state_file + ".bak"))
check("migrated state loaded correctly", sm.state["schema_version"] == 1)
check("node status migrated to 'installed'", sm.state["deps"]["node"]["status"] == "installed")
shutil.rmtree(td_mig, ignore_errors=True)

# === 3: Previous RC4 checks ===
print("\n=== Schema Version ===")
td = os.path.join(tempfile.gettempdir(), "mimo_rc4_main")
shutil.rmtree(td, ignore_errors=True)
os.makedirs(td, exist_ok=True)
sm = StateManager(td)
check("schema_version in state", sm.state.get("schema_version") == STATE_SCHEMA_VERSION)

print("\n=== Explicit Dep States ===")
check("install_result defaults to 'pending'", sm.state["install_result"] == "pending")
check("node defaults to 'not_installed'", sm.state["deps"]["node"]["status"] == "not_installed")

print("\n=== Timestamps ===")
check("last_install_time defaults to None", sm.state.get("last_install_time") is None)
sm.mark_install_result("success")
sm2 = StateManager(td)
check("last_install_time set", sm2.state["last_install_time"] is not None)

print("\n=== Lock File ===")
td_lock = os.path.join(tempfile.gettempdir(), "mimo_rc4_lock2")
os.makedirs(td_lock, exist_ok=True)
Path(td_lock, "portable.flag").touch()
lock1 = _acquire_lock(td_lock)
check("lock acquired", lock1 is not None)
lock2 = _acquire_lock(td_lock)
check("second lock blocked", lock2 is None)
_release_lock(lock1)
check("lock released", not os.path.exists(os.path.join(td_lock, "install.lock")))

print("\n=== Log Rotation ===")
td_log = os.path.join(tempfile.gettempdir(), "mimo_rc4_rot2")
os.makedirs(td_log, exist_ok=True)
log_path = os.path.join(td_log, "test.log")
with open(log_path, "w") as f:
    f.write("x" * (5 * 1024 * 1024 + 1))
_rotate_log(log_path)
check("log rotated", not os.path.exists(log_path))
check(".1.log created", os.path.exists(f"{log_path}.1.log"))

print("\n=== Bootstrapper Log ===")
td_fr = os.path.join(tempfile.gettempdir(), "mimo_rc4_log2")
shutil.rmtree(td_fr, ignore_errors=True)
os.makedirs(td_fr, exist_ok=True)
Path(td_fr, "portable.flag").touch()
first_run(td_fr)
log_file = os.path.join(td_fr, "logs", "bootstrapper.log")
check("bootstrapper.log exists", os.path.exists(log_file))
sm_final = StateManager(td_fr)
check("install_result set", sm_final.state["install_result"] in ("success", "partial"))
check("schema_version preserved", sm_final.state["schema_version"] == STATE_SCHEMA_VERSION)

# Cleanup
for d in [td, td_lock, td_log, td_fr]:
    shutil.rmtree(d, ignore_errors=True)

print()
print("=" * 55)
if failed == 0:
    print(f"  ALL {passed} CHECKS PASSED")
else:
    print(f"  {passed} passed, {failed} FAILED")
print("=" * 55)
