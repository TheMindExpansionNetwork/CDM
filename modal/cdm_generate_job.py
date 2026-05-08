from __future__ import annotations

import json
import modal

APP_NAME = "jimsky-cdm-radio-generate-job"
HF_CACHE = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
OUTPUTS = modal.Volume.from_name("outputs", create_if_missing=True)

gpu_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "ffmpeg", "libgl1", "libglib2.0-0")
    .pip_install(
        "torch<=2.6.0",
        "torchvision",
        "diffusers>=0.35.0",
        "transformers>=4.55.0",
        "accelerate",
        "safetensors",
        "sentencepiece",
        "protobuf",
        "pillow",
        "huggingface_hub[hf_transfer]",
    )
)

app = modal.App(APP_NAME)


def normalize_request(prompt: str, loop_id: str, seed: int, width: int, height: int, steps: int, guidance_scale: float) -> dict:
    return {
        "prompt": str(prompt)[:1200],
        "model": "byliutao/stable-diffusion-3-medium-turbo",
        "width": max(512, min(int(width), 1536)),
        "height": max(512, min(int(height), 1536)),
        "steps": max(1, min(int(steps), 8)),
        "guidance_scale": float(guidance_scale),
        "seed": int(seed),
        "loop_id": "".join(c if c.isalnum() or c in "-_" else "-" for c in str(loop_id))[:80] or "manual",
        "sigmas": [1.0, 0.75, 0.5, 0.25],
    }


@app.cls(
    image=gpu_image,
    gpu="A10G",
    timeout=900,
    scaledown_window=180,
    volumes={"/cache": HF_CACHE, "/outputs": OUTPUTS},
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
class CDMJobGenerator:
    @modal.enter()
    def load(self):
        import os
        import torch
        from diffusers import StableDiffusion3Pipeline
        os.environ.setdefault("HF_HOME", "/cache/huggingface")
        os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")
        self.torch = torch
        self.pipeline_name = "byliutao/stable-diffusion-3-medium-turbo"
        self.pipe = StableDiffusion3Pipeline.from_pretrained(
            self.pipeline_name,
            torch_dtype=torch.bfloat16,
        )
        self.pipe.to("cuda")
        try:
            self.pipe.set_progress_bar_config(disable=True)
        except Exception:
            pass

    @modal.method()
    def generate(self, cfg: dict) -> dict:
        import datetime as dt
        import hashlib
        import json
        from pathlib import Path
        gen = self.torch.Generator("cuda").manual_seed(int(cfg["seed"]))
        image = self.pipe(
            cfg["prompt"],
            height=int(cfg["height"]),
            width=int(cfg["width"]),
            num_inference_steps=int(cfg["steps"]),
            sigmas=cfg["sigmas"],
            guidance_scale=float(cfg["guidance_scale"]),
            generator=gen,
        ).images[0]
        ts = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        out_dir = Path("/outputs/cdm-radio-loop") / cfg["loop_id"]
        out_dir.mkdir(parents=True, exist_ok=True)
        png_path = out_dir / f"{ts}_seed{cfg['seed']}.png"
        image.save(png_path)
        data = png_path.read_bytes()
        manifest = {
            "ok": True,
            "utc": ts,
            "app": APP_NAME,
            "request": cfg,
            "output_volume_path": str(png_path),
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "realtime_note": "No-web Modal job for timer/radio-loop use. Warm A10G container targets fast 4-NFE visual refreshes.",
        }
        png_path.with_suffix(".json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        OUTPUTS.commit()
        return manifest


@app.local_entrypoint()
def main(
    prompt: str = "Sonic-Forage neon strawberry radio station visual, no text",
    loop_id: str = "sonic-radio-loop",
    seed: int = 2045,
    width: int = 1024,
    height: int = 1024,
    steps: int = 4,
    guidance_scale: float = 1.0,
    dry_run: bool = True,
):
    cfg = normalize_request(prompt, loop_id, seed, width, height, steps, guidance_scale)
    if dry_run:
        print(json.dumps({"ok": True, "dry_run": True, "gpu_started": False, "model_download_started": False, "request": cfg}, indent=2))
    else:
        print(json.dumps(CDMJobGenerator().generate.remote(cfg), indent=2))
