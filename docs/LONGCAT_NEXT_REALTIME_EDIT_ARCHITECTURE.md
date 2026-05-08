# LongCat-Next + CDM Realtime Edit/Understanding Architecture

User goal: **realtime radio loop visuals that can understand context, react, and edit.**

## Model roles

- **LongCat-Next (`meituan-longcat/LongCat-Next`)**
  - Native multimodal foundation model: text, image, audio, image generation, speech/audio generation.
  - Best role for Sonic-Forage: the *director/editor/understanding brain*.
  - It can inspect a current visual frame, audio segment, chat/context note, or operator prompt and produce a structured edit/control plan.
  - It is large: Hugging Face card reports 74B-class model; upstream inference requires CUDA >= 12.9 and a local model path.

- **CDM / `byliutao/stable-diffusion-3-medium-turbo`**
  - Fast few-step image generation.
  - Best role: produce visual frames, album covers, stream background/key art, and review images from LongCat-Next’s control prompts.

## Why this split

Trying to make LongCat-Next the always-on realtime generator immediately would be expensive and fragile. The more reliable live-stack is:

```text
radio context / current image / audio note / chat spark
        ↓
LongCat-Next director understanding/edit plan
        ↓ strict JSON control object
CDM 4-step visual generator on Modal
        ↓ PNG + manifest in outputs volume
Program Deck / HyperFrames radio loop picks up generated visual
```

This gives the “sooooo sick realtime editing/understanding” feel while keeping heavy 74B inference approval-gated.

## Files added in this fork

- `modal/longcat_next_readiness.py`
  - CPU-only Modal readiness check for `meituan-longcat/LongCat-Next`.
  - Checks model metadata only.
  - Does **not** download weights and does **not** start GPU.

- `scripts/longcat_next_control_bridge.py`
  - Safe controller bridge.
  - Today: local deterministic director fallback emits strict JSON control plans.
  - Later: if `LONGCAT_NEXT_ENDPOINT` is set, routes to a real LongCat-Next director endpoint at `/v1/director`.
  - Writes `cdm_request` objects compatible with the CDM radio visual generator.

## Commands

```bash
cd /opt/data/hermes-agent
source venv/bin/activate
set -a; source /opt/data/.env; set +a
cd /opt/data/workspace/projects/cdm-modal-radio-loop

# CPU-only LongCat-Next readiness; no model download, no GPU.
modal run modal/longcat_next_readiness.py

# Local control-plan dry run; no model/GPU.
python3 scripts/longcat_next_control_bridge.py \
  --context "Hour 4 Goa sunrise afterglow, live radio wants a new visual edit" \
  --mode radio_visual_edit
```

## Example control output

The bridge emits:

```json
{
  "ok": true,
  "source": "local_safe_director_fallback",
  "cdm_request": {
    "prompt": "Sonic-Forage neon cyberpunk...",
    "loop_id": "radio_visual_edit-dawn-Goa-psytrance",
    "seed_hint": 12345,
    "width": 1024,
    "height": 1024,
    "steps": 4,
    "guidance_scale": 1.0
  },
  "program_deck_action": {
    "type": "queue_visual_prompt",
    "allowed_to_execute": false,
    "chat_to_shell": false,
    "requires_human_or_cron_gate": true
  }
}
```

## Future real LongCat-Next endpoint contract

When GPU/quantization is approved, deploy a separate LongCat-Next service exposing:

```http
POST /v1/director
Content-Type: application/json
Authorization: Bearer <LONGCAT_NEXT_API_TOKEN>

{
  "context": "radio/chat/operator/current show state",
  "mode": "radio_visual_edit | image_understanding | audio_understanding | prompt_rewrite",
  "image": "optional URL/base64/path handled by endpoint",
  "audio": "optional URL/base64/path handled by endpoint"
}
```

Response must be strict JSON with:

- `understanding.context_summary`
- `understanding.image_note` and/or `audio_note`
- `cdm_request.prompt`
- `cdm_request.loop_id`
- `cdm_request.seed_hint`
- `program_deck_action.allowed_to_execute=false`
- `safety.no_direct_shell=true`

## Safety gates

- No uncontrolled 74B GPU/model download.
- No public posting/DMs.
- No direct shell from chat/context.
- No copyrighted character prompts.
- No tokens/stream keys in prompts, logs, or manifests.
- Treat real LongCat-Next inference as a separate cost-bearing deployment that needs explicit approval.

## Modal notes discovered

- `LongCat-Next-inference` upstream supports `img_gen`, `img_und`, `aud_2_txt`, `spk_syn`, and `aud_2_aud`.
- Upstream inference repo README says CUDA >= 12.9 and uses `demo.py --model-path ${MODEL_PATH}`.
- The demo uses a FluentLLM backend, shared-memory style processing, and task special tokens such as `<longcat_img_start>` and `<longcat_audiogen_start>`.
- This fork intentionally avoids installing/running that full stack until a GPU target and budget are chosen.
