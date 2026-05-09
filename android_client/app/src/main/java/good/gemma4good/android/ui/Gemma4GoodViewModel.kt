package good.gemma4good.android.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import good.gemma4good.android.data.network.RetrofitFactory
import good.gemma4good.android.data.repository.SafetyRepository
import good.gemma4good.contract.Gemma4GoodContractAdapters
import good.gemma4good.contract.GroundedQueryEnvelopeDto
import good.gemma4good.contract.NormalizedProductPayloadDto
import good.gemma4good.contract.PreviewUrlRequestDto
import good.gemma4good.contract.ReviewSignalDto
import good.gemma4good.contract.Stage2DecisionDto
import java.util.UUID
import kotlinx.coroutines.launch

class Gemma4GoodViewModel : ViewModel() {
    private val repository = SafetyRepository(RetrofitFactory.api)

    var userId by mutableStateOf("pixel8_demo_user")
    var region by mutableStateOf("California, USA")
    var inputMode by mutableStateOf("image")
    var productName by mutableStateOf("")
    var productPageUrl by mutableStateOf("")
    var directText by mutableStateOf("")
    var frontImageUri by mutableStateOf("")
    var ingredientsImageUri by mutableStateOf("")
    var warningImageUri by mutableStateOf("")
    var ocrReviewText by mutableStateOf("")
    var statusText by mutableStateOf("Idle")
    var resultSummary by mutableStateOf("")
    var errorText by mutableStateOf("")
    var nextStepText by mutableStateOf("")
    var urlPreviewText by mutableStateOf("")

    fun prepareOcrDraft() {
        val parts = buildList {
            if (frontImageUri.isNotBlank()) add("[FRONT_IMAGE_URI] $frontImageUri")
            if (ingredientsImageUri.isNotBlank()) add("[INGREDIENTS_IMAGE_URI] $ingredientsImageUri")
            if (warningImageUri.isNotBlank()) add("[WARNING_IMAGE_URI] $warningImageUri")
        }
        val scaffold = buildString {
            appendLine("# OCR Review Draft")
            if (parts.isNotEmpty()) {
                parts.forEach { appendLine(it) }
            } else {
                appendLine("(No image URIs entered yet)")
            }
            appendLine()
            appendLine("# Reviewed OCR Text")
            appendLine("Paste or revise OCR text here before analysis.")
        }.trim()
        ocrReviewText = scaffold
    }

    fun clearImageFlow() {
        frontImageUri = ""
        ingredientsImageUri = ""
        warningImageUri = ""
        ocrReviewText = ""
    }

    fun previewUrlFetch() {
        if (productPageUrl.isBlank()) {
            statusText = "Needs input"
            errorText = "Enter a product URL first."
            return
        }

        errorText = ""
        nextStepText = ""
        statusText = "Previewing URL..."
        urlPreviewText = ""

        viewModelScope.launch {
            runCatching {
                repository.previewUrl(PreviewUrlRequestDto(productPageUrl = productPageUrl.trim(), region = region))
            }.onSuccess { response ->
                val intake = response.intakeAssessment
                statusText = if (intake.canProceed) "URL preview ready" else "Needs better URL input"
                nextStepText = intake.recommendedNextStep
                errorText = if (intake.canProceed) "" else intake.reason
                urlPreviewText = buildString {
                    appendLine("Status: ${intake.status}")
                    appendLine("Can proceed: ${intake.canProceed}")
                    appendLine("Reason: ${intake.reason}")
                    appendLine("Recommended next step: ${intake.recommendedNextStep}")
                    appendLine()
                    if (response.urlContext.productText.isNotBlank()) {
                        appendLine("Fetched product text:")
                        appendLine(response.urlContext.productText)
                        appendLine()
                    }
                    if (response.urlContext.ingredientsText.isNotBlank()) {
                        appendLine("Fetched ingredients:")
                        appendLine(response.urlContext.ingredientsText)
                        appendLine()
                    }
                    if (response.urlContext.warningText.isNotBlank()) {
                        appendLine("Fetched warnings:")
                        appendLine(response.urlContext.warningText)
                        appendLine()
                    }
                    if (!response.urlContext.fetchError.isNullOrBlank()) {
                        appendLine("Fetch error:")
                        appendLine(response.urlContext.fetchError)
                    }
                }.trim()
            }.onFailure { exc ->
                statusText = "Error"
                errorText = exc.message ?: "Unknown error"
            }
        }
    }

    fun analyze() {
        errorText = ""
        nextStepText = ""
        statusText = "Analyzing..."
        resultSummary = ""

        if (inputMode == "image") {
            if (ocrReviewText.isBlank()) {
                statusText = "Needs input"
                errorText = "Image mode needs reviewed OCR text. If the current images are unreadable, try clearer images or switch to URL/text mode."
                return
            }
        }
        if (inputMode == "url") {
            if (productPageUrl.isBlank()) {
                statusText = "Needs input"
                errorText = "URL mode needs a product page URL."
                return
            }
        }
        if (inputMode == "text") {
            if (productName.isBlank() || directText.isBlank()) {
                statusText = "Needs input"
                errorText = "Text mode needs both a product name and a typed product description."
                return
            }
        }

        val imageClues = listOf(frontImageUri, ingredientsImageUri, warningImageUri)
            .filter { it.isNotBlank() }
            .joinToString(" | ")
        val normalizedRawText = when (inputMode) {
            "image" -> ocrReviewText.trim()
            "text" -> directText.trim()
            else -> ""
        }

        val envelope = GroundedQueryEnvelopeDto(
            userId = userId,
            sessionId = UUID.randomUUID().toString(),
            payload = NormalizedProductPayloadDto(
                productName = productName,
                productPageUrl = productPageUrl,
                rawOcrText = normalizedRawText,
                ingredientText = if (inputMode == "text") directText.trim() else normalizedRawText,
                warningText = "",
                safetyCautionText = "",
                categoryClues = imageClues,
                region = region,
                inputMode = inputMode,
                userQuestion = "",
            ),
            stage2 = Stage2DecisionDto(
                confidenceNotes = when (inputMode) {
                    "image" -> "android_image_placeholder_flow"
                    "url" -> "android_url_flow"
                    else -> "android_direct_text_flow"
                },
            ),
            review = ReviewSignalDto(
                userCorrectedText = inputMode == "image",
                userCorrectedCategory = false,
                queueForReview = false,
                reviewNotes = when (inputMode) {
                    "image" -> "Android MVP image placeholder flow"
                    "url" -> "Android MVP URL flow"
                    else -> ""
                },
            ),
        )

        val request = Gemma4GoodContractAdapters.envelopeToAnalyzeRequest(envelope)

        viewModelScope.launch {
            runCatching {
                repository.analyzeProduct(request)
            }.onSuccess { response ->
                val intake = response.intakeAssessment
                if (!intake.canProceed) {
                    statusText = "Needs better input"
                    errorText = intake.reason
                    nextStepText = intake.recommendedNextStep
                    resultSummary = ""
                    return@onSuccess
                }

                statusText = "Done"
                resultSummary = buildString {
                    appendLine("Input mode: $inputMode")
                    appendLine("Category: ${response.inferredCategory.productUseCategory}")
                    appendLine("Material: ${response.inferredCategory.materialSubcategory}")
                    appendLine("Recommendation: ${response.recommendation.recommendationBucket}")
                    appendLine("Reason: ${response.recommendation.recommendationReason}")
                    if (response.concernSources.isNotEmpty()) {
                        appendLine("Sources:")
                        response.concernSources.take(5).forEach { src ->
                            appendLine("- ${src.sourceAuthority ?: "unknown"} / ${src.countryOrJurisdiction ?: "unknown"} / ${src.regulatoryStatus ?: "unknown"}")
                        }
                    }
                    if (response.reviewReasons.isNotEmpty()) {
                        appendLine("Review reasons: ${response.reviewReasons.joinToString()}")
                    }
                }
            }.onFailure { exc ->
                statusText = "Error"
                errorText = exc.message ?: "Unknown error"
            }
        }
    }
}
