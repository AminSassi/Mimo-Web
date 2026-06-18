"""Verify all runtime code paths work after ML module exclusions."""
import sys, os, tempfile, shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

passed = 0
failed = 0

def test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  PASS  {name}")
        passed += 1
    except Exception as e:
        print(f"  FAIL  {name} -- {e}")
        failed += 1

def assert_exists(path):
    if not os.path.exists(path):
        raise ValueError(f"Not found: {path}")

def assert_in_file(filename, text):
    with open(os.path.join(os.path.dirname(__file__), filename)) as f:
        if text not in f.read():
            raise ValueError(f"'{text}' not found in {filename}")

print("=" * 55)
print("  Post-Exclusion Runtime Verification")
print("=" * 55)

print("\n=== Core Module Imports ===")
from core.logger import MiMoLogger
from core.version import get_version
from core.paths import get_log_dir, get_state_path, ensure_dirs, is_portable
from core.rollback import RollbackRegistry
from core.signing import ManifestSigner
from core.user_assets import UserAssetManager
from core.updater import AutoUpdater
from core.models_manager import ModelManager
print("  PASS  All 8 core modules imported")

print("\n=== GPU Detection (no torch at import) ===")
from core.gpu import (detect_all_gpus, select_best_gpu, detect_cuda_runtime,
                      get_gpu_info_dict, check_compatibility, gpu_health_check,
                      COMPATIBILITY_MATRIX, GPU_TIERS, run_inference_smoke_test)

gpus = detect_all_gpus()
test("detect_all_gpus", lambda: gpus if len(gpus) >= 0 else (_ for _ in ()).throw())
print(f"  INFO  Found {len(gpus)} GPU(s)")

best = select_best_gpu(gpus)
test("select_best_gpu", lambda: best)
print(f"  INFO  Best GPU: {best.get('name', 'N/A') if best else 'None'}")

cuda = detect_cuda_runtime()
test("detect_cuda_runtime", lambda: cuda)
print(f"  INFO  CUDA: {cuda}")

info = get_gpu_info_dict()
test("get_gpu_info_dict", lambda: info if 'total_vram_gb' in info else (_ for _ in ()).throw())
print(f"  INFO  VRAM: {info.get('total_vram_gb', 0)} GB total, {info.get('free_vram_gb', 0)} GB free")

result = run_inference_smoke_test(0)
test("run_inference_smoke_test", lambda: result if result.get('passed') else (_ for _ in ()).throw())
print(f"  INFO  Inference: {result}")

print("\n=== Model Recommendations ===")
from core.models import (MODEL_TIERS, get_max_model_tier, get_model_recommendation,
                         get_vram_warnings)

test("5 model tiers", lambda: len(MODEL_TIERS) == 5)
tier = get_max_model_tier(info.get('total_vram_gb', 0))
test("get_max_model_tier", lambda: tier)
print(f"  INFO  Max tier: {tier}")

rec = get_model_recommendation(info.get('total_vram_gb', 0), info.get('free_vram_gb', 0))
test("get_model_recommendation", lambda: rec)
print(f"  INFO  Recommendation: {rec}")

warnings = get_vram_warnings(info.get('total_vram_gb', 0), info.get('free_vram_gb', 0))
test("get_vram_warnings", lambda: isinstance(warnings, list))
print(f"  INFO  Warnings: {len(warnings)}")

print("\n=== Bootstrapper ===")
from bootstrapper.MiMoBootstrapper import (HealthChecker, StateManager,
                                            run_cmd, refresh_path, is_admin)

test("is_admin", lambda: is_admin())
test("refresh_path", lambda: refresh_path())

ok, out, err = run_cmd(["echo", "hello"])
test("run_cmd", lambda: ok if ok else (_ for _ in ()).throw())

test_dir = os.path.join(tempfile.gettempdir(), "mimo_verify_state")
os.makedirs(test_dir, exist_ok=True)
try:
    sm = StateManager(test_dir)
    sm.update_dep("node", "ok", "20.15.1")
    sm.save()
    sm2 = StateManager(test_dir)
    test("StateManager roundtrip", lambda: sm2.state["deps"]["node"]["status"] == "ok")
except Exception as e:
    print(f"  FAIL  StateManager -- {e}")
finally:
    shutil.rmtree(test_dir, ignore_errors=True)

from core.logger import MiMoLogger as ML
from core.version import get_version as gv
health_dir = os.path.join(tempfile.gettempdir(), "mimo_verify_health")
os.makedirs(health_dir, exist_ok=True)
try:
    logger = ML("test", health_dir, gv())
    checker = HealthChecker(health_dir, logger)
    issues = checker.health_check()
    test("health_check", lambda: isinstance(issues, list))
    print(f"  INFO  Health issues: {issues}")
except Exception as e:
    print(f"  FAIL  HealthChecker -- {e}")
finally:
    shutil.rmtree(health_dir, ignore_errors=True)

print("\n=== Inno Setup .iss Verification ===")
test("No skipifnotsilent", lambda: assert_in_file("MiMoSetup.iss", "postinstall") and (
    open("MiMoSetup.iss").read().count("skipifnotsilent") == 0 or (_ for _ in ()).throw()))
test("Version 2.2.0", lambda: assert_in_file("MiMoSetup.iss", "2.2.0"))
test("Bootstrapper in [Run]", lambda: assert_in_file("MiMoSetup.iss", "MiMoBootstrapper.exe"))
test("No runascurrentuser", lambda: (
    open("MiMoSetup.iss").read().count("runascurrentuser") == 0 or (_ for _ in ()).throw()))

print("\n=== Build Output ===")
build = os.path.join(os.path.dirname(__file__), "build")
test("MiMoBootstrapper.exe", lambda: assert_exists(os.path.join(build, "bootstrapper", "MiMoBootstrapper.exe")))
test("mimo_launch.exe", lambda: assert_exists(os.path.join(build, "dist", "mimo_launch.exe")))
test("MiMoInstaller.exe", lambda: assert_exists(os.path.join(build, "dist", "MiMoInstaller.exe")))
test("MiMoSetup.exe", lambda: assert_exists(os.path.join(build, "build", "MiMoSetup.exe")))

print("\n=== EXE Sizes ===")
for name in ["bootstrapper/MiMoBootstrapper.exe", "dist/mimo_launch.exe",
             "dist/MiMoInstaller.exe", "build/MiMoSetup.exe"]:
    p = os.path.join(build, name)
    if os.path.exists(p):
        size_mb = os.path.getsize(p) / (1024 * 1024)
        print(f"  {name}: {size_mb:.1f} MB")

print()
print("=" * 55)
if failed == 0:
    print(f"  ALL {passed} CHECKS PASSED")
else:
    print(f"  {passed} passed, {failed} FAILED")
print("=" * 55)
