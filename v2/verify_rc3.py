"""RC3 verification: install_result, explicit states, bootstrapper.log"""
import sys, os, tempfile, shutil, json
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
print("  RC3 Verification")
print("=" * 55)

from bootstrapper.MiMoBootstrapper import StateManager, first_run

# 1: New state defaults use explicit states
td = os.path.join(tempfile.gettempdir(), "mimo_rc3")
shutil.rmtree(td, ignore_errors=True)
os.makedirs(td, exist_ok=True)
sm = StateManager(td)
check("install_result defaults to 'pending'", sm.state["install_result"] == "pending")
check("node defaults to 'not_installed'", sm.state["deps"]["node"]["status"] == "not_installed")
check("git defaults to 'not_installed'", sm.state["deps"]["git"]["status"] == "not_installed")
check("mimo defaults to 'not_installed'", sm.state["mimo"]["status"] == "not_installed")

# 2: mark_install_result works
sm.mark_install_result("success")
sm2 = StateManager(td)
check("install_result 'success' persists", sm2.state["install_result"] == "success")

# 3: Simulate partial install
sm.mark_install_result("partial")
sm.update_dep("node", "installed", "v20.15.1")
sm.update_dep("git", "installed", "2.45.2")
sm.update_mimo("failed")
sm.save()
sm3 = StateManager(td)
check("partial install_result", sm3.state["install_result"] == "partial")
check("node=installed in partial", sm3.state["deps"]["node"]["status"] == "installed")
check("mimo=failed in partial", sm3.state["mimo"]["status"] == "failed")

# 4: Inno Setup Pascal would detect partial
content = json.dumps(sm3.state)
check("Pascal detects 'install_result: partial'", '"install_result": "partial"' in content)

# 5: bootstrapper.log written by first_run
td2 = os.path.join(tempfile.gettempdir(), "mimo_rc3_log")
os.makedirs(td2, exist_ok=True)
Path(td2, "portable.flag").touch()
first_run(td2)
log_path = os.path.join(td2, "logs", "bootstrapper.log")
check("bootstrapper.log exists", os.path.exists(log_path))
if os.path.exists(log_path):
    with open(log_path) as f:
        log_content = f.read()
    check("log contains 'Bootstrapper started'", "Bootstrapper started" in log_content)
    check("log contains 'Health check'", "Health check" in log_content)
    print(f"\n  Log content:")
    for line in log_content.strip().split("\n"):
        print(f"    {line}")

# 6: State after first_run
sm_final = StateManager(td2)
check("install_result set after first_run", sm_final.state["install_result"] in ("success", "partial"))

# 7: health_check_only returns issues, not install_result
from bootstrapper.MiMoBootstrapper import health_check_only
td3 = os.path.join(tempfile.gettempdir(), "mimo_rc3_hc")
os.makedirs(td3, exist_ok=True)
Path(td3, "portable.flag").touch()
issues = health_check_only(td3)
check("health_check_only returns list", isinstance(issues, list))
sm_hc = StateManager(td3)
check("health_check sets last_health_result", sm_hc.state["last_health_result"] in ("healthy", "issues_found"))
check("health_check does NOT set install_result", sm_hc.state["install_result"] == "pending")

shutil.rmtree(td, ignore_errors=True)
shutil.rmtree(td2, ignore_errors=True)
shutil.rmtree(td3, ignore_errors=True)

print()
print("=" * 55)
if failed == 0:
    print(f"  ALL {passed} RC3 CHECKS PASSED")
else:
    print(f"  {passed} passed, {failed} FAILED")
print("=" * 55)
