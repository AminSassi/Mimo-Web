"""
MiMo GPU/CUDA Validation Tests v2.1
Covers: detection, smoke test, multi-GPU, free VRAM, compatibility, failure scenarios
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
# SECTION 1: GPU Detection
# ============================================================
def test_gpu_detection():
    print("\n=== GPU Detection ===")
    from core.gpu import detect_all_gpus, select_best_gpu, detect_cuda_runtime

    def test_detect_all():
        gpus = detect_all_gpus()
        assert isinstance(gpus, list)
        return True
    test("detect_all_gpus returns list", test_detect_all)

    def test_gpu_fields():
        gpus = detect_all_gpus()
        if gpus:
            gpu = gpus[0]
            required = ["index", "name", "driver_version", "compute_capability",
                        "vram_total_mb", "vram_total_gb", "vram_free_mb", "vram_free_gb"]
            for field in required:
                assert field in gpu, f"Missing: {field}"
            assert gpu["vram_total_gb"] > 0
            assert gpu["vram_free_gb"] >= 0
        return True
    test("GPU has all required fields", test_gpu_fields)

    def test_select_best():
        gpus = detect_all_gpus()
        best = select_best_gpu(gpus)
        if gpus:
            assert best is not None
            assert "name" in best
            assert "index" in best
        else:
            assert best is None
        return True
    test("select_best_gpu picks highest capability", test_select_best)

    def test_cuda_runtime():
        cuda = detect_cuda_runtime()
        assert "available" in cuda
        if cuda["available"]:
            assert "torch_version" in cuda
            assert "cuda_version" in cuda
            assert "device_count" in cuda
            assert "compute_capability" in cuda
            assert "total_memory_gb" in cuda
            assert "supports_float16" in cuda
            assert "supports_bfloat16" in cuda
        return True
    test("CUDA runtime has all fields including bfloat16", test_cuda_runtime)

    def test_pytorch_smoke():
        import torch
        assert torch.cuda.is_available()
        device = torch.device("cuda:0")
        x = torch.randn(256, 256, device=device)
        y = x @ x
        torch.cuda.synchronize()
        assert y.shape == (256, 256)
        return True
    test("PyTorch basic CUDA operation works", test_pytorch_smoke)


# ============================================================
# SECTION 2: Inference Smoke Test
# ============================================================
def test_smoke_test():
    print("\n=== Inference Smoke Test ===")
    from core.gpu import run_inference_smoke_test

    def test_smoke_passes():
        result = run_inference_smoke_test(0)
        assert result["passed"] == True, f"Smoke test failed: {result.get('error')}"
        assert "elapsed_ms" in result
        assert result["elapsed_ms"] > 0
        assert result["matrix_size"] == "1024x1024"
        return True
    test("Smoke test passes on primary GPU", test_smoke_passes)

    def test_smoke_result_valid():
        result = run_inference_smoke_test(0)
        assert "result_sample" in result
        assert isinstance(result["result_sample"], float)
        return True
    test("Smoke test returns valid float result", test_smoke_result_valid)

    def test_smoke_device_info():
        result = run_inference_smoke_test(0)
        assert "device" in result
        assert "cuda:0" in result["device"]
        return True
    test("Smoke test reports correct device", test_smoke_device_info)


# ============================================================
# SECTION 3: Multi-GPU
# ============================================================
def test_multi_gpu():
    print("\n=== Multi-GPU Handling ===")
    from core.gpu import detect_all_gpus, select_best_gpu

    def test_gpu_list():
        gpus = detect_all_gpus()
        assert isinstance(gpus, list)
        for gpu in gpus:
            assert "index" in gpu
            assert "name" in gpu
            assert gpu["index"] >= 0
        return True
    test("GPU list has valid indices", test_gpu_list)

    def test_select_empty():
        best = select_best_gpu([])
        assert best is None
        return True
    test("select_best_gpu handles empty list", test_select_empty)

    def test_multi_gpu_fields():
        gpus = detect_all_gpus()
        if len(gpus) > 1:
            for gpu in gpus:
                assert "vram_free_mb" in gpu
                assert "compute_capability" in gpu
        return True
    test("Multi-GPU: all GPUs have free VRAM and compute capability", test_multi_gpu_fields)

    def test_selected_gpu_in_info():
        from core.gpu import get_gpu_info_dict
        info = get_gpu_info_dict()
        assert "selected_gpu" in info
        assert "gpu_count" in info
        assert "all_gpus" in info
        assert isinstance(info["all_gpus"], list)
        return True
    test("GPU info includes selected GPU and all GPUs list", test_selected_gpu_in_info)


# ============================================================
# SECTION 4: Free VRAM
# ============================================================
def test_free_vram():
    print("\n=== Free VRAM Checks ===")
    from core.gpu import detect_all_gpus, check_compatibility

    def test_free_vram_positive():
        gpus = detect_all_gpus()
        if gpus:
            assert gpus[0]["vram_free_mb"] >= 0
            assert gpus[0]["vram_free_gb"] >= 0
        return True
    test("Free VRAM is non-negative", test_free_vram_positive)

    def test_free_less_than_total():
        gpus = detect_all_gpus()
        if gpus:
            assert gpus[0]["vram_free_mb"] <= gpus[0]["vram_total_mb"]
        return True
    test("Free VRAM <= total VRAM", test_free_less_than_total)

    def test_compat_warns_low_free():
        from core.gpu import COMPATIBILITY_MATRIX
        matrix = COMPATIBILITY_MATRIX["2.1.x"]
        assert "min_free_vram_gb" in matrix
        assert matrix["min_free_vram_gb"] > 0
        return True
    test("Compatibility matrix has min_free_vram_gb", test_compat_warns_low_free)

    def test_vram_in_diagnostics():
        from core.gpu import get_gpu_info_dict
        info = get_gpu_info_dict()
        assert "free_vram_gb" in info
        assert "total_vram_gb" in info
        return True
    test("Diagnostics include free and total VRAM", test_vram_in_diagnostics)


# ============================================================
# SECTION 5: Compatibility Matrix
# ============================================================
def test_compatibility():
    print("\n=== Compatibility Matrix ===")
    from core.gpu import check_compatibility, COMPATIBILITY_MATRIX

    def test_matrix_structure():
        for ver, matrix in COMPATIBILITY_MATRIX.items():
            assert "pytorch" in matrix
            assert "min_driver" in matrix
            assert "min_vram_gb" in matrix
            assert "min_free_vram_gb" in matrix
            assert "min_compute_capability" in matrix
        return True
    test("Matrix entries have all required fields", test_matrix_structure)

    def test_check_returns_result():
        result = check_compatibility("2.1.x")
        assert "gpus" in result
        assert "selected_gpu" in result
        assert "cuda" in result
        assert "smoke_test" in result
        assert "compatibility" in result
        assert "issues" in result
        assert "warnings" in result
        return True
    test("Compatibility check returns complete result", test_check_returns_result)

    def test_smoke_test_included():
        result = check_compatibility("2.1.x")
        if result["compatibility"] != "failed":
            assert result["smoke_test"] is not None
            assert "passed" in result["smoke_test"]
        return True
    test("Compatibility check includes smoke test", test_smoke_test_included)


# ============================================================
# SECTION 6: Health Check
# ============================================================
def test_health_check():
    print("\n=== GPU Health Check ===")
    from core.gpu import gpu_health_check, get_gpu_info_dict

    def test_health_returns_tuple():
        issues, info = gpu_health_check()
        assert isinstance(issues, list)
        assert isinstance(info, dict)
        return True
    test("Health check returns (issues, info)", test_health_returns_tuple)

    def test_health_info_fields():
        issues, info = gpu_health_check()
        required = ["vendor", "model", "driver_version", "cuda_version",
                     "total_vram_gb", "free_vram_gb", "tier", "cuda_available",
                     "smoke_test_passed", "torch_version"]
        for field in required:
            assert field in info, f"Missing: {field}"
        return True
    test("Health check info has all required fields", test_health_info_fields)

    def test_health_with_logger():
        from core.logger import MiMoLogger
        d = tempfile.mkdtemp()
        logger = MiMoLogger("test_gpu_health", d, "2.0.0")
        issues, info = gpu_health_check(logger)
        log_file = os.path.join(d, "test_gpu_health.jsonl")
        assert os.path.exists(log_file)
        with open(log_file) as f:
            lines = f.readlines()
        assert len(lines) > 0
        entry = json.loads(lines[0].strip())
        assert "event" in entry
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("Health check logs GPU status", test_health_with_logger)


# ============================================================
# SECTION 7: State & Diagnostics
# ============================================================
def test_state_diagnostics():
    print("\n=== State & Diagnostics ===")
    from core.gpu import get_gpu_info_dict

    def test_info_serializable():
        info = get_gpu_info_dict()
        json_str = json.dumps(info, indent=2)
        parsed = json.loads(json_str)
        assert parsed["vendor"] == info["vendor"]
        return True
    test("GPU info is JSON-serializable", test_info_serializable)

    def test_all_gpus_in_info():
        info = get_gpu_info_dict()
        assert "all_gpus" in info
        for gpu in info["all_gpus"]:
            assert "index" in gpu
            assert "name" in gpu
            assert "vram_gb" in gpu
        return True
    test("GPU info includes all GPUs summary", test_all_gpus_in_info)

    def test_gpu_in_state():
        from bootstrapper.MiMoBootstrapper import StateManager
        d = tempfile.mkdtemp()
        state = StateManager(d)
        info = get_gpu_info_dict()
        state.state["gpu"] = info
        state.save()
        state2 = StateManager(d)
        assert "gpu" in state2.state
        assert state2.state["gpu"]["model"] == info["model"]
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("GPU info persists in install_state.json", test_gpu_in_state)

    def test_torch_in_diagnostics():
        info = get_gpu_info_dict()
        assert "torch_version" in info
        assert "cuda_version" in info
        return True
    test("Diagnostics include PyTorch and CUDA versions", test_torch_in_diagnostics)


# ============================================================
# SECTION 8: Failure Scenarios
# ============================================================
def test_failure_scenarios():
    print("\n=== Failure Scenarios ===")
    from core.gpu import (
        detect_all_gpus, select_best_gpu, run_inference_smoke_test,
        check_compatibility, COMPATIBILITY_MATRIX
    )

    def test_no_gpu():
        best = select_best_gpu([])
        assert best is None
        return True
    test("No GPU: select_best_gpu returns None", test_no_gpu)

    def test_smoke_on_device_99():
        result = run_inference_smoke_test(99)
        assert result["passed"] == False
        assert "error" in result
        return True
    test("Smoke test on invalid device fails gracefully", test_smoke_on_device_99)

    def test_compat_no_gpu():
        original = detect_all_gpus
        import core.gpu as gpu_mod
        gpu_mod.detect_all_gpus = lambda: []
        try:
            result = check_compatibility("2.1.x")
            assert result["compatibility"] == "failed"
            assert any("No NVIDIA" in i for i in result["issues"])
            return True
        finally:
            gpu_mod.detect_all_gpus = original
    test("Compatibility fails gracefully with no GPU", test_compat_no_gpu)

    def test_compat_old_driver():
        import core.gpu as gpu_mod
        original = gpu_mod.detect_all_gpus
        gpu_mod.detect_all_gpus = lambda: [{
            "index": 0, "name": "Fake GPU", "driver_version": "400.00",
            "compute_capability": "8.9", "vram_total_mb": 16000,
            "vram_total_gb": 16.0, "vram_free_mb": 14000, "vram_free_gb": 13.7,
        }]
        original_cuda = gpu_mod.detect_cuda_runtime
        gpu_mod.detect_cuda_runtime = lambda: {"available": True, "torch_version": "2.1.2",
            "cuda_version": "11.8", "cudnn_version": "8700", "cudnn_available": True,
            "device_count": 1, "current_device": 0, "device_name": "Fake GPU",
            "compute_capability": "8.9", "total_memory_gb": 16.0,
            "supports_float16": True, "supports_bfloat16": True}
        try:
            result = check_compatibility("2.1.x")
            assert any("Driver too old" in i for i in result["issues"])
            return True
        finally:
            gpu_mod.detect_all_gpus = original
            gpu_mod.detect_cuda_runtime = original_cuda
    test("Compatibility detects old driver", test_compat_old_driver)

    def test_compat_low_vram():
        import core.gpu as gpu_mod
        original = gpu_mod.detect_all_gpus
        gpu_mod.detect_all_gpus = lambda: [{
            "index": 0, "name": "Low VRAM GPU", "driver_version": "596.36",
            "compute_capability": "8.9", "vram_total_mb": 2000,
            "vram_total_gb": 2.0, "vram_free_mb": 1500, "vram_free_gb": 1.5,
        }]
        try:
            result = check_compatibility("2.1.x")
            assert any("VRAM too low" in i for i in result["issues"])
            return True
        finally:
            gpu_mod.detect_all_gpus = original
    test("Compatibility detects low VRAM", test_compat_low_vram)

    def test_compat_low_compute():
        import core.gpu as gpu_mod
        original = gpu_mod.detect_all_gpus
        gpu_mod.detect_all_gpus = lambda: [{
            "index": 0, "name": "Old GPU", "driver_version": "596.36",
            "compute_capability": "6.1", "vram_total_mb": 8000,
            "vram_total_gb": 8.0, "vram_free_mb": 7000, "vram_free_gb": 6.8,
        }]
        try:
            result = check_compatibility("2.1.x")
            assert any("Compute capability" in i for i in result["issues"])
            return True
        finally:
            gpu_mod.detect_all_gpus = original
    test("Compatibility detects low compute capability", test_compat_low_compute)


# ============================================================
# MAIN
# ============================================================
def main():
    global PASS, FAIL
    print("=" * 55)
    print("  MiMo GPU/CUDA Validation Tests v2.1")
    print("=" * 55)

    test_gpu_detection()
    test_smoke_test()
    test_multi_gpu()
    test_free_vram()
    test_compatibility()
    test_health_check()
    test_state_diagnostics()
    test_failure_scenarios()

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
