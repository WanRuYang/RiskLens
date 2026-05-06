# Demo Plan

## Goal

Show that `gemma4good` is not just an image-to-chat demo. The strongest story is:

1. a fixed local Gemma 4 model reads labels or user-entered text,
2. a small, explicit category and material taxonomy stabilizes reasoning,
3. a local risk database adds grounded regulatory and literature context,
4. the app produces a cautious consumer answer with source and region context.

This framing highlights both product usefulness and engineering depth.

## What To Demo

### 1. Input Flexibility

Show both supported entry paths:

- image input
  - front label
  - ingredients panel
  - warning panel
- direct text input
  - product name
  - ingredient or material clue
  - warning text

The key point is that both paths converge to the same normalized Stage 2 payload.

### 2. Two-Stage Reasoning

Explain the pipeline clearly:

1. Stage 1
   - image reading and text extraction
2. Stage 2
   - category identification
   - material or form identification
   - ingredient-first vs material-first priority
   - grounded risk response

This is a good engineering showcase because it separates OCR quality from safety reasoning quality.

### 3. Why The Local DB Matters

Use one or two cases where raw model reasoning sounds plausible but misses nuance:

- legal additive with region differences
- Prop 65 warning that is not the same as a ban
- household cleaner where handling caution matters more than a listed ingredient match

Then show the grounded version using the same Gemma 4 model size.

The core message:

- improvements come from system design, retrieval, and constrained reasoning
- not from swapping to a larger model

### 4. User History / Repeated Exposure

Show that the app can store prior analyzed products and point out repeated overlaps:

- same chemical across multiple products
- same concern family across multiple categories
- repeated contact routes such as ingestion, inhalation, or child-use items

This helps the app feel like a real safety assistant instead of a one-off scanner.

## Best Demo Order

### Option A: Live Product Story

1. Show a cleaner spray image set.
2. Show OCR output.
3. Show grounded API result.
4. Show final answer with handling caution.
5. Show saved history and repeated chemical overlaps.

### Option B: Benchmark Story

1. Show Stage 1 OCR benchmark.
2. Show Stage 2 raw benchmark.
3. Show Stage 2 grounded benchmark.
4. Show before/after improvement with the same Gemma 4 model.

This is stronger for technically minded judges.

## What To Emphasize In The Talk Track

- California consumers see Prop 65 warnings everywhere, but the warnings are hard to interpret.
- The app does not reduce everything to safe or unsafe.
- The app separates:
  - warning
  - restriction
  - ban
  - allowed with conditions
  - literature-based controversy
- The app keeps the final local Gemma model size fixed for mobile relevance.
- Better performance comes from:
  - explicit category/material references
  - grounded retrieval
  - benchmarked pipeline design

## Engineering Highlights

If you want to showcase engineering skill, focus on:

- shared normalized payload across image and text input
- separate Stage 1 and Stage 2 benchmarks
- dataset-derived category reference instead of free-form taxonomy
- local PostgreSQL-backed API for grounded retrieval
- separate raw, normalized, and serving layers in the data design
- preservation of benchmark artifacts and before/after comparisons

## Nice Side-By-Side Comparisons

- raw Gemma Stage 2 vs grounded Gemma Stage 2
- Gemma grounded app vs OpenAI grounded app
- image input vs direct text input through the same Stage 2 path

These comparisons make the system design visible, which is often more impressive than just showing a fluent final answer.
