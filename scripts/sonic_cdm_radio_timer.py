#!/usr/bin/env python3
"""Sonic-Forage CDM radio-loop timer launcher.

This script is safe to run from Hermes cron. By default it performs a dry-run prompt
plan and does NOT start a GPU. Use --generate to call the Modal GPU entrypoint.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = Path("/opt/data/drops/sonic-forage-cdm-radio-loop")
PROMPTS = [
    "Sonic-Forage intergalactic radio album cover, neon strawberry API avatar, cyberpunk rave booth, safe original art, no text",
    "Astra Kandi Saffron dawn Goa psytrance mandala, sunrise afterglow, kandi beads, fractal flowers, safe original art, no text",
    "Jimsky autonomous radio command center, HyperFrames neon panels, PLUR festival lights, strawberry signal tower, no text",
    "Freedoom legal game radio takeover visual, retro cyber arcade, rave lasers, friendly AI operator, no copyrighted characters, no text",
]


def run(cmd: list[str], timeout: int = 1200) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    return subprocess.run(cmd, cwd=str(ROOT), env=env, text=True, capture_output=True, timeout=timeout)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--generate", action="store_true", help="Actually start Modal GPU generation. Default is dry-run only.")
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--loop-id", default="sonic-radio-loop")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    minute_slot = int(dt.datetime.utcnow().timestamp() // 900)
    prompt = args.prompt or PROMPTS[minute_slot % len(PROMPTS)]
    seed = args.seed if args.seed is not None else 2045 + (minute_slot % 100000)
    cmd = [
        "/opt/data/hermes-agent/venv/bin/modal",
        "run",
        "modal/cdm_generate_job.py",
        "--prompt", prompt,
    ]
    if not args.generate:
        cmd += ["--dry-run"]
    else:
        cmd += ["--no-dry-run"]

    # Modal local_entrypoint currently accepts prompt/dry_run. Full endpoint calls can pass
    # seed/loop-id via HTTP once deployed; this cron wrapper still records the intended slot.
    result = run(cmd, timeout=1800 if args.generate else 300)
    payload = {
        "utc": dt.datetime.utcnow().isoformat() + "Z",
        "generate": bool(args.generate),
        "loop_id": args.loop_id,
        "prompt": prompt,
        "seed": seed,
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-2000:],
        "safety": "dry-run by default; --generate is the explicit GPU gate",
    }
    out = STATE_DIR / f"timer_{dt.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
