# Retrofit Usage Example

This example shows how the future Pixel 8 Android client can use the same app-side envelope contract and convert it into the current `/analyze-product` request.

## Recommended stack

- Retrofit
- OkHttp
- kotlinx.serialization
- Kotlin coroutines

## Retrofit builder example

```kotlin
val json = Json {
    ignoreUnknownKeys = true
    explicitNulls = false
}

val contentType = "application/json".toMediaType()

val retrofit = Retrofit.Builder()
    .baseUrl("http://10.0.2.2:8010/")
    .addConverterFactory(json.asConverterFactory(contentType))
    .build()

val api = retrofit.create(Gemma4GoodApiService::class.java)
```

For a real device on the same LAN, replace `10.0.2.2` with the reachable IP or hostname for the API server.

## Example request flow

```kotlin
val envelope = GroundedQueryEnvelopeDto(
    userId = "pixel8_demo_user",
    sessionId = UUID.randomUUID().toString(),
    payload = NormalizedProductPayloadDto(
        productName = "Waterproof baby bib",
        productPageUrl = "https://www.amazon.com/example",
        rawOcrText = "PVC waterproof bib. Warning: Cancer and Reproductive Harm...",
        ingredientText = "DEHP; PVC; soft vinyl layer",
        warningText = "WARNING: Cancer and Reproductive Harm - www.P65Warnings.ca.gov",
        safetyCautionText = "",
        categoryClues = "baby bib, waterproof, soft vinyl",
        region = "California, USA",
        inputMode = "image",
    ),
    stage2 = Stage2DecisionDto(
        productUseCategory = "children_products",
        materialOrForm = "pvc_vinyl",
        informationPriority = "material_first",
        confidenceNotes = "ocr_confirmed",
    ),
    review = ReviewSignalDto(
        userCorrectedText = false,
        userCorrectedCategory = false,
        queueForReview = false,
        reviewNotes = "",
    ),
)

val request = Gemma4GoodContractAdapters.envelopeToAnalyzeRequest(envelope)
val response = api.analyzeProduct(request)
```

## What the Android shell should show first

Bind the UI first to the stable summary layer:

- `response.inferredCategory`
- `response.recommendation`
- `response.concernSources`
- `response.evidenceScopeSummary`
- `response.userOverlapSummary`
- `response.reviewReasons`

Then expose deeper collections like:

- `response.regulatoryEvidence`
- `response.literatureEvidence`
- `response.controversyTopics`

in expandable details panels.
