# Jimsky / Sonic-Forage Modal CDM Realtime Radio Setup

This fork wraps [`byliutao/CDM`](https://github.com/byliutao/CDM) for Sonic-Forage realtime-radio visuals.

## What CDM is good for here

CDM is **not an audio model**. It is a few-step image diffusion/distillation implementation. For the radio loop, use it to generate:

- album-cover candidates,
- stream background/key art,
- episode cards,
- live visual refresh frames,
- prompt-to-image assets that can be placed into the Program Deck / HyperFrames loop.

The upstream examples use 4 NFE / 4 inference steps, which is the right shape for fast visual refreshes once the Modal GPU container is warm.

## Current Modal lane

As of `2026-05-08T15:39:34Z`, the previously blocked Modal web endpoint lane has been deployed after endpoint slots were freed.

- CPU readiness: `modal/cdm_radio_jobs.py`
- no-web real generation job: `modal/cdm_generate_job.py`
- deployed CPU web shell + gated GPU route: `modal/cdm_realtime_app.py`
- live CPU API URL: `https://m1ndb0t-2045--jimsky-cdm-realtime-radio-api.modal.run`

The no-web job remains the safest cron/default path. The web API is now available for `/health` and `/v1/dry-run`; `/v1/generate` is still gated and rejects requests unless `allow_gpu=true` is intentionally supplied.

## Realtime expectations

- Cold start = Modal image start + model load/cache; not instant.
- Warm container = target path for fast 4-step visual generation.
- Dry-run/timer planning is CPU-only.
- Real generation requires the explicit `--no-dry-run` Modal flag or `scripts/sonic_cdm_radio_timer.py --generate`.
- Outputs are written to the Modal `outputs` volume under `/outputs/cdm-radio-loop/...` with JSON manifests.

## Files added

- `modal/cdm_realtime_app.py` — FastAPI Modal app with `/health`, `/v1/dry-run`, and gated `/v1/generate` for later, once a Modal web endpoint slot is free.
- `modal/cdm_generate_job.py` — active no-web A10G generation job for timer/radio-loop use.
- `modal/cdm_radio_jobs.py` — CPU-only readiness; no Torch/GPU image in this file.
- `modal/cdm_gpu_probe.py` — optional tiny T4 GPU dependency probe, isolated so readiness stays cheap.
- `scripts/sonic_cdm_radio_timer.py` — Hermes cron-safe timer runner; dry-run by default.
- `docs/JIMSKY_MODAL_CDM_SETUP.md` — this setup note.

## Commands

From Hermes:

```bash
cd /opt/data/hermes-agent
source venv/bin/activate
set -a; source /opt/data/.env; set +a
cd /opt/data/workspace/projects/cdm-modal-radio-loop

# CPU-only readiness; no model download, no GPU.
modal run modal/cdm_radio_jobs.py --mode readiness

# Dry-run a no-web generation request; no GPU.
modal run modal/cdm_generate_job.py --prompt "Sonic-Forage neon album card" --dry-run

# Optional tiny GPU dependency probe; no model download. Kept in a separate app
# so CPU readiness does not build Torch/CUDA images.
modal run modal/cdm_gpu_probe.py --mode gpu-probe
```

Real generation is intentionally explicit:

```bash
modal run modal/cdm_generate_job.py \
  --prompt "Sonic-Forage intergalactic radio album cover, neon strawberry API avatar, no text" \
  --loop-id "hour4-goa" \
  --seed 2045 \
  --steps 4 \
  --width 1024 \
  --height 1024 \
  --no-dry-run
```

Optional web API deployment once a Modal endpoint slot is free:

```bash
modal deploy modal/cdm_realtime_app.py
```

## Timer pattern

Hermes cron can call:

```bash
python3 /opt/data/workspace/projects/cdm-modal-radio-loop/scripts/sonic_cdm_radio_timer.py
```

That records a dry-run plan every tick. Use `--generate` only after approving GPU/model-cache cost:

```bash
python3 /opt/data/workspace/projects/cdm-modal-radio-loop/scripts/sonic_cdm_radio_timer.py --generate
```

## Radio integration path

1. Use dry-run timer to rotate prompt plans every 15 minutes.
2. Use `scripts/longcat_next_control_bridge.py` as the safe LongCat-Next-style director/controller: context/audio/image notes become strict `cdm_request` JSON without starting a 74B model.
3. Later, wire `LONGCAT_NEXT_ENDPOINT` to a real LongCat-Next multimodal service for image/audio understanding and edit intent.
4. Approve one CDM GPU warmup/generation smoke test.
5. Pull generated PNGs from Modal `outputs` volume.
6. Add generated frames to the Program Deck / HyperFrames asset playlist.
7. If stable, schedule `--generate` ticks at a conservative cadence such as every 15 or 30 minutes.

See `docs/LONGCAT_NEXT_REALTIME_EDIT_ARCHITECTURE.md` for the LongCat-Next understanding/edit-control plan.

## Safety and cost gates

- No chat-to-shell.
- No copyrighted character prompts.
- No public posting/DMs.
- No uncontrolled recurring GPU jobs.
- No HF/model token values in logs or manifests.
- Real generation requires `--no-dry-run` / `--generate`.
