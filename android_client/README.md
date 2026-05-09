# Android MVP Client

This folder is a minimal Android client shell for the future Pixel 8 product path. It now follows the same single-composer intake model as the macOS product app: the user types product text, pastes a URL, or adds image evidence, and the app decides how to process that turn behind the scenes.

It is intentionally scoped to:

- one single-composer intake surface that auto-detects whether the turn is image-driven, URL-driven, or text-driven
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

- type one product message into a single composer
- paste a product URL into that same message box
- add optional image placeholders plus reviewed OCR text
- preview a URL fetch before analysis
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
