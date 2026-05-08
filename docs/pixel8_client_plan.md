# Pixel 8 Client Shell Plan

## Goal

Build a native Android shell for Pixel 8 that reuses the same core safety contract already used by the macOS harness and the benchmark pipeline.

## What stays the same

- `NormalizedProductPayload`
- Stage 2 category and material contract
- local API request and response shape
- review-queue semantics
- distinction between production Gemma path and OpenAI evaluation path

## What changes on Android

- the UI shell becomes native Android
- image intake uses Android photo capture / picker flows
- text input becomes a first-class fallback path
- the agentic states are rendered as mobile cards or steps instead of desktop chat-only affordances

## Suggested shell architecture

1. image or text intake screen
2. OCR review screen
3. category/material confirmation screen
4. grounded result screen
5. optional save-to-history and review-queue actions

## Contract boundaries

The Android shell should call into the same logical layers:

1. extraction
2. normalized payload assembly
3. Stage 2 interpretation
4. grounded retrieval
5. final answer rendering

## Engineering milestones

1. freeze the shared payload and retrieval contract
2. keep Stage 2 benchmark using that same contract
3. define Android-side JSON models to mirror `vnext_contract.py`
4. implement a lightweight Android shell around those models
5. run the same gold Stage 2 benchmark payloads through the Android path

## Immediate next step

The most important prerequisite is already underway: make the benchmark pipeline and the macOS app use the exact same normalized payload shape.
