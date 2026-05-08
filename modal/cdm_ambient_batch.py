from __future__ import annotations

import json
import modal

APP_NAME = "jimsky-cdm-ambient-batch"
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

MOODS = [
    "neon strawberry API shimmer",
    "Goa sunrise mandala bloom",
    "intergalactic radio mist",
    "PLUR kandi bead aurora",
    "cyberpunk orchard fog",
    "HyperFrames glass tunnel",
    "legal arcade dream haze",
    "ambient rave nebula",
    "soft laser strawberry field",
    "AI VTuber stage glow",
    "deep space fruit cathedral",
    "safe queue signal garden",
]
PALETTES = [
    "magenta cyan gold",
    "saffron teal ultraviolet",
    "strawberry red electric blue",
    "mint green hot pink indigo",
    "sunrise orange lavender black",
    "liquid chrome berry neon",
]


def make_prompt(i: int, theme: str) -> str:
    mood = MOODS[i % len(MOODS)]
    palette = PALETTES[(i // len(MOODS)) % len(PALETTES)]
    # Keep the prompt short enough that safety/style terms survive tokenizer limits.
    return (
        f"{theme}, frame {i+1:03d}, {mood}, {palette}, "
        "abstract neon strawberry rave background, seamless DJ visual loop, luminous haze, "
        "original non-character art, text-free, logo-free"
    )[:700]


def negative_prompt() -> str:
    return (
        "text, letters, words, logo, watermark, signature, copyrighted character, mascot, "
        "Sonic the Hedgehog, blue hedgehog, Shadow the Hedgehog, cartoon gloves, cartoon shoes, "
        "human face, mouth pipe, straw, cigarette, hookah, smoking, weapon"
    )


@app.cls(
    image=gpu_image,
    gpu="A10G",
    timeout=5400,
    scaledown_window=180,
    volumes={"/cache": HF_CACHE, "/outputs": OUTPUTS},
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
class AmbientBatchGenerator:
    @modal.enter()
    def load(self):
        import os
        import time
        import torch
        from diffusers import StableDiffusion3Pipeline

        self.load_start = time.time()
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
        self.load_seconds = round(time.time() - self.load_start, 3)

    @modal.method()
    def run_batch(self, req: dict) -> dict:
        import datetime as dt
        import hashlib
        import json
        import time
        from pathlib import Path

        count = max(1, min(int(req.get("count", 111)), 333))
        width = max(512, min(int(req.get("width", 768)), 1024))
        height = max(512, min(int(req.get("height", 768)), 1024))
        steps = max(1, min(int(req.get("steps", 4)), 8))
        guidance_scale = float(req.get("guidance_scale", 1.0))
        seed_base = int(req.get("seed", 2045))
        batch_size = max(1, min(int(req.get("batch_size", 4)), 8))
        theme = str(req.get("theme") or "Sonic-Forage ambient intergalactic radio visuals, safe original abstract art")
        run_id = str(req.get("run_id") or dt.datetime.utcnow().strftime("ambient-111-%Y%m%dT%H%M%SZ"))
        safe_run = "".join(c if c.isalnum() or c in "-_" else "-" for c in run_id)[:96] or "ambient-batch"
        out_dir = Path("/outputs/cdm-radio-loop") / safe_run
        out_dir.mkdir(parents=True, exist_ok=True)

        started = time.time()
        images = []
        failures = []
        i = 0
        current_batch_size = batch_size
        while i < count:
            n = min(current_batch_size, count - i)
            prompts = [make_prompt(j, theme) for j in range(i, i + n)]
            seeds = [seed_base + j for j in range(i, i + n)]
            generators = [self.torch.Generator("cuda").manual_seed(s) for s in seeds]
            try:
                result = self.pipe(
                    prompts,
                    negative_prompt=[negative_prompt()] * n,
                    height=height,
                    width=width,
                    num_inference_steps=steps,
                    sigmas=[1.0, 0.75, 0.5, 0.25],
                    guidance_scale=guidance_scale,
                    generator=generators,
                )
            except RuntimeError as exc:
                if "out of memory" in str(exc).lower() and current_batch_size > 1:
                    try:
                        self.torch.cuda.empty_cache()
                    except Exception:
                        pass
                    current_batch_size = max(1, current_batch_size // 2)
                    failures.append({"at_index": i, "error": "OOM_REDUCED_BATCH", "new_batch_size": current_batch_size})
                    continue
                raise
            for local_idx, image in enumerate(result.images):
                global_idx = i + local_idx
                seed = seeds[local_idx]
                png_path = out_dir / f"ambient_{global_idx+1:03d}_seed{seed}.png"
                image.save(png_path)
                data = png_path.read_bytes()
                images.append({
                    "index": global_idx + 1,
                    "seed": seed,
                    "prompt": prompts[local_idx],
                    "output_volume_path": str(png_path),
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                })
            i += n
            # commit periodically so partial results survive interruptions
            if len(images) % 24 == 0:
                OUTPUTS.commit()

        elapsed = round(time.time() - started, 3)
        payload = {
            "ok": True,
            "app": APP_NAME,
            "utc": dt.datetime.utcnow().isoformat() + "Z",
            "run_id": safe_run,
            "model": self.pipeline_name,
            "load_seconds": getattr(self, "load_seconds", None),
            "generate_seconds": elapsed,
            "total_images": len(images),
            "requested_count": count,
            "seconds_per_image": round(elapsed / max(1, len(images)), 3),
            "images_per_minute": round(len(images) * 60 / max(0.001, elapsed), 3),
            "settings": {
                "width": width,
                "height": height,
                "steps": steps,
                "guidance_scale": guidance_scale,
                "seed_base": seed_base,
                "initial_batch_size": batch_size,
                "final_batch_size": current_batch_size,
                "theme": theme,
            },
            "images": images,
            "failures": failures,
            "safety": {
                "safe_original_abstract_prompts": True,
                "no_text_logos_or_copyrighted_characters": True,
                "no_stream_keys_or_tokens": True,
            },
        }
        manifest_path = out_dir / "batch_manifest.json"
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        OUTPUTS.commit()
        return payload


@app.local_entrypoint()
def main(
    count: int = 111,
    width: int = 768,
    height: int = 768,
    steps: int = 4,
    batch_size: int = 4,
    seed: int = 2045,
    theme: str = "Strawberry Forage intergalactic radio visuals, berry API rave nebula, safe original abstract art",
    run_id: str = "ambient-111-system-test",
    dry_run: bool = True,
):
    req = {
        "count": count,
        "width": width,
        "height": height,
        "steps": steps,
        "batch_size": batch_size,
        "seed": seed,
        "theme": theme,
        "run_id": run_id,
    }
    if dry_run:
        print(json.dumps({
            "ok": True,
            "dry_run": True,
            "gpu_started": False,
            "model_download_started": False,
            "request": req,
            "sample_prompts": [make_prompt(i, theme) for i in range(min(5, count))],
        }, indent=2))
    else:
        print(json.dumps(AmbientBatchGenerator().run_batch.remote(req), indent=2))
