# Android MVP Client

This folder is a minimal Android client shell for the future Pixel 8 product path. It now follows the same single-composer intake model as the macOS product app: the user types product text, pastes a URL, or adds image evidence, and the app decides how to process that turn behind the scenes.

It is intentionally scoped to:

- one single-composer intake surface that auto-detects whether the turn is image-driven, URL-driven, or text-driven
- region selection
- real camera capture and photo-gallery selection
- Android ML Kit Text Recognition for attached-image OCR
- Gemma 4 identification after OCR normalization
- automatic URL preview before analysis
- the same "ask for ingredients / Nutrition Facts when missing" behavior used by the web app
- calling the current `/analyze-product` API
- showing grounded results in stacked mobile cards aligned with the web result order

It does **not** include:

- benchmark tooling
- OpenAI evaluation flows
- report-generation logic

## Source layout

- `app/src/main/java/good/gemma4good/android/`
  - `MainActivity.kt`
  - `AppConfig.kt`
  - `data/network/`
  - `data/repository/`
  - `ui/`
- `../../android_contract/`
  - shared Kotlin models and adapters reused by this module through Gradle sourceSets

## Current MVP behavior

The current MVP screen lets you:

- type one product message into a single composer
- paste a product URL into that same message box
- attach up to five images from the camera or photo gallery
- let ML Kit extract visible text from attached images before Gemma 4 identification
- let the app preview URL context automatically before analysis
- reuse the same URL sufficiency rules as the web app, including stopping when a food page exposes only an incomplete ingredient snippet
- choose region text
- submit an `AnalyzeProductRequestDto` to the local API
- view:
  - product input / image upload
  - Analyze Product / Start new analysis
  - RiskLens Score
  - RiskLens Flags
  - scrollable Result explanation
  - disclaimer
  - Submit feedback

For food turns, the Android client mirrors the web flow: ingredients are the core product-specific input for RiskLens scoring, while Nutrition Facts are optional and only add non-scoring nutrition notes.

For URL turns, the Android client also mirrors the web intake behavior. If a retailer page exposes only a partial ingredient snippet, such as an Amazon accordion that shows a short fragment instead of the full formula, the phone app asks the user to paste the ingredient list or upload a clear ingredient-panel photo rather than running an overconfident analysis.

The Android client uses ML Kit only for fast on-device OCR. Gemma 4 remains responsible for interpreting noisy OCR, identifying the product, structuring fields, deriving nutrition flags, scoring, and supporting the downstream safety analysis. OpenAI remains evaluation-only and is not part of the phone product path.

The phone app does not maintain a second chemical ruleset for food dyes, melamine, PFAS, plasticizers, or black-plastic signals. After OCR normalization, it uses the same backend-owned retrieval, scoring, and formatter logic as the web app so both clients share the same evidence, confidence labels, and recommendations.

The phone identify flow mirrors web:

1. image capture or gallery upload
2. ML Kit OCR / label extraction
3. Gemma product identification
4. ingredient and nutrition parsing
5. chemical/process risk screening
6. nutrition flag derivation
7. shared RiskLens Score / RiskLens Flags / Result explanation rendering

## Run guide

See:

- `/Users/adelie/Projects/gemma4good/docs/run_on_pixel8.md`
