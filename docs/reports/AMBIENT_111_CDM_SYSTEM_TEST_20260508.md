# Ambient 111 CDM System Test — 2026-05-08

## Result

A real Modal GPU system test generated ambient shuffle visuals for the Sonic-Forage/Jimsky radio loop.

- Batch app: `jimsky-cdm-ambient-batch`
- Model: `byliutao/stable-diffusion-3-medium-turbo`
- GPU: Modal `A10G`
- Output resolution: `768x768`
- Steps: `4`
- Batch size: `4`
- Final curated frame count: `111`
- Live review page: `https://themindexpansionnetwork.github.io/sonic-forage-night-shift-review-hub/ambient-111-system-test.html`
- Pages commit: `1abe8998f874408846a80c2aeabf811e973da917`

## Timing

### First benchmark batch

- Requested images: `111`
- Generated images: `111`
- Load seconds: `105.736`
- Generation seconds: `113.238`
- Seconds/image during generation: `1.020`
- Images/minute during generation: `58.814`
- Cost row observed: `$0.08215519`

QA caught that using the literal phrase `Sonic-Forage` caused some Sonic-like/IP-contaminated images. This was useful system feedback, so the harness was patched.

### Clean batch

- Requested images: `111`
- Generated images: `111`
- Load seconds: `152.494`
- Generation seconds: `123.651`
- Seconds/image during generation: `1.114`
- Images/minute during generation: `53.861`
- Cost row observed: `$0.10094421`

Prompt fixes:

- Avoided literal `Sonic` phrasing in visual prompts.
- Kept positive prompts shorter so safety/style terms survive tokenizer limits.
- Added a negative prompt for text, logos, copyrighted mascots, Sonic/Shadow-like characters, cartoon gloves/shoes, human faces, mouth pipes, straws, smoking artifacts, and weapons.

### Replacement mini-batch

A 16-image replacement batch was generated so the final curated 111-pack could replace text/logo artifacts detected in the clean batch.

## Curated pack

Local curated directory:

```text
/opt/data/workspace/projects/cdm-modal-radio-loop/outputs/ambient-111-curated-system-test
```

Key local artifacts:

```text
contact_sheet_111_curated_v2.jpg
ambient_111_curated_v2_shuffle_preview.mp4
CURATED_SYSTEM_TEST_SUMMARY.json
curated_001.png ... curated_111.png
```

Published lightweight review artifacts:

```text
https://themindexpansionnetwork.github.io/sonic-forage-night-shift-review-hub/ambient-111-system-test.html
https://themindexpansionnetwork.github.io/sonic-forage-night-shift-review-hub/data/ambient_111_curated_manifest.json
```

The Pages version uses optimized JPGs, thumbnails, a contact sheet, and a 9.25s/12fps MP4 shuffle preview. Raw PNGs remain local and were not committed to the Pages repo.

## QA

Vision QA on the final v2 contact sheet found:

- No meaningful artwork text.
- No obvious logos or brand marks.
- No recognizable copyrighted characters.
- No mouth-pipe/straw/smoking artifacts.
- Contact-sheet index labels are preview-only.

## Modal hygiene

After the run and idle window, relevant Modal apps were checked:

- `jimsky-cdm-radio-generate-job`: deployed, `Tasks: 0`
- `jimsky-cdm-realtime-radio`: deployed, `Tasks: 0`
- `jimsky-cdm-ambient-batch`: stopped, `Tasks: 0`
- `jimsky-cdm-radio-jobs`: stopped, `Tasks: 0`

## Notes

The system successfully generated more than 50 usable 768x768 ambient visuals per minute once the GPU container was loaded. For future stream use, prefer prompts that avoid project names which collide with known IP terms. Use the live CDM realtime endpoint for controlled single-image requests and this batch harness for high-throughput overnight visual packs.
