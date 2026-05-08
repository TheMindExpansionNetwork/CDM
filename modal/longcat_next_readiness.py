from __future__ import annotations

import json
import modal

APP_NAME = "jimsky-longcat-next-control-readiness"
OUTPUTS = modal.Volume.from_name("outputs", create_if_missing=True)
HF_CACHE = modal.Volume.from_name("huggingface-cache", create_if_missing=True)

image = modal.Image.debian_slim(python_version="3.10").pip_install("huggingface_hub", "requests")
app = modal.App(APP_NAME)


@app.function(
    image=image,
    cpu=0.25,
    memory=512,
    timeout=180,
    volumes={"/outputs": OUTPUTS, "/cache": HF_CACHE},
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
def readiness() -> str:
    import datetime as dt
    import json
    import os
    from pathlib import Path
    from huggingface_hub import model_info

    repo = "meituan-longcat/LongCat-Next"
    try:
        info = model_info(repo, token=os.getenv("HF_TOKEN") or None, files_metadata=True)
        siblings = getattr(info, "siblings", []) or []
        top_files = []
        for s in siblings[:80]:
            top_files.append({"path": getattr(s, "rfilename", ""), "size": getattr(s, "size", None)})
        ok = True
        error = None
        tags = getattr(info, "tags", []) or []
    except Exception as exc:
        ok = False
        error = type(exc).__name__
        top_files = []
        tags = []
    payload = {
        "ok": ok,
        "utc": dt.datetime.utcnow().isoformat() + "Z",
        "repo": repo,
        "purpose": "CPU-only LongCat-Next readiness for multimodal director/edit-control bridge.",
        "gpu_started": False,
        "model_download_started": False,
        "hf_token_present": bool(os.getenv("HF_TOKEN")),
        "known_constraints": {
            "model_size": "74B class / large native multimodal model",
            "upstream_inference_cuda": ">=12.9",
            "modal_plan": "Do not download or start 74B model until GPU/quantization target is approved.",
        },
        "capabilities_to_route": ["image_understanding", "audio_understanding", "image_generation", "speech_synthesis", "audio_to_audio", "edit_prompt_control"],
        "tags": tags[:20],
        "sample_files": top_files[:30],
        "error": error,
    }
    out = Path("/outputs/cdm-radio-loop/longcat_next_readiness.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    OUTPUTS.commit()
    return json.dumps(payload, indent=2)


@app.local_entrypoint()
def main():
    print(readiness.remote())
