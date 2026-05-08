# CDM Realtime Radio Endpoint Deploy Receipt — 2026-05-08

## Result

- Modal app: `jimsky-cdm-realtime-radio`
- Deployment URL: `https://m1ndb0t-2045--jimsky-cdm-realtime-radio-api.modal.run`
- Modal deployment page: `https://modal.com/apps/m1ndb0t-2045/main/deployed/jimsky-cdm-realtime-radio`
- Deployed at: `2026-05-08T15:36:35Z`
- Verification timestamp: `2026-05-08T15:39:34Z`

## Verified CPU routes

- `GET /health` returned HTTP 200 with `ok=true` and `gpu_started=false`.
- `POST /v1/dry-run` returned HTTP 200 with normalized CDM request JSON and `gpu_started=false`.
- `POST /v1/generate` without `allow_gpu=true` returned HTTP 400 with the expected default-deny message.

## Scale-to-zero check

After the CPU web `scaledown_window` elapsed, Modal app list showed the deployed app at:

```text
Description: jimsky-cdm-realtime-radio
State: deployed
Tasks: 0
```

## Safety posture

- No real CDM image generation was run in this deployment receipt.
- No GPU inference was started by the verification requests.
- No Stable Diffusion / CDM weights were downloaded by this receipt.
- LongCat-Next remains a director/control scaffold only; no 74B model download or GPU run occurred.
- `/v1/generate` remains gated and must be intentionally called with `allow_gpu=true` before any cost-bearing generation.

## Next approval gate

If a real proof image is desired, run one explicit CDM GPU smoke test with:

- one safe Sonic-Forage prompt,
- `steps=4`,
- bounded size such as `1024x1024`,
- output to the Modal `outputs` volume,
- post-run `Tasks: 0` verification.

Do not flip cron/timer jobs from dry-run to real generation until that smoke test is approved and reviewed.
