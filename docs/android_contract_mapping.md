# Android Contract Mapping

## Goal

Mirror the current Python-side contract into Android models without bringing over macOS-only or benchmark-only concerns.

## Source of truth

The current sources mirrored here are:

- `vnext_contract.py`
- `app_shared.py`
- `/analyze-product` request fields in the local API
- `/identify-product` request/response fields for Gemma 4 product identification after OCR
- `/analyze-product` response fields currently used by the app and tests

## Main mapping layers

### 1. Local client state

Python:

- `NormalizedProductPayload`
- `Stage2Decision`
- `ReviewSignal`
- `GroundedQueryEnvelope`

Android mirror:

- `NormalizedProductPayloadDto`
- `Stage2DecisionDto`
- `ReviewSignalDto`
- `GroundedQueryEnvelopeDto`

### 2. API request

Python API request model:

- `AnalyzeProductRequest`

Android mirror:

- `AnalyzeProductRequestDto`
- `IdentifyProductRequestDto`

### 3. API response

The response is currently composed in `service.analyze_product_for_app()` and includes:

- product matches
- chemical matches
- regulatory evidence
- warning interpretations
- literature evidence
- controversy topics
- inferred category
- serving recommendation
- recommendation bucket and reason
- concern sources
- evidence-scope summary
- user overlap summary
- review metadata

Android mirror:

- `AnalyzeProductResponseDto`
- `ProductIdentificationDto`
- nested DTOs for the key collections and summary objects

## Deliberate exclusions

These are not part of the Android production contract:

- OpenAI judge responses
- benchmark score distributions
- OCR benchmark artifacts
- report-generation structures

## Stability guidance

The Android shell should treat the following as high-stability fields:

- `product_name`
- `product_page_url`
- `raw_ocr_text`
- `ingredients_text`
- `nutrition_text`
- `warning_text`
- `region`
- `input_mode`
- `inferred_category`
- `recommendation`
- `concern_sources`
- `evidence_scope_summary`
- `chemical_evidence_pack`
- `user_overlap_summary`
- `review_reasons`

The following are lower-stability and should be used more cautiously in UI binding:

- `product_matches`
- `regulatory_evidence`
- `literature_evidence`
- `controversy_topics`
- `review_payload`

## Recommendation

For the first Android client, build UI around the stable summary layer first, and surface deeper evidence in an expandable details view.


### 4. Networking layer

The Android client should use:

- `Gemma4GoodApiService.kt` for Retrofit endpoint definitions
- `Gemma4GoodContractAdapters.kt` to convert a local envelope into `AnalyzeProductRequestDto`

This keeps request assembly logic close to the contract instead of scattering it across UI code.

The phone-specific identify path is:

```text
Android ML Kit OCR
-> IdentifyProductRequestDto
-> /identify-product
-> ProductIdentificationDto
-> NormalizedProductPayloadDto
-> /analyze-product
```

This preserves one shared reasoning boundary: ML Kit extracts text only, while Gemma 4 performs product identification and OCR interpretation.
