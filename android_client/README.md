# Android MVP Client

This folder is a minimal Android client shell for the future Pixel 8 product path. It now enforces the same three input modes as the macOS product app: image, URL, or typed text.

It is intentionally scoped to:

- one selected input mode at a time: image, URL, or typed text
- region selection
- image-intake placeholder fields
- OCR review text before analysis
- URL preview step before analysis
- URL-only request path
- typed text fallback path
- calling the current `/analyze-product` API
- showing the grounded summary response and next-step guidance

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

- choose one mode: image, URL, or text
- type a product name
- in image mode: enter image placeholders and reviewed OCR text
- in URL mode: provide a product URL and preview what the app can fetch before analysis
- in text mode: provide a typed product description
- choose region text
- submit an `AnalyzeProductRequestDto` to the local API
- view:
  - inferred category
  - recommendation bucket
  - recommendation reason
  - concern sources
  - review reasons

## Run guide

See:

- `/Users/adelie/Projects/gemma4good/docs/run_on_pixel8.md`
