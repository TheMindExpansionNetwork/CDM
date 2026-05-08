from __future__ import annotations

import json
import modal

APP_NAME = "jimsky-cdm-realtime-radio"
HF_CACHE = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
OUTPUTS = modal.Volume.from_name("outputs", create_if_missing=True)

# CPU shell stays cheap. GPU image is isolated behind explicit allow_gpu route.
cpu_image = modal.Image.debian_slim(python_version="3.10").pip_install(
    "fastapi>=0.110",
    "pydantic>=2",
)

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


def _json_primitive_generate(req: dict) -> dict:
    prompt = str(req.get("prompt") or "Sonic-Forage cyberpunk strawberry radio station album cover, neon rave, safe original art")[:1200]
    model = str(req.get("model") or "sd3").lower()
    width = int(req.get("width") or 1024)
    height = int(req.get("height") or 1024)
    steps = int(req.get("steps") or 4)
    guidance_scale = float(req.get("guidance_scale") or 1.0)
    seed = int(req.get("seed") or 2045)
    loop_id = str(req.get("loop_id") or "manual")[:80]
    return {
        "prompt": prompt,
        "model": model,
        "width": max(512, min(width, 1536)),
        "height": max(512, min(height, 1536)),
        "steps": max(1, min(steps, 8)),
        "guidance_scale": guidance_scale,
        "seed": seed,
        "loop_id": loop_id,
        "sigmas": req.get("sigmas") or [1.0, 0.75, 0.5, 0.25],
    }


@app.cls(
    image=gpu_image,
    gpu="A10G",
    timeout=900,
    scaledown_window=180,
    volumes={"/cache": HF_CACHE, "/outputs": OUTPUTS},
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
class CDMGenerator:
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
    def generate(self, req: dict) -> dict:
        import base64
        import datetime as dt
        import hashlib
        import io
        import json
        from pathlib import Path

        cfg = _json_primitive_generate(req)
        if cfg["model"] not in {"sd3", "sd3-medium"}:
            raise ValueError("This first realtime wrapper supports sd3 only; LongCat support is scaffolded for a later dependency probe.")
        gen = self.torch.Generator("cuda").manual_seed(cfg["seed"])
        image = self.pipe(
            cfg["prompt"],
            height=cfg["height"],
            width=cfg["width"],
            num_inference_steps=cfg["steps"],
            sigmas=cfg["sigmas"],
            guidance_scale=cfg["guidance_scale"],
            generator=gen,
        ).images[0]
        ts = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        safe_loop = "".join(c if c.isalnum() or c in "-_" else "-" for c in cfg["loop_id"])[:80] or "manual"
        out_dir = Path("/outputs/cdm-radio-loop") / safe_loop
        out_dir.mkdir(parents=True, exist_ok=True)
        png_path = out_dir / f"{ts}_seed{cfg['seed']}.png"
        image.save(png_path)
        data = png_path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        manifest = {
            "ok": True,
            "utc": ts,
            "model": self.pipeline_name,
            "request": cfg,
            "output_volume_path": str(png_path),
            "sha256": sha,
            "bytes": len(data),
            "realtime_note": "Warm 4-NFE generation target for radio-loop visuals; cold starts include model load/cache time.",
        }
        manifest_path = png_path.with_suffix(".json")
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        OUTPUTS.commit()
        if bool(req.get("return_base64")):
            manifest["image_base64_png"] = base64.b64encode(data).decode("ascii")
        return manifest


@app.function(image=cpu_image, cpu=0.25, memory=512, timeout=180, scaledown_window=60)
@modal.asgi_app()
def api():
    from fastapi import Body, FastAPI, Header, HTTPException
    import os
    import datetime as dt

    web = FastAPI(title="Jimsky CDM Realtime Radio Visual API", version="0.1.0")

    def guard(auth_header: str | None, body: dict):
        token = os.getenv("CDM_API_TOKEN")
        if token:
            expected = "Bearer " + token
            if auth_header != expected:
                raise HTTPException(status_code=403, detail="missing or invalid bearer token")
        if not bool(body.get("allow_gpu")):
            raise HTTPException(status_code=400, detail="GPU generation is closed by default; pass allow_gpu=true intentionally.")

    @web.get("/health")
    def health():
        return {
            "ok": True,
            "app": APP_NAME,
            "utc": dt.datetime.utcnow().isoformat() + "Z",
            "gpu_started": False,
            "routes": ["/health", "/v1/dry-run", "/v1/generate"],
            "safety": "POST /v1/generate requires allow_gpu=true and optional CDM_API_TOKEN bearer guard if secret is configured.",
        }

    @web.post("/v1/dry-run")
    def dry_run(body: dict = Body(default_factory=dict)):
        cfg = _json_primitive_generate(body)
        return {
            "ok": True,
            "gpu_started": False,
            "normalized_request": cfg,
            "radio_loop_use": "Use this to validate prompts/timers without waking a GPU.",
        }

    @web.post("/v1/generate")
    async def generate(body: dict = Body(default_factory=dict), authorization: str | None = Header(default=None)):
        guard(authorization, body)
        return await CDMGenerator().generate.remote.aio(body)

    return web


@app.local_entrypoint()
def main(prompt: str = "Sonic-Forage neon strawberry radio station visual", dry_run: bool = True):
    req = {"prompt": prompt, "loop_id": "local-entrypoint", "allow_gpu": not dry_run}
    if dry_run:
        print(json.dumps({"ok": True, "dry_run": True, "request": _json_primitive_generate(req)}, indent=2))
    else:
        print(json.dumps(CDMGenerator().generate.remote(req), indent=2))
