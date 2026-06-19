"""
MiMo CUDA/GPU Management v2.1 — PyTorch-based inference stack.
Detects GPU, driver, CUDA runtime. Runs inference smoke test.
Multi-GPU selection. Free VRAM validation.
"""
import os
import sys
import json
import subprocess
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


COMPATIBILITY_MATRIX = {
    "2.1.x": {
        "pytorch": "2.1.2+cu118",
        "min_driver": 522,
        "min_vram_gb": 4,
        "min_free_vram_gb": 2,
        "min_compute_capability": "7.5",
    },
    "2.2.x": {
        "pytorch": "2.2.0+cu121",
        "min_driver": 545,
        "min_vram_gb": 4,
        "min_free_vram_gb": 2,
        "min_compute_capability": "7.5",
    },
}

GPU_TIERS = {
    "basic": {"min_gb": 4, "label": "Basic — MiMo will run but slowly"},
    "good": {"min_gb": 8, "label": "Good — comfortable for most tasks"},
    "excellent": {"min_gb": 12, "label": "Excellent — fast inference"},
    "extreme": {"min_gb": 24, "label": "Extreme — maximum performance"},
}


def run_cmd(cmd, timeout=15):
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception:
        return False, "", ""


def _version_num(v):
    try:
        return float(".".join(v.split(".")[:2]))
    except Exception:
        return 0.0


def detect_all_gpus():
    """Detect all NVIDIA GPUs via nvidia-smi."""
    smi_paths = [
        "nvidia-smi",
        "C:\\Windows\\System32\\nvidia-smi.exe",
        "C:\\Program Files\\NVIDIA Corporation\\NVSMI\\nvidia-smi.exe",
    ]
    for smi in smi_paths:
        ok, out, err = run_cmd(
            [smi, "--query-gpu=index,name,driver_version,compute_cap,memory.total,memory.free",
             "--format=csv,noheader,nounits"],
            timeout=10
        )
        if ok and out:
            gpus = []
            for line in out.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 6:
                    gpus.append({
                        "index": int(parts[0]),
                        "name": parts[1],
                        "driver_version": parts[2],
                        "compute_capability": parts[3],
                        "vram_total_mb": int(parts[4]),
                        "vram_total_gb": round(int(parts[4]) / 1024, 1),
                        "vram_free_mb": int(parts[5]),
                        "vram_free_gb": round(int(parts[5]) / 1024, 1),
                    })
            return gpus
    return []


def select_best_gpu(gpus):
    """Select the best GPU: highest compute capability, most free VRAM."""
    if not gpus:
        return None
    scored = []
    for gpu in gpus:
        try:
            cc = float(gpu["compute_capability"])
        except Exception:
            cc = 0.0
        score = cc * 1000 + gpu["vram_free_mb"]
        scored.append((score, gpu))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def detect_cuda_runtime():
    """Detect CUDA runtime via PyTorch."""
    try:
        import torch
        if not torch.cuda.is_available():
            return {"available": False, "error": "torch.cuda.is_available() = False"}
        props = torch.cuda.get_device_properties(0)
        return {
            "available": True,
            "torch_version": torch.__version__,
            "cuda_version": torch.version.cuda or "unknown",
            "cudnn_version": str(torch.backends.cudnn.version()) if torch.backends.cudnn.is_available() else "N/A",
            "cudnn_available": torch.backends.cudnn.is_available(),
            "device_count": torch.cuda.device_count(),
            "current_device": torch.cuda.current_device(),
            "device_name": props.name,
            "compute_capability": f"{props.major}.{props.minor}",
            "total_memory_gb": round(props.total_mem / (1024**3), 1),
            "supports_float16": props.major >= 7,
            "supports_bfloat16": props.major >= 8,
        }
    except ImportError:
        return {"available": False, "error": "PyTorch not installed"}
    except Exception as e:
        return {"available": False, "error": str(e)}


def run_inference_smoke_test(device_index=0):
    """Run a tiny GPU workload to verify CUDA works end-to-end."""
    try:
        import torch
        if not torch.cuda.is_available():
            return {"passed": False, "error": "CUDA not available"}

        start = time.time()
        device = torch.device(f"cuda:{device_index}")

        x = torch.randn(1024, 1024, device=device, dtype=torch.float32)
        y = x @ x
        torch.cuda.synchronize()
        elapsed_ms = (time.time() - start) * 1000

        result_val = y[0][0].item()
        if not isinstance(result_val, float):
            return {"passed": False, "error": "Unexpected result type"}

        return {
            "passed": True,
            "elapsed_ms": round(elapsed_ms, 2),
            "matrix_size": "1024x1024",
            "device": str(device),
            "result_sample": round(result_val, 4),
        }
    except torch.cuda.OutOfMemoryError:
        return {"passed": False, "error": "CUDA out of memory"}
    except Exception as e:
        return {"passed": False, "error": str(e)}


def check_compatibility(app_version="2.1.x"):
    """Full CUDA compatibility check with smoke test."""
    result = {
        "gpus": detect_all_gpus(),
        "selected_gpu": None,
        "cuda": detect_cuda_runtime(),
        "smoke_test": None,
        "compatibility": "unknown",
        "issues": [],
        "warnings": [],
    }

    matrix = COMPATIBILITY_MATRIX.get(app_version, COMPATIBILITY_MATRIX["2.1.x"])

    if not result["gpus"]:
        result["issues"].append("No NVIDIA GPU detected")
        result["compatibility"] = "failed"
        return result

    result["selected_gpu"] = select_best_gpu(result["gpus"])
    gpu = result["selected_gpu"]

    try:
        cc = float(gpu["compute_capability"])
        min_cc = float(matrix["min_compute_capability"])
        if cc < min_cc:
            result["issues"].append(
                f"Compute capability too low: {gpu['compute_capability']} < {matrix['min_compute_capability']}"
            )
    except Exception:
        pass

    try:
        driver = _version_num(gpu["driver_version"])
        if driver < matrix["min_driver"]:
            result["issues"].append(
                f"Driver too old: {gpu['driver_version']} < {matrix['min_driver']}.0"
            )
    except Exception:
        pass

    if gpu["vram_total_gb"] < matrix["min_vram_gb"]:
        result["issues"].append(
            f"VRAM too low: {gpu['vram_total_gb']}GB < {matrix['min_vram_gb']}GB required"
        )

    if gpu["vram_free_gb"] < matrix["min_free_vram_gb"]:
        result["warnings"].append(
            f"Low free VRAM: {gpu['vram_free_gb']}GB free (recommend {matrix['min_free_vram_gb']}GB+)"
        )

    if not result["cuda"]["available"]:
        result["issues"].append("CUDA runtime not available (PyTorch CUDA build required)")
    else:
        if result["cuda"]["device_count"] > 1:
            result["warnings"].append(
                f"Multiple GPUs detected ({result['cuda']['device_count']}). "
                f"Selected: {gpu['name']}"
            )

    if result["issues"]:
        result["compatibility"] = "failed"
    elif result["warnings"]:
        result["compatibility"] = "warning"
    else:
        result["compatibility"] = "ok"

    if result["compatibility"] != "failed":
        result["smoke_test"] = run_inference_smoke_test(gpu["index"])
        if not result["smoke_test"]["passed"]:
            result["issues"].append(
                f"Inference smoke test failed: {result['smoke_test']['error']}"
            )
            result["compatibility"] = "failed"

    return result


def get_gpu_info_dict():
    """Get full GPU info as JSON-serializable dict for state/diagnostics."""
    gpus = detect_all_gpus()
    selected = select_best_gpu(gpus)
    cuda = detect_cuda_runtime()
    smoke = run_inference_smoke_test(selected["index"]) if selected else None

    def _tier_from_gb(gb):
        if gb >= 24: return "extreme"
        if gb >= 12: return "excellent"
        if gb >= 8: return "good"
        if gb >= 4: return "basic"
        return "insufficient"

    return {
        "vendor": "NVIDIA" if gpus else "none",
        "gpu_count": len(gpus),
        "selected_gpu": selected["index"] if selected else -1,
        "model": selected["name"] if selected else "not detected",
        "driver_version": selected["driver_version"] if selected else "unknown",
        "compute_capability": selected["compute_capability"] if selected else "unknown",
        "total_vram_gb": selected["vram_total_gb"] if selected else 0,
        "free_vram_gb": selected["vram_free_gb"] if selected else 0,
        "tier": _tier_from_gb(selected["vram_total_gb"]) if selected else "insufficient",
        "cuda_available": cuda.get("available", False),
        "torch_version": cuda.get("torch_version", "unknown"),
        "cuda_version": cuda.get("cuda_version", "unknown"),
        "cudnn_version": cuda.get("cudnn_version", "unknown"),
        "smoke_test_passed": smoke["passed"] if smoke else False,
        "all_gpus": [{"index": g["index"], "name": g["name"],
                      "vram_gb": g["vram_total_gb"]} for g in gpus],
    }


def gpu_health_check(logger=None):
    """Launch-time GPU validation with smoke test."""
    info = get_gpu_info_dict()
    issues = []

    if not info["cuda_available"]:
        issues.append("CUDA runtime unavailable")
        if logger:
            logger.error("GPU health: CUDA unavailable", event="gpu_cuda_unavailable")

    if info["total_vram_gb"] < 4:
        issues.append(f"VRAM insufficient: {info['total_vram_gb']}GB (need 4GB+)")
        if logger:
            logger.warn(f"GPU health: low VRAM ({info['total_vram_gb']}GB)", event="gpu_low_vram")

    if info["free_vram_gb"] < 2 and info["total_vram_gb"] >= 4:
        issues.append(f"Free VRAM low: {info['free_vram_gb']}GB (need 2GB+)")
        if logger:
            logger.warn(f"GPU health: low free VRAM ({info['free_vram_gb']}GB)",
                        event="gpu_low_free_vram")

    if info["vendor"] == "none":
        issues.append("No NVIDIA GPU detected")
        if logger:
            logger.error("GPU health: no GPU", event="gpu_not_found")

    if info["driver_version"] == "unknown":
        issues.append("Driver version unknown")
        if logger:
            logger.warn("GPU health: driver unknown", event="gpu_driver_unknown")

    if not info["smoke_test_passed"] and info["cuda_available"]:
        issues.append("Inference smoke test failed")
        if logger:
            logger.error("GPU health: smoke test failed", event="gpu_smoke_failed")

    if not issues and logger:
        logger.info(
            f"GPU health: {info['model']} ({info['total_vram_gb']}GB, "
            f"free {info['free_vram_gb']}GB) — smoke test passed",
            event="gpu_healthy", gpu=info["model"]
        )

    return issues, info
