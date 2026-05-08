from __future__ import annotations

import json
import modal

APP_NAME = "jimsky-cdm-radio-jobs"
OUTPUTS = modal.Volume.from_name("outputs", create_if_missing=True)
HF_CACHE = modal.Volume.from_name("huggingface-cache", create_if_missing=True)

image = modal.Image.debian_slim(python_version="3.10").pip_install("huggingface_hub", "requests")
app = modal.App(APP_NAME)


@app.function(image=image, cpu=0.25, memory=512, timeout=180, volumes={"/outputs": OUTPUTS, "/cache": HF_CACHE}, secrets=[modal.Secret.from_name("huggingface-secret")])
def readiness() -> str:
    import datetime as dt
    import json
    import os
    from pathlib import Path
    from huggingface_hub import model_info

    models = ["byliutao/stable-diffusion-3-medium-turbo", "byliutao/Longcat-Image-Turbo"]
    infos = []
    for model in models:
        try:
            info = model_info(model, token=os.getenv("HF_TOKEN") or None)
            infos.append({"model": model, "ok": True, "private": bool(getattr(info, "private", False)), "siblings": len(getattr(info, "siblings", []) or [])})
        except Exception as exc:
            infos.append({"model": model, "ok": False, "error": type(exc).__name__})
    payload = {
        "ok": all(x["ok"] for x in infos),
        "utc": dt.datetime.utcnow().isoformat() + "Z",
        "gpu_started": False,
        "model_download_started": False,
        "hf_token_present": bool(os.getenv("HF_TOKEN")),
        "models": infos,
        "next_gate": "Deploy cdm_realtime_app.py and call /v1/generate only when ready to spend GPU/model-cache time.",
    }
    out = Path("/outputs/cdm-radio-loop/readiness.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    OUTPUTS.commit()
    return json.dumps(payload, indent=2)


@app.local_entrypoint()
def main(mode: str = "readiness"):
    if mode != "readiness":
        raise SystemExit("cdm_radio_jobs.py is CPU/readiness-only. Use modal/cdm_gpu_probe.py --mode gpu-probe for the optional GPU probe.")
    print(readiness.remote())
