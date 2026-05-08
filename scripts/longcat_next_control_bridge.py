#!/usr/bin/env python3
"""LongCat-Next control bridge for Sonic-Forage realtime radio visuals.

This is the safe local/controller layer. It does not download LongCat-Next and it
does not start GPU inference by itself. It turns radio context + optional
understanding notes into a strict JSON edit-control object that CDM/Program Deck
can consume. Later, set LONGCAT_NEXT_ENDPOINT to a deployed LongCat service and
replace the heuristic planner with real multimodal calls.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import urllib.request
from pathlib import Path

DEFAULT_STYLE = "Sonic-Forage neon cyberpunk PLUR radio, strawberry API avatar, HyperFrames glow, safe original art"
FORBIDDEN = ["copyrighted character", "nintendo", "pokemon", "mario", "trademarked logo", "stream key", "password", "token"]


def safe_slug(text: str, limit: int = 80) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", text).strip("-")[:limit] or "longcat-control"


def local_director(context: str, mode: str, image_note: str = "", audio_note: str = "") -> dict:
    ctx = " ".join((context or "").split())[:1600]
    mood = "dawn Goa psytrance" if re.search(r"goa|sunrise|dawn|psy", ctx, re.I) else "intergalactic radio rave"
    if re.search(r"game|doom|freedoom|arcade", ctx, re.I):
        mood = "legal open-source arcade takeover"
    if re.search(r"sponsor|collab|deck|outreach", ctx, re.I):
        mood = "collab sponsor proof hub"
    prompt = f"{DEFAULT_STYLE}, {mood}, {ctx or 'live autonomous radio loop'}, no text, no logos, no copyrighted characters"
    negative = ", ".join(FORBIDDEN + ["blurry", "low quality", "mouth pipe", "straw near mouth"])
    if image_note:
        prompt += f", visually respond to: {image_note[:400]}"
    if audio_note:
        prompt += f", audio-reactive feel: {audio_note[:400]}"
    return {
        "ok": True,
        "source": "local_safe_director_fallback",
        "utc": dt.datetime.utcnow().isoformat() + "Z",
        "mode": mode,
        "understanding": {
            "context_summary": ctx or "No context supplied; use default Sonic-Forage radio identity.",
            "image_note": image_note,
            "audio_note": audio_note,
            "intended_longcat_next_role": "Use LongCat-Next for image/audio understanding and edit intent once a gated endpoint is deployed.",
        },
        "cdm_request": {
            "prompt": prompt[:1200],
            "negative_prompt": negative,
            "loop_id": safe_slug(mode + "-" + mood),
            "seed_hint": 2045 + (sum(map(ord, prompt)) % 100000),
            "width": 1024,
            "height": 1024,
            "steps": 4,
            "guidance_scale": 1.0,
            "model": "byliutao/stable-diffusion-3-medium-turbo",
        },
        "program_deck_action": {
            "type": "queue_visual_prompt",
            "allowed_to_execute": False,
            "chat_to_shell": False,
            "requires_human_or_cron_gate": True,
        },
        "safety": {
            "no_direct_shell": True,
            "no_auto_public_post": True,
            "no_unapproved_gpu_74b": True,
            "forbidden_terms_checked": FORBIDDEN,
        },
    }


def endpoint_director(endpoint: str, payload: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(
        endpoint.rstrip("/") + "/v1/director",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + os.getenv("LONGCAT_NEXT_API_TOKEN", "")},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--context", default="")
    ap.add_argument("--context-file", default="")
    ap.add_argument("--mode", default="radio_visual_edit")
    ap.add_argument("--image-note", default="")
    ap.add_argument("--audio-note", default="")
    ap.add_argument("--out", default="/opt/data/drops/sonic-forage-cdm-radio-loop/longcat_next_control_latest.json")
    args = ap.parse_args()
    context = args.context
    if args.context_file:
        context += "\n" + Path(args.context_file).read_text(errors="ignore")[:6000]
    payload = {"context": context, "mode": args.mode, "image_note": args.image_note, "audio_note": args.audio_note}
    endpoint = os.getenv("LONGCAT_NEXT_ENDPOINT", "").strip()
    try:
        result = endpoint_director(endpoint, payload) if endpoint else local_director(context, args.mode, args.image_note, args.audio_note)
    except Exception as exc:
        result = local_director(context + f"\nEndpoint fallback reason: {type(exc).__name__}", args.mode, args.image_note, args.audio_note)
        result["endpoint_error"] = type(exc).__name__
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
