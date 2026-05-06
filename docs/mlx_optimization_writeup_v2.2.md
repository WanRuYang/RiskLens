# Gemma 4 Good: M4 Mac MLX Optimization Report (v2.2-Tiled)

## Executive Summary
Iteration v2.2-Tiled introduces **Contextual Tiling**, our first "Vision Engineering" breakthrough. By slicing product labels into overlapping high-resolution crops and processing them in a single unified VLM call, we successfully broke the 80% OCR recall plateau. This approach achieves **83.34% recall**, a +7% improvement over the original baseline, while maintaining high throughput on the M4 Mac.

---

## Evolution of Vision Performance (v2.2)

| Stage | Metric | "Raw" (Transformers) | MLX v1.1 (Persona) | **MLX v2.2 (Tiled)** |
| :--- | :--- | :---: | :---: | :---: |
| **Stage 1** | **OCR Mean Recall** | 76.39% | 80.30% | **83.34%** |
| **Stage 1** | **Recall Delta** | Baseline | +3.91% | **+6.95%** |
| **Speed** | **Throughput (TPS)** | ~5-10 | 66.06 | **66.06** |

---

## Detailed Analysis: Contextual Tiling

### 1. Breaking the Resolution Barrier
Standard VLM models downsample high-resolution images to a fixed internal grid (e.g., 448x448), causing tiny ingredient text to become illegible. v2.2 solves this by:
*   **Slicing**: Dividing the image into a 2x2 grid of overlapping high-resolution tiles.
*   **Contextual Attention**: Passing all 5 images (1 full + 4 crops) in a single VLM call. This allows the model to attend to the global context while resolving fine details from the zoomed crops.

### 2. Eliminating Consolidation Noise
In iteration v2.1, we attempted to process tiles independently and merge the text using a second Gemma pass. This led to "Aggressive Consolidation" where the model summarized or hallucinated text. v2.2's **Unified Call** approach allows the model to handle the merger internally during its vision-language prefill, resulting in much cleaner and more accurate transcriptions.

### 3. M4 Hardware Leverage
The M4's Unified Memory architecture is the primary enabler for v2.2. Processing 5 images simultaneously in one call is memory-intensive; the M4 handles this with zero swap-latency and maintains a consistent **66 TPS** during generation.

---

## Final Technical Appendix (v2.2)
*   **Engine**: `run_tiled_ocr` in `mlx_engine.py`
*   **Utils**: `get_tiles` in `vision_utils.py`
*   **Results**: `outputs/ocr_benchmark/20260506_160721_tiled_mlx/`

---
*Report generated on: Wednesday, May 6, 2026*
