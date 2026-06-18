"""
MiMo Model VRAM + Inference Validation Tests
Tests: model tiers, VRAM checks, recommendations, performance telemetry
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
# SECTION 1: Model Tiers
# ============================================================
def test_model_tiers():
    print("\n=== Model VRAM Tiers ===")
    from core.models import MODEL_TIERS, get_max_model_tier, model_tier_to_dict

    def test_all_tiers_exist():
        expected = ["small", "medium", "large", "xl", "xxl"]
        for tier in expected:
            assert tier in MODEL_TIERS, f"Missing tier: {tier}"
        return True
    test("All 5 model tiers defined", test_all_tiers_exist)

    def test_tier_fields():
        for name, tier in MODEL_TIERS.items():
            assert "min_vram_gb" in tier
            assert "min_free_vram_gb" in tier
            assert "description" in tier
            assert "examples" in tier
            assert "expected_latency_ms" in tier
            assert tier["min_vram_gb"] > 0
            assert tier["min_free_vram_gb"] > 0
            assert len(tier["examples"]) > 0
        return True
    test("All tiers have required fields", test_tier_fields)

    def test_tier_vram_ordering():
        prev = 0
        for name in ["small", "medium", "large", "xl", "xxl"]:
            assert MODEL_TIERS[name]["min_vram_gb"] > prev
            prev = MODEL_TIERS[name]["min_vram_gb"]
        return True
    test("Tiers increase in VRAM requirements", test_tier_vram_ordering)

    def test_max_tier_4gb():
        tier = get_max_model_tier(4, 3)
        assert tier == "small"
        return True
    test("4GB VRAM -> small tier", test_max_tier_4gb)

    def test_max_tier_8gb():
        tier = get_max_model_tier(8, 6)
        assert tier == "medium"
        return True
    test("8GB VRAM -> medium tier", test_max_tier_8gb)

    def test_max_tier_12gb():
        tier = get_max_model_tier(12, 8)
        assert tier == "large"
        return True
    test("12GB VRAM -> large tier", test_max_tier_12gb)

    def test_max_tier_16gb():
        tier = get_max_model_tier(16, 12)
        assert tier == "xl"
        return True
    test("16GB VRAM -> xl tier", test_max_tier_16gb)

    def test_max_tier_24gb():
        tier = get_max_model_tier(24, 16)
        assert tier == "xxl"
        return True
    test("24GB VRAM -> xxl tier", test_max_tier_24gb)

    def test_max_tier_2gb():
        tier = get_max_model_tier(2, 1)
        assert tier is None
        return True
    test("2GB VRAM -> no tier (insufficient)", test_max_tier_2gb)

    def test_dict_serializable():
        d = model_tier_to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert "small" in parsed
        assert "xxl" in parsed
        return True
    test("Model tiers are JSON-serializable", test_dict_serializable)


# ============================================================
# SECTION 2: Model Compatibility
# ============================================================
def test_model_compatibility():
    print("\n=== Model Compatibility ===")
    from core.models import check_model_compatibility, MODEL_TIERS

    def test_small_on_4gb():
        result = check_model_compatibility("small", 4, 3)
        assert result["compatible"] == True
        assert result["tier"] == "small"
        return True
    test("Small model on 4GB: compatible", test_small_on_4gb)

    def test_medium_on_4gb():
        result = check_model_compatibility("medium", 4, 3)
        assert result["compatible"] == False
        assert len(result["issues"]) > 0
        return True
    test("Medium model on 4GB: incompatible", test_medium_on_4gb)

    def test_xl_on_16gb():
        result = check_model_compatibility("xl", 16, 12)
        assert result["compatible"] == True
        return True
    test("XL model on 16GB: compatible", test_xl_on_16gb)

    def test_low_free_vram():
        result = check_model_compatibility("large", 16, 3)
        assert result["compatible"] == False
        assert any("Free VRAM" in i for i in result["issues"])
        return True
    test("Large model with low free VRAM: incompatible", test_low_free_vram)

    def test_unknown_tier():
        result = check_model_compatibility("nonexistent", 16, 12)
        assert result["compatible"] == False
        assert "Unknown" in result["error"]
        return True
    test("Unknown model tier: returns error", test_unknown_tier)

    def test_latency_included():
        result = check_model_compatibility("small", 4, 3)
        assert "expected_latency_ms" in result
        assert result["expected_latency_ms"] > 0
        return True
    test("Compatibility result includes latency estimate", test_latency_included)

    def test_examples_included():
        result = check_model_compatibility("medium", 8, 6)
        assert "examples" in result
        assert len(result["examples"]) > 0
        return True
    test("Compatibility result includes model examples", test_examples_included)


# ============================================================
# SECTION 3: Recommendations
# ============================================================
def test_recommendations():
    print("\n=== Model Recommendations ===")
    from core.models import get_model_recommendation, get_vram_warnings

    def test_recommend_4gb():
        rec = get_model_recommendation(4, 3)
        assert rec["recommended"] == "small"
        assert "small" in rec["message"].lower()
        return True
    test("Recommend small for 4GB", test_recommend_4gb)

    def test_recommend_16gb():
        rec = get_model_recommendation(16, 12)
        assert rec["recommended"] == "xl"
        return True
    test("Recommend xl for 16GB", test_recommend_16gb)

    def test_recommend_2gb():
        rec = get_model_recommendation(2, 1)
        assert rec["recommended"] is None
        assert "insufficient" in rec["message"].lower()
        return True
    test("No recommendation for 2GB", test_recommend_2gb)

    def test_warnings_tight_vram():
        warnings = get_vram_warnings(8, 2)
        assert len(warnings) > 0
        return True
    test("Warning when free VRAM is tight", test_warnings_tight_vram)

    def test_warnings_no_vram():
        warnings = get_vram_warnings(2, 1)
        assert len(warnings) > 0
        assert "insufficient" in warnings[0].lower() or "close" in warnings[0].lower()
        return True
    test("Warning when VRAM insufficient", test_warnings_no_vram)

    def test_no_warnings_plenty():
        warnings = get_vram_warnings(16, 12)
        assert len(warnings) == 0
        return True
    test("No warnings with plenty of VRAM", test_no_warnings_plenty)


# ============================================================
# SECTION 4: Performance Telemetry
# ============================================================
def test_performance_telemetry():
    print("\n=== Performance Telemetry ===")
    from core.gpu import run_inference_smoke_test, get_gpu_info_dict

    def test_smoke_test_timing():
        result = run_inference_smoke_test(0)
        assert "elapsed_ms" in result
        assert result["elapsed_ms"] > 0
        assert result["elapsed_ms"] < 10000
        return True
    test("Smoke test reports timing", test_smoke_test_timing)

    def test_gpu_info_performance():
        info = get_gpu_info_dict()
        assert "smoke_test_passed" in info
        assert "total_vram_gb" in info
        assert "free_vram_gb" in info
        assert "tier" in info
        return True
    test("GPU info includes performance metrics", test_gpu_info_performance)

    def test_telemetry_serializable():
        info = get_gpu_info_dict()
        json_str = json.dumps(info, indent=2)
        parsed = json.loads(json_str)
        assert parsed["smoke_test_passed"] == info["smoke_test_passed"]
        return True
    test("Performance telemetry is JSON-serializable", test_telemetry_serializable)

    def test_full_diagnostics_bundle():
        from core.gpu import get_gpu_info_dict
        from core.models import model_tier_to_dict, get_model_recommendation
        info = get_gpu_info_dict()
        tiers = model_tier_to_dict()
        rec = get_model_recommendation(info["total_vram_gb"], info["free_vram_gb"])
        bundle = {
            "gpu": info,
            "model_tiers": tiers,
            "recommendation": rec,
        }
        json_str = json.dumps(bundle, indent=2)
        parsed = json.loads(json_str)
        assert "gpu" in parsed
        assert "model_tiers" in parsed
        assert "recommendation" in parsed
        return True
    test("Full diagnostics bundle is complete and serializable", test_full_diagnostics_bundle)


# ============================================================
# SECTION 5: Integration with State
# ============================================================
def test_state_integration():
    print("\n=== State Integration ===")
    from core.gpu import get_gpu_info_dict
    from core.models import get_model_recommendation, get_max_model_tier

    def test_gpu_state_includes_vram():
        info = get_gpu_info_dict()
        d = tempfile.mkdtemp()
        state_path = os.path.join(d, "install_state.json")
        state = {
            "version": "2.0.0",
            "gpu": info,
            "model_recommendation": get_model_recommendation(
                info["total_vram_gb"], info["free_vram_gb"]
            ),
        }
        with open(state_path, "w") as f:
            json.dump(state, f, indent=2)
        with open(state_path) as f:
            loaded = json.load(f)
        assert loaded["gpu"]["total_vram_gb"] == info["total_vram_gb"]
        assert "recommended" in loaded["model_recommendation"]
        shutil.rmtree(d, ignore_errors=True)
        return True
    test("GPU + model info persists in state", test_gpu_state_includes_vram)

    def test_max_tier_matches_gpu_tier():
        from core.gpu import get_gpu_info_dict
        info = get_gpu_info_dict()
        max_model = get_max_model_tier(info["total_vram_gb"], info["free_vram_gb"])
        gpu_tier = info["tier"]
        tier_order = {"insufficient": 0, "basic": 1, "good": 2, "excellent": 3, "extreme": 4}
        model_order = {"small": 1, "medium": 2, "large": 3, "xl": 4, "xxl": 5}
        if max_model:
            assert model_order.get(max_model, 0) <= tier_order.get(gpu_tier, 0) + 1
        return True
    test("Max model tier aligns with GPU tier", test_max_tier_matches_gpu_tier)


# ============================================================
# MAIN
# ============================================================
def main():
    global PASS, FAIL
    print("=" * 55)
    print("  MiMo Model VRAM + Inference Validation Tests")
    print("=" * 55)

    test_model_tiers()
    test_model_compatibility()
    test_recommendations()
    test_performance_telemetry()
    test_state_integration()

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
