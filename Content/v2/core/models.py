"""
MiMo Model VRAM Requirements — Maps models to minimum VRAM.
Prevents users from launching models that won't fit in memory.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


MODEL_TIERS = {
    "small": {
        "min_vram_gb": 4,
        "min_free_vram_gb": 2,
        "description": "Small models (1-3B params)",
        "examples": ["Qwen2-1.5B", "Phi-3-mini", "Gemma-2B"],
        "expected_latency_ms": 200,
    },
    "medium": {
        "min_vram_gb": 8,
        "min_free_vram_gb": 4,
        "description": "Medium models (3-7B params)",
        "examples": ["Qwen2-7B", "Llama-3-8B", "Mistral-7B"],
        "expected_latency_ms": 500,
    },
    "large": {
        "min_vram_gb": 12,
        "min_free_vram_gb": 6,
        "description": "Large models (7-13B params)",
        "examples": ["Llama-3-13B", "Qwen2-14B"],
        "expected_latency_ms": 1000,
    },
    "xl": {
        "min_vram_gb": 16,
        "min_free_vram_gb": 8,
        "description": "Extra-large models (13-30B params)",
        "examples": ["Llama-3-34B", "Qwen2-32B", "DeepSeek-Coder-33B"],
        "expected_latency_ms": 2000,
    },
    "xxl": {
        "min_vram_gb": 24,
        "min_free_vram_gb": 12,
        "description": "Massive models (30B+ params)",
        "examples": ["Llama-3-70B", "Qwen2-72B"],
        "expected_latency_ms": 5000,
    },
}

GPU_TIER_TO_MODEL_TIER = {
    "insufficient": None,
    "basic": "small",
    "good": "medium",
    "excellent": "large",
    "extreme": "xl",
}


def get_max_model_tier(total_vram_gb, free_vram_gb=None):
    """Determine the largest model tier that fits in VRAM."""
    if free_vram_gb is None:
        free_vram_gb = total_vram_gb * 0.7

    for tier_name in ["xxl", "xl", "large", "medium", "small"]:
        tier = MODEL_TIERS[tier_name]
        if total_vram_gb >= tier["min_vram_gb"] and free_vram_gb >= tier["min_free_vram_gb"]:
            return tier_name
    return None


def check_model_compatibility(tier_name, total_vram_gb, free_vram_gb):
    """Check if a specific model tier can run on the available VRAM."""
    tier = MODEL_TIERS.get(tier_name)
    if not tier:
        return {"compatible": False, "error": f"Unknown model tier: {tier_name}"}

    issues = []
    if total_vram_gb < tier["min_vram_gb"]:
        issues.append(
            f"VRAM too low: {total_vram_gb}GB total, "
            f"need {tier['min_vram_gb']}GB for {tier['description']}"
        )
    if free_vram_gb < tier["min_free_vram_gb"]:
        issues.append(
            f"Free VRAM too low: {free_vram_gb}GB free, "
            f"need {tier['min_free_vram_gb']}GB for {tier['description']}"
        )

    return {
        "compatible": len(issues) == 0,
        "tier": tier_name,
        "description": tier["description"],
        "issues": issues,
        "expected_latency_ms": tier["expected_latency_ms"],
        "examples": tier["examples"],
    }


def get_model_recommendation(total_vram_gb, free_vram_gb):
    """Recommend the best model tier for available VRAM."""
    max_tier = get_max_model_tier(total_vram_gb, free_vram_gb)
    if not max_tier:
        return {
            "recommended": None,
            "message": "VRAM insufficient for any supported model. Need 4GB+ total.",
        }

    tier = MODEL_TIERS[max_tier]
    return {
        "recommended": max_tier,
        "description": tier["description"],
        "examples": tier["examples"],
        "message": f"Recommended: {tier['description']} ({tier['examples'][0]})",
    }


def get_vram_warnings(total_vram_gb, free_vram_gb):
    """Get warnings about VRAM availability for models."""
    warnings = []
    max_tier = get_max_model_tier(total_vram_gb, free_vram_gb)

    if not max_tier:
        warnings.append("VRAM insufficient for any model. Close other GPU applications.")
        return warnings

    tier = MODEL_TIERS[max_tier]
    if free_vram_gb < tier["min_free_vram_gb"] * 1.5:
        warnings.append(
            f"Free VRAM is tight for {tier['description']}. "
            f"Close other GPU applications for best performance."
        )

    if total_vram_gb >= 8 and free_vram_gb < 4:
        warnings.append(
            f"Only {free_vram_gb}GB free out of {total_vram_gb}GB total. "
            f"Other applications may be using GPU memory."
        )

    return warnings


def model_tier_to_dict():
    """Export model tiers as JSON-serializable dict."""
    return {k: {**v, "tier_name": k} for k, v in MODEL_TIERS.items()}
