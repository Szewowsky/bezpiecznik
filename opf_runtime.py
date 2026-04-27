"""
OPF singleton runtime — jeden globalny model loader używany przez Gradio i FastAPI.

Lazy load (model 3GB pobiera się przy pierwszym wywołaniu, ~30s).
Kolejne wywołania używają cached instance.
"""

from __future__ import annotations

import os

from opf import OPF

_MODEL: OPF | None = None
DEVICE = os.environ.get("OPF_DEVICE", "cpu")  # macOS Apple Silicon → tylko CPU


def get_model() -> OPF:
    """Lazy load OPF model on first call. Subsequent calls return cached instance."""
    global _MODEL
    if _MODEL is None:
        print(f"⏳ Loading OPF on {DEVICE.upper()} (first run downloads ~3 GB)...")
        _MODEL = OPF(device=DEVICE, output_mode="typed")
        print("✅ OPF loaded.")
    return _MODEL
