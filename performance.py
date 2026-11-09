"""Memory policy only: never change weights, pitch, diffusion steps or mix."""
import os

PROFILES = {"low": "6 GB 节省显存", "balanced": "8 GB 均衡", "fast": "12 GB+ 性能优先"}


def choose_profile(total_mib, free_mib, requested="auto"):
    if requested not in {"auto", *PROFILES}:
        raise ValueError("未知性能档位，请使用自动选择。")
    if total_mib < 5500:
        raise ValueError("需要 6 GB 级或以上 NVIDIA 显卡。")
    available = min(total_mib, free_mib)
    automatic = "fast" if available >= 11000 else "balanced" if available >= 7200 else "low"
    order = ["low", "balanced", "fast"]
    return automatic if requested == "auto" else order[min(order.index(requested), order.index(automatic))]


def configure(request):
    import torch
    free, total = torch.cuda.mem_get_info()
    profile = choose_profile(total / 1024**2, free / 1024**2, request.get("performance", "auto"))
    # Diagnostic budget limits PyTorch's allocator, not all driver allocations.
    budget = os.getenv("VOICE_TEST_BUDGET_MIB")
    if budget:
        torch.cuda.set_per_process_memory_fraction(min(float(budget) * 1024**2 / total, 1))
    torch.cuda.reset_peak_memory_stats()
    return {"profile": profile, "label": PROFILES[profile], "gpu": torch.cuda.get_device_name(),
            "total_mib": round(total / 1024**2), "free_mib": round(free / 1024**2),
            "allocator_budget_mib": float(budget) if budget else None}


def memory_report(policy):
    import torch
    return dict(policy, peak_allocated_mib=round(torch.cuda.max_memory_allocated() / 1024**2, 1),
                peak_reserved_mib=round(torch.cuda.max_memory_reserved() / 1024**2, 1))
