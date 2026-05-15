package good.gemma4good.android.ui

import android.content.Context
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.FileProvider
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import good.gemma4good.android.data.network.RetrofitFactory
import good.gemma4good.android.data.repository.SafetyRepository
import good.gemma4good.contract.AnalyzeProductResponseDto
import good.gemma4good.contract.Gemma4GoodContractAdapters
import good.gemma4good.contract.GroundedQueryEnvelopeDto
import good.gemma4good.contract.IdentifyProductRequestDto
import good.gemma4good.contract.NormalizedProductPayloadDto
import good.gemma4good.contract.PreviewUrlRequestDto
import good.gemma4good.contract.PreviewUrlResponseDto
import good.gemma4good.contract.ProductIdentificationDto
import good.gemma4good.contract.ReviewSignalDto
import good.gemma4good.contract.Stage2DecisionDto
import java.io.File
import java.util.UUID
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import retrofit2.HttpException

data class ChatMessage(
    val role: String,
    val content: String,
)

private data class PreparedTurn(
    val inputMode: String,
    val productName: String,
    val productUseCategory: String,
    val productPageUrl: String,
    val rawText: String,
    val ingredientText: String,
    val nutritionText: String,
    val materialText: String,
    val packagingMaterial: String,
    val processingMethod: String,
    val processingDerivatives: String,
    val concentrationAssessment: String,
    val warningText: String,
    val categoryClues: String,
    val confidenceNotes: String = "",
)

class Gemma4GoodViewModel : ViewModel() {
    private val repository = SafetyRepository(RetrofitFactory.api)

    var userId by mutableStateOf("pixel8_demo_user")
    var region by mutableStateOf("California, USA")
    var messageInput by mutableStateOf("")

    val attachedImages = mutableStateListOf<Uri>()
    val chatMessages = mutableStateListOf<ChatMessage>()

    var isProcessing by mutableStateOf(false)
    var statusText by mutableStateOf("Idle")
    var errorText by mutableStateOf("")
    var nextStepText by mutableStateOf("")
    var latestAnalysis by mutableStateOf<AnalyzeProductResponseDto?>(null)
    var resultExplanation by mutableStateOf("")
    var feedbackInput by mutableStateOf("")
    var feedbackStatus by mutableStateOf("")

    private var tempCameraUri: Uri? = null
    private var lastPreparedTurn: PreparedTurn? = null

    private fun firstUrl(text: String): String {
        val regex = Regex("""https?://\S+""")
        return regex.find(text)?.value.orEmpty()
    }

    private fun stripUrls(text: String): String {
        return text.replace(Regex("""https?://\S+"""), "").trim()
    }

    private fun detectInputMode(message: String, images: List<Uri>): String {
        return when {
            images.isNotEmpty() -> "image"
            firstUrl(message).isNotBlank() -> "url"
            else -> "text"
        }
    }

    private fun deriveProductName(text: String): String {
        val trimmed = text.trim()
        if (trimmed.isBlank()) return ""
        return trimmed.lineSequence()
            .map { it.trim() }
            .firstOrNull { it.isNotBlank() }
            .orEmpty()
            .take(120)
    }

    private fun hasIngredientEvidence(text: String): Boolean {
        return Regex(
            """(?i)\b(ingredients?|contains|ingredient list)\b|內容物|成分"""
        ).containsMatchIn(text)
    }

    private fun hasNutritionEvidence(text: String): Boolean {
        return Regex(
            """(?i)\b(nutrition facts|serving size|calories|total sugars|added sugars|sodium|saturated fat)\b"""
        ).containsMatchIn(text)
    }

    private fun looksLikeOnlyProductName(text: String): Boolean {
        val clean = stripUrls(text)
        if (clean.isBlank()) return false
        if (hasIngredientEvidence(clean) || hasNutritionEvidence(clean)) return false
        return clean.length < 80 && clean.lines().count { it.isNotBlank() } <= 2
    }

    private fun likelyFoodText(text: String): Boolean {
        return Regex(
            """(?i)\b(food|snack|cookie|cookies|biscuit|chips?|cracker|waffle|cereal|tea|coffee|drink|beverage|sauce|meat|chocolate|candy|nutrition facts)\b"""
        ).containsMatchIn(text)
    }

    fun reset() {
        messageInput = ""
        attachedImages.clear()
        chatMessages.clear()
        statusText = "Idle"
        errorText = ""
        nextStepText = ""
        latestAnalysis = null
        resultExplanation = ""
        feedbackInput = ""
        feedbackStatus = ""
        lastPreparedTurn = null
    }

    fun addImage(uri: Uri) {
        if (!attachedImages.contains(uri) && attachedImages.size < 5) {
            attachedImages.add(uri)
        }
    }

    fun removeImage(uri: Uri) {
        attachedImages.remove(uri)
    }

    fun getTempCameraUri(context: Context): Uri {
        val directory = File(context.externalCacheDir, "Pictures")
        if (!directory.exists()) directory.mkdirs()
        val file = File(directory, "camera_capture_${System.currentTimeMillis()}.jpg")
        val uri = FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            file,
        )
        tempCameraUri = uri
        return uri
    }

    fun onCameraCaptureSuccess() {
        tempCameraUri?.let { addImage(it) }
        tempCameraUri = null
    }

    private suspend fun extractTextFromImage(context: Context, uri: Uri): String {
        val image = InputImage.fromFilePath(context, uri)
        val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
        return try {
            suspendCancellableCoroutine { continuation ->
                recognizer.process(image)
                    .addOnSuccessListener { result -> continuation.resume(result.text.trim()) }
                    .addOnFailureListener { exc -> continuation.resumeWithException(exc) }
            }
        } finally {
            recognizer.close()
        }
    }

    private suspend fun extractTextFromImagesWithMlKit(context: Context, images: List<Uri>): String {
        val chunks = mutableListOf<String>()
        images.take(5).forEachIndexed { index, uri ->
            runCatching { extractTextFromImage(context, uri) }
                .getOrNull()
                ?.takeIf { it.isNotBlank() }
                ?.let { text ->
                    chunks += buildString {
                        appendLine("Image ${index + 1}")
                        append(text)
                    }
                }
        }
        return chunks.joinToString("\n\n").trim()
    }

    private fun summarizeUserTurn(message: String, images: List<Uri>): String {
        val parts = mutableListOf<String>()
        stripUrls(message).takeIf { it.isNotBlank() }?.let(parts::add)
        firstUrl(message).takeIf { it.isNotBlank() }?.let(parts::add)
        if (images.isNotEmpty()) {
            parts += "[attached ${images.size} image(s)]"
        }
        return parts.joinToString("\n").ifBlank { "[empty turn]" }
    }

    private fun appendAssistantMessage(text: String) {
        chatMessages += ChatMessage(role = "assistant", content = text.trim())
        resultExplanation = text.trim()
    }

    private fun composeMissingFoodLabelMessage(productName: String): String {
        val subject = productName.ifBlank { "this food product" }
        return buildString {
            appendLine("This looks like a food product for $subject, but I still need the ingredient list and Nutrition Facts before a complete assessment.")
            appendLine()
            appendLine("Please upload clear close-up photos of:")
            appendLine("- the ingredient list")
            appendLine("- the Nutrition Facts table")
            appendLine()
            append("You can also paste those label details as text.")
        }
    }

    private fun composeNameOnlyMessage(text: String): String {
        val categoryNote = if (likelyFoodText(text)) {
            "\n\nBased on the product name alone, there may be category-level considerations, but that is not a product-specific finding."
        } else {
            ""
        }
        return "I only have the product name. Please upload or paste the ingredient list and nutrition facts so I can provide a more complete and product-specific assessment.$categoryNote"
    }

    private fun urlContextText(response: PreviewUrlResponseDto): String {
        return listOf(
            response.urlContext.productText,
            response.urlContext.ingredientsText,
            response.urlContext.nutritionText,
            response.urlContext.warningText,
        ).filter { it.isNotBlank() }
            .joinToString("\n\n")
            .trim()
    }

    private fun mergeIdentification(
        base: PreparedTurn,
        identified: ProductIdentificationDto,
    ): PreparedTurn {
        return base.copy(
            productName = identified.productName.ifBlank { base.productName },
            productUseCategory = identified.productUseCategory.ifBlank { base.productUseCategory },
            ingredientText = identified.ingredientText.ifBlank { base.ingredientText },
            nutritionText = identified.nutritionText.ifBlank { base.nutritionText },
            materialText = identified.materialText.ifBlank { base.materialText },
            packagingMaterial = identified.packagingMaterial.ifBlank { base.packagingMaterial },
            processingMethod = identified.processingMethod.ifBlank { base.processingMethod },
            processingDerivatives = identified.processingDerivatives.ifBlank { base.processingDerivatives },
            concentrationAssessment = identified.concentrationAssessment.ifBlank { base.concentrationAssessment },
            warningText = identified.warningText.ifBlank { base.warningText },
            categoryClues = listOf(
                base.categoryClues,
                identified.productUseCategory.takeUnless { it == "unknown" }.orEmpty(),
                identified.safetyClaims,
            ).filter { it.isNotBlank() }.joinToString(" | "),
            confidenceNotes = identified.confidenceNotes,
        )
    }

    private fun enrichTurnFromResponse(
        turn: PreparedTurn,
        response: AnalyzeProductResponseDto,
    ): PreparedTurn {
        return turn.copy(
            productName = turn.productName.ifBlank { deriveProductName(response.urlContext.productText) },
            ingredientText = turn.ingredientText.ifBlank { response.urlContext.ingredientsText },
            nutritionText = turn.nutritionText.ifBlank { response.urlContext.nutritionText },
            warningText = turn.warningText.ifBlank { response.urlContext.warningText },
        )
    }

    private suspend fun identifyWithGemma(turn: PreparedTurn): PreparedTurn {
        statusText = "Gemma is identifying product details..."
        val identified = repository.identifyProduct(
            IdentifyProductRequestDto(
                rawText = turn.rawText,
                inputMode = turn.inputMode,
            )
        )
        return mergeIdentification(turn, identified)
    }

    private suspend fun prepareTurn(
        context: Context,
        message: String,
        images: List<Uri>,
    ): PreparedTurn? {
        val inputMode = detectInputMode(message, images)
        val url = firstUrl(message)
        val typedText = stripUrls(message)

        if (inputMode == "text" && looksLikeOnlyProductName(typedText)) {
            appendAssistantMessage(composeNameOnlyMessage(typedText))
            statusText = "Needs more product details"
            nextStepText = "Add ingredients and nutrition facts, or attach label images."
            return null
        }

        if (inputMode == "url") {
            statusText = "Fetching product page..."
            val preview = repository.previewUrl(PreviewUrlRequestDto(productPageUrl = url, region = region))
            val pageText = urlContextText(preview)
            if (!preview.intakeAssessment.canProceed && typedText.isBlank()) {
                appendAssistantMessage(
                    buildString {
                        appendLine("I need better product information before I can continue.")
                        appendLine()
                        appendLine("Reason: ${preview.intakeAssessment.reason}")
                        appendLine()
                        append("Next step: ${preview.intakeAssessment.recommendedNextStep}")
                    }
                )
                statusText = "Needs better URL input"
                nextStepText = preview.intakeAssessment.recommendedNextStep
                return null
            }
            val combined = listOf(pageText, typedText).filter { it.isNotBlank() }.joinToString("\n\n")
            return PreparedTurn(
                inputMode = inputMode,
                productName = deriveProductName(preview.urlContext.productText.ifBlank { typedText }),
                productUseCategory = "unknown",
                productPageUrl = url,
                rawText = combined,
                ingredientText = preview.urlContext.ingredientsText,
                nutritionText = preview.urlContext.nutritionText,
                materialText = "",
                packagingMaterial = "",
                processingMethod = "",
                processingDerivatives = "",
                concentrationAssessment = "",
                warningText = preview.urlContext.warningText,
                categoryClues = combined,
            )
        }

        if (inputMode == "image") {
            statusText = "ML Kit is reading label text..."
            val ocrText = extractTextFromImagesWithMlKit(context, images)
            val combined = listOf(ocrText, typedText).filter { it.isNotBlank() }.joinToString("\n\n")
            if (combined.length < 20) {
                appendAssistantMessage(
                    "I could not read enough text from the uploaded images. Please try clearer close-up photos of the product front, ingredient list, or Nutrition Facts panel, or paste the label text."
                )
                statusText = "Needs clearer images"
                nextStepText = "Upload clearer label photos or paste the product details."
                return null
            }
            return PreparedTurn(
                inputMode = inputMode,
                productName = deriveProductName(typedText.ifBlank { ocrText }),
                productUseCategory = "unknown",
                productPageUrl = "",
                rawText = combined,
                ingredientText = if (hasIngredientEvidence(combined)) combined else "",
                nutritionText = if (hasNutritionEvidence(combined)) combined else "",
                materialText = "",
                packagingMaterial = "",
                processingMethod = "",
                processingDerivatives = "",
                concentrationAssessment = "",
                warningText = "",
                categoryClues = combined,
            )
        }

        if (typedText.isBlank()) {
            appendAssistantMessage("Please type product details, paste a product URL, or attach product images.")
            statusText = "Needs input"
            nextStepText = "Add product text, a URL, or images."
            return null
        }

        return PreparedTurn(
            inputMode = inputMode,
            productName = deriveProductName(typedText),
            productUseCategory = "unknown",
            productPageUrl = "",
            rawText = typedText,
            ingredientText = if (hasIngredientEvidence(typedText)) typedText else "",
            nutritionText = if (hasNutritionEvidence(typedText)) typedText else "",
            materialText = "",
            packagingMaterial = "",
            processingMethod = "",
            processingDerivatives = "",
            concentrationAssessment = "",
            warningText = "",
            categoryClues = typedText,
        )
    }

    private fun buildRequest(
        turn: PreparedTurn,
        queueForReview: Boolean = false,
        reviewNotes: String = "Android single-composer turn",
        saveToHistory: Boolean = true,
    ) =
        Gemma4GoodContractAdapters.envelopeToAnalyzeRequest(
            GroundedQueryEnvelopeDto(
                userId = userId,
                sessionId = UUID.randomUUID().toString(),
                payload = NormalizedProductPayloadDto(
                    productName = turn.productName,
                    productPageUrl = turn.productPageUrl,
                    rawOcrText = turn.rawText,
                    ingredientText = turn.ingredientText,
                    nutritionText = turn.nutritionText,
                    materialText = turn.materialText,
                    processingMethod = turn.processingMethod,
                    packagingMaterial = turn.packagingMaterial,
                    processingDerivatives = turn.processingDerivatives,
                    concentrationAssessment = turn.concentrationAssessment,
                    warningText = turn.warningText,
                    safetyCautionText = "",
                    categoryClues = turn.categoryClues,
                    region = region,
                    inputMode = turn.inputMode,
                    userQuestion = "",
                ),
                stage2 = Stage2DecisionDto(
                    productUseCategory = turn.productUseCategory,
                    confidenceNotes = "android_single_composer_${turn.inputMode}_flow",
                ),
                review = ReviewSignalDto(
                    userCorrectedText = false,
                    userCorrectedCategory = false,
                    queueForReview = queueForReview,
                    reviewNotes = reviewNotes,
                ),
            )
        ).copy(saveToHistory = saveToHistory)

    private fun foodLabelFieldsMissing(turn: PreparedTurn, response: AnalyzeProductResponseDto): Boolean {
        val category = response.inferredCategory.productUseCategory.lowercase()
        val isFood = category.contains("food") ||
            likelyFoodText("${turn.productName}\n${turn.rawText}")
        if (!isFood) return false
        val effectiveIngredientText = turn.ingredientText.ifBlank { response.urlContext.ingredientsText }
        val effectiveNutritionText = turn.nutritionText.ifBlank { response.urlContext.nutritionText }
        return effectiveIngredientText.isBlank() || effectiveNutritionText.isBlank()
    }

    private fun formatResult(response: AnalyzeProductResponseDto, turn: PreparedTurn): String {
        val effectiveIngredientText = turn.ingredientText.ifBlank { response.urlContext.ingredientsText }
        val effectiveNutritionText = turn.nutritionText.ifBlank { response.urlContext.nutritionText }
        val ingredientStatus = if (effectiveIngredientText.isBlank()) "missing" else "provided"
        val nutritionStatus = if (effectiveNutritionText.isBlank()) "missing" else "provided"
        val isFood = response.inferredCategory.productUseCategory.lowercase().contains("food") ||
            likelyFoodText("${turn.productName}\n${turn.rawText}")
        val analysisStatus = if (!isFood || (ingredientStatus == "provided" && nutritionStatus == "provided")) {
            "complete"
        } else {
            "limited"
        }
        return buildString {
            appendLine("## Information Completeness Check")
            appendLine("Product name: ${if (turn.productName.isBlank()) "missing" else "identified"}")
            appendLine("Category: ${response.inferredCategory.productUseCategory.ifBlank { "unknown" }}")
            appendLine("Ingredient list: $ingredientStatus")
            appendLine("Nutrition facts: $nutritionStatus")
            appendLine("Input source: ${turn.inputMode}")
            appendLine("Analysis status: $analysisStatus")
            appendLine()
            appendLine("## Product Overview")
            appendLine("Product: ${turn.productName.ifBlank { "Unknown product" }}")
            appendLine("Category: ${response.inferredCategory.productUseCategory}")
            appendLine("Input source: ${turn.inputMode}")
            appendLine()
            appendLine("## Key Screening Signals")
            if (turn.processingDerivatives.isNotBlank()) {
                appendLine("- ${turn.processingDerivatives}: possible process-derived signal from ${turn.processingMethod.ifBlank { "product processing clues" }}")
            }
            if (response.chemicalMatches.isNotEmpty()) {
                response.chemicalMatches.take(5).forEach { match ->
                    appendLine("- ${match.preferredName ?: match.matchedTerm ?: "Chemical match"}: listed or matched from product text")
                }
            }
            if (turn.processingDerivatives.isBlank() && response.chemicalMatches.isEmpty()) {
                appendLine("- No major product-specific chemical signal identified from the available text.")
            }
            appendLine()
            appendLine("## Safety Analysis")
            appendLine("### Processing & Derivatives")
            appendLine(
                if (turn.processingDerivatives.isNotBlank()) {
                    "${turn.processingDerivatives} was flagged from ${turn.processingMethod.ifBlank { "processing" }} clues. This is not necessarily a listed ingredient."
                } else {
                    "No process-derived compound was identified from the available product text."
                }
            )
            appendLine()
            appendLine("### Ingredient-Based Concerns")
            appendLine(
                if (response.chemicalMatches.isNotEmpty()) {
                    response.chemicalMatches.take(5).joinToString(separator = "\n") { match ->
                        "- ${match.preferredName ?: match.matchedTerm ?: "Chemical match"}"
                    }
                } else if (effectiveIngredientText.isBlank()) {
                    "Ingredient list was not provided, so ingredient-level concentration analysis cannot be performed."
                } else {
                    "No direct chemical matches were found in the available ingredient text."
                }
            )
            appendLine()
            appendLine("### Nutrition Flags")
            appendLine(
                if (effectiveNutritionText.isBlank()) {
                    "Nutrition facts were not provided, so nutrition-level assessment is limited."
                } else {
                    "Nutrition facts were included in the normalized input for downstream food scoring."
                }
            )
            appendLine()
            appendLine("### Sources and Regions")
            if (response.concernSources.isNotEmpty()) {
                response.concernSources.take(5).forEach { src ->
                    appendLine("- ${src.sourceAuthority ?: "unknown"} / ${src.countryOrJurisdiction ?: "unknown"} / ${src.regulatoryStatus ?: "unknown"}")
                }
            } else {
                appendLine("No product-specific regulatory source was returned from the available input.")
            }
            appendLine()
            appendLine("## Practical Recommendation")
            appendLine("${response.recommendation.recommendationBucket}: ${response.recommendation.recommendationReason}")
            appendLine()
            appendLine("## Important Caveat")
            appendLine("This analysis is based on the available label text only. OCR or category-level signals do not confirm quantity or batch-specific safety without complete label data or testing.")
        }.trim()
    }

    fun submit(context: Context) {
        val message = messageInput.trim()
        val images = attachedImages.toList()
        if (message.isBlank() && images.isEmpty()) {
            errorText = "Type product text, paste a URL, or attach product images."
            statusText = "Needs input"
            return
        }

        errorText = ""
        nextStepText = ""
        latestAnalysis = null
        resultExplanation = ""
        feedbackStatus = ""
        isProcessing = true
        statusText = "Collecting product information..."
        chatMessages += ChatMessage(role = "user", content = summarizeUserTurn(message, images))
        messageInput = ""
        attachedImages.clear()

        viewModelScope.launch {
            runCatching {
                val preparedTurn = prepareTurn(context, message, images) ?: return@runCatching null
                val turn = identifyWithGemma(preparedTurn)
                statusText = "Analyzing..."
                val response = repository.analyzeProduct(buildRequest(turn))
                enrichTurnFromResponse(turn, response) to response
            }.onSuccess { result ->
                isProcessing = false
                if (result == null) return@onSuccess
                val (turn, response) = result
                if (!response.intakeAssessment.canProceed) {
                    statusText = "Needs better input"
                    nextStepText = response.intakeAssessment.recommendedNextStep
                    appendAssistantMessage(
                        buildString {
                            appendLine("I need better ${turn.inputMode} input before I can continue.")
                            appendLine()
                            appendLine("Reason: ${response.intakeAssessment.reason}")
                            appendLine()
                            append("Next step: ${response.intakeAssessment.recommendedNextStep}")
                        }
                    )
                    return@onSuccess
                }

                if (foodLabelFieldsMissing(turn, response)) {
                    statusText = "Needs food label details"
                    nextStepText = "Upload ingredients and Nutrition Facts, or paste them as text."
                    appendAssistantMessage(composeMissingFoodLabelMessage(turn.productName))
                    return@onSuccess
                }

                statusText = "Done"
                latestAnalysis = response
                lastPreparedTurn = turn
                appendAssistantMessage(formatResult(response, turn))
            }.onFailure { exc ->
                isProcessing = false
                statusText = "Error"
                errorText = when {
                    exc is HttpException && exc.code() == 404 ->
                        "The local API is missing the current phone-app endpoint. Restart the repo-local API server so `/identify-product` is loaded."
                    else -> exc.message ?: "Unknown error"
                }
                appendAssistantMessage("I could not finish that turn. ${errorText}")
            }
        }
    }

    fun submitFeedback() {
        val turn = lastPreparedTurn
        val notes = feedbackInput.trim()
        if (turn == null || latestAnalysis == null) {
            feedbackStatus = "Analyze a product first, then submit feedback."
            return
        }
        if (notes.isBlank()) {
            feedbackStatus = "Add a short correction or feedback note first."
            return
        }
        isProcessing = true
        feedbackStatus = "Submitting feedback..."
        viewModelScope.launch {
            runCatching {
                repository.analyzeProduct(
                    buildRequest(
                        turn,
                        queueForReview = true,
                        reviewNotes = notes,
                        saveToHistory = false,
                    )
                )
            }.onSuccess { response ->
                isProcessing = false
                feedbackInput = ""
                feedbackStatus = response.reviewQueueId?.let { "Feedback submitted for review (case $it)." }
                    ?: "Feedback submitted for review."
            }.onFailure { exc ->
                isProcessing = false
                feedbackStatus = "Could not submit feedback: ${exc.message ?: "Unknown error"}"
            }
        }
    }
}
