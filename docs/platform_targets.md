# Platform Targets

## Goal

The product should be designed so that:

- it runs today as a macOS development and benchmark harness
- it can ship later as a Pixel 8 Android app without changing the core safety contract

## Target 1: macOS development harness

Current mac target:

- Python 3.12
- Gradio UI
- local FastAPI + Postgres
- fixed-size Gemma 4 product path
- OpenAI only for evaluation and judging

This target is for:

- OCR iteration
- benchmark runs
- grounded retrieval tuning
- agentic UX design

## Target 2: Pixel 8 product target

The Pixel 8 target should keep the same app contract, but replace the desktop shell with a native Android client.

The important rule is that the system core must stay portable:

- same normalized payload shape
- same category and material reasoning contract
- same review-queue concept
- same grounded source framing

The product should not depend on:

- Gradio
- desktop file paths
- Python-only UI behavior
- OpenAI as a runtime requirement

## Why Pixel 8 is a reasonable target

Google's official Android LLM Inference guide describes on-device LLM inference for high-end Android devices such as Pixel 8, and the official docs note that the API is optimized for devices in that class. The product should therefore be designed around:

- compact prompts
- bounded image count
- bounded retrieval payloads
- a strict structured Stage 2 contract

Relevant official references:

- [LLM Inference guide for Android](https://ai.google.dev/edge/mediapipe/solutions/genai/llm_inference/android)
- [LiteRT for Android](https://ai.google.dev/edge/litert/android)
- [Deploy GenAI Models with LiteRT](https://ai.google.dev/edge/litert/genai/overview)
- [LiteRT-LM](https://github.com/google-ai-edge/LiteRT-LM)

## Design constraints for cross-platform portability

1. Keep image intake capped at 3 images.
2. Keep direct text input as a first-class path.
3. Keep product links optional and non-authoritative.
4. Treat the normalized payload as the portability boundary.
5. Keep retrieval JSON compact and typed.
6. Keep agentic interaction as a UI layer, not as backend branching.
7. Keep review-queue capture independent from the UI shell.

## Engineering implication

The current Python app is the macOS harness, not the final Android app shell.

That is acceptable because the portable part of the system is now:

- `vnext_contract.py`
- `app_shared.py`
- the local API contract
- the benchmarked Stage 1 and Stage 2 logic

These are the parts that should be carried forward into the Pixel 8 implementation.
