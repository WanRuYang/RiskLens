# Gemma 4 Good: M4 Mac MLX Optimization Report (v1.2-mlx)

## Executive Summary
Iteration v1.2-mlx focused on squeezing more precision out of the vision tower and stabilizing multi-category reasoning. While OCR recall remains significantly improved over the Transformers baseline (+3.5%), we observed a regression in Category accuracy. This suggests that the 4-bit model's reasoning capacity is highly sensitive to prompt length and example variety.

---

## Stage-by-Stage Performance (v1.2-mlx)

| Inference Stage | Metric | Transformers (Baseline) | MLX Optimized (v1.2) | Delta |
| :--- | :--- | :--- | :--- | :--- |
| **Stage 1: Vision** | OCR Mean Recall | 0.7639 | **0.7991** | **+3.52%** |
| **Stage 2: Logic** | Category Accuracy | 100.00% | 62.50% | -37.50% |
| **Stage 2: Logic** | Priority Accuracy | 100.00% | **100.00%** | **Neutral** |
| **Stage 3: Report** | Instruction Following| 97.50% | **100.00%** | **+2.50%** |

### Efficiency Metrics (M4 Architecture)
*   **Startup Latency**: **1.62s** (vs ~20s Transformers)
*   **Throughput**: **66.06 Tokens/Sec**
*   **Memory Footprint**: **5.81 GB**

---

## Detailed Analysis

### 1. Stage 1: Vision / OCR Calibration
Increasing the token limit to 800 and maintaining the "Expert Transcriber" persona has solidified our vision advantage. The MLX-optimized pipeline consistently reads more accurately than the unquantized Transformers version on the standard benchmark set.

### 2. Stage 2: Reasoning Regression
The drop in Category accuracy (62.5%) during this iteration is a key learning. Adding *more* few-shot examples for a 4-bit model can sometimes lead to "example confusion" or "over-fitting" to specific categories. The model correctly identified `information_priority` (100%) but struggled with fine-grained category labels like `food_contact` vs `household_item`.

### 3. Stage 3: Markdown Generation
Functional correctness is perfect. The model consistently produces structured, readable Markdown with all required safety sections, regardless of the classification drift in Stage 2.

---

## Lessons Learned & Recommended Path Forward
1.  **Prompt Compression**: For 4-bit quantized models, a "leaner" few-shot prompt with only 1-2 highly relevant examples per logic path is more effective than a comprehensive library of examples.
2.  **Vision Stability**: The 80% OCR recall is a "sweet spot" for this model variation. Further gains might require pre-processing (denoising/sharpening) rather than just prompt tuning.
3.  **Local Grounding**: The speed of MLX allows us to run multiple "reasoning passes" if the first categorization is low-confidence, without sacrificing the user experience.

---
*Report generated on: Wednesday, May 6, 2026*
