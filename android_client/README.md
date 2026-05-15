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
- showing grounded results and next-step guidance in a chat-like transcript

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
- choose region text
- submit an `AnalyzeProductRequestDto` to the local API
- view:
  - inferred category
  - recommendation bucket
  - recommendation reason
  - concern sources
  - review reasons

For food turns, the Android client now mirrors the web flow: if the current evidence does not include both an ingredient list and Nutrition Facts, it asks for those label images or pasted text before presenting a complete assessment.

The Android client uses ML Kit only for OCR. Gemma 4 remains responsible for interpreting noisy OCR, identifying the product, structuring fields, and supporting the downstream safety analysis. OpenAI remains evaluation-only and is not part of the phone product path.

## Run guide

See:

- `/Users/adelie/Projects/gemma4good/docs/run_on_pixel8.md`
