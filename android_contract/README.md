# Android Contract Mirror

This folder defines the Android-side JSON models that mirror the current Python app and local API contract.

## Purpose

These models are intended for the future Pixel 8 client shell. They are not benchmark-only utilities.

The goal is to keep Android aligned with the same portable core used by:

- `vnext_contract.py`
- `app_shared.py`
- the local FastAPI `analyze-product` endpoint
- the Stage 2 benchmark payload

## Files

- `Gemma4GoodApiModels.kt`
  - Kotlin `@Serializable` data models for:
    - local app-side normalized payloads
    - API requests
    - API responses
    - review queue requests and items
- `Gemma4GoodApiService.kt`
  - Retrofit service interface for the current local API endpoints
- `Gemma4GoodContractAdapters.kt`
  - adapter that converts the app-side envelope into the current `/analyze-product` request
- `RetrofitUsageExample.md`
  - sample Retrofit builder and request flow for the Pixel 8 client shell

## Model groups

### App-side local contract

- `NormalizedProductPayloadDto`
- `Stage2DecisionDto`
- `ReviewSignalDto`
- `GroundedQueryEnvelopeDto`

Use these before the Android shell calls the local or remote retrieval API.

### API request contract

- `AnalyzeProductRequestDto`
- `CuratedCorrectionRequestDto`

### API response contract

- `AnalyzeProductResponseDto`
- `HealthResponseDto`
- `ReviewQueueItemDto`

## Important production rule

These models are for the product path.

They do **not** include:

- OpenAI benchmark judge payloads
- OCR benchmark result models
- report-only evaluation structures

Those stay in the macOS development and evaluation environment.

## Mapping notes

- Python `product_use_category` remains Android `productUseCategory` with `@SerialName`
- Python `material_or_form` is used in Stage 2 local reasoning models
- Python API returns `material_subcategory` inside `inferred_category`, so Android mirrors that separately
- `servingRecommendation` is nullable because the DB may not yet have a row for every category/material pair
- `reviewPayload` remains a raw `JsonElement` because it is a debug/review object rather than a stable end-user UI model

## Recommended Android implementation order

1. Use `AnalyzeProductRequestDto` and `AnalyzeProductResponseDto` in networking first.
2. Use `NormalizedProductPayloadDto` and `GroundedQueryEnvelopeDto` in the client-side state layer.
3. Add thin mappers from API DTOs into UI view models after the retrieval contract is stable.
