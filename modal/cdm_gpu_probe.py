from __future__ import annotations

import json
import modal

app = modal.App("jimsky-cdm-gpu-probe")


@app.function(image=modal.Image.debian_slim(python_version="3.10").pip_install("torch<=2.6.0"), gpu="T4", timeout=180)
def gpu_probe() -> str:
    import json
    import subprocess
    import torch
    smi = subprocess.check_output("nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader", shell=True, text=True).strip()
    return json.dumps({
        "ok": True,
        "gpu_started": True,
        "model_download_started": False,
        "nvidia_smi": smi,
        "torch": str(torch.__version__),
        "cuda": bool(torch.cuda.is_available()),
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }, indent=2)


@app.local_entrypoint()
def main(mode: str = "gpu-probe"):
    if mode != "gpu-probe":
        raise SystemExit(f"unknown mode: {mode}")
    print(gpu_probe.remote())
