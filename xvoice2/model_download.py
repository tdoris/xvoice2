"""
First-run model download helpers for the Parakeet (onnx-asr) engine.

The Parakeet model (~2.4 GB) is not bundled with the app; it is fetched from
Hugging Face on first use. These helpers let the GUI detect whether the model is
already cached and download it with a progress indicator, instead of the app
silently blocking on the first transcription.
"""

import os
from typing import Optional


def model_repo_id(model_name: str) -> Optional[str]:
    """Return the Hugging Face repo id for an onnx-asr model name, or None."""
    try:
        from onnx_asr import resolver
        return getattr(resolver, "model_repos", {}).get(model_name)
    except Exception:
        return None


def _cache_dir(model_name: str) -> Optional[str]:
    """Path to the model's Hugging Face cache directory, or None."""
    repo = model_repo_id(model_name)
    if not repo:
        return None
    from huggingface_hub import constants
    return os.path.join(constants.HF_HUB_CACHE, "models--" + repo.replace("/", "--"))


def is_model_cached(model_name: str) -> bool:
    """True if the model's ONNX weights are already present in the HF cache."""
    cache_dir = _cache_dir(model_name)
    if not cache_dir:
        return False
    snapshots = os.path.join(cache_dir, "snapshots")
    if not os.path.isdir(snapshots):
        return False
    for root, _dirs, files in os.walk(snapshots):
        if any(f.endswith(".onnx") for f in files):
            return True
    return False


def cache_bytes_on_disk(model_name: str) -> int:
    """Bytes currently downloaded for the model (for progress display).

    Counts only the ``blobs`` directory (the actual downloaded data) when
    present, so progress tracks the true total rather than double-counting the
    ``snapshots`` copies/links Hugging Face also creates.
    """
    cache_dir = _cache_dir(model_name)
    if not cache_dir or not os.path.isdir(cache_dir):
        return 0
    blobs = os.path.join(cache_dir, "blobs")
    target = blobs if os.path.isdir(blobs) else cache_dir
    total = 0
    for root, _dirs, files in os.walk(target):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def model_total_bytes(model_name: str) -> int:
    """Total download size from the HF repo metadata, or 0 if unavailable.

    A quick metadata-only network call; returns 0 offline so the caller can
    fall back to an indeterminate progress indicator.
    """
    repo = model_repo_id(model_name)
    if not repo:
        return 0
    try:
        from huggingface_hub import HfApi
        info = HfApi().model_info(repo, files_metadata=True)
        return sum((s.size or 0) for s in (info.siblings or []))
    except Exception:
        return 0


def download_model(model_name: str) -> None:
    """Download all files for the model into the HF cache (blocking).

    Safe to re-run: Hugging Face resumes partial downloads and skips complete
    files. Raises on network/repo errors.
    """
    repo = model_repo_id(model_name)
    if not repo:
        raise ValueError(f"Unknown model '{model_name}' (no Hugging Face repo mapping)")
    from huggingface_hub import snapshot_download
    snapshot_download(repo)
