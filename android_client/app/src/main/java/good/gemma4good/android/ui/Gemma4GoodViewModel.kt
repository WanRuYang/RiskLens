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
import good.gemma4good.contract.IdentifiedRiskDto
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
            appendLine("This looks like a food product for $subject, but I still need the ingredient list for a more complete RiskLens screening.")
            appendLine()
            appendLine("Please upload clear close-up photos of:")
            appendLine("- the ingredient list")
            appendLine("- the Nutrition Facts table, if you want optional nutrition notes")
            appendLine()
            append("The RiskLens Score uses chemical, material, contaminant, and process-related signals. Nutrition Facts are optional and only add nutrition notes; they do not change the A-E RiskLens Score.")
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
            response.urlContext.materialsText,
            response.urlContext.nutritionText,
            response.urlContext.warningText,
        ).filter { it.isNotBlank() }
            .joinToString("\n\n")
            .trim()
    }

    private fun composeUrlIntakeFailureMessage(
        preview: PreviewUrlResponseDto,
        url: String,
    ): String {
        val assessment = preview.intakeAssessment
        val isAmazon = url.contains("amazon.", ignoreCase = true)
        val heading = when {
            assessment.status == "needs_food_ingredients" &&
                isAmazon &&
                preview.urlContext.ingredientPanelFound ->
                "I found the Amazon product page, but Amazon only exposed an incomplete ingredient snippet to the app."
            assessment.status == "needs_food_ingredients" && isAmazon ->
                "I found the Amazon product page, but Amazon did not expose the ingredient panel to the app."
            assessment.status == "needs_food_ingredients" ->
                "I found the product page, but I still need the ingredient list before I can continue."
            assessment.status in setOf("needs_better_url", "blocked_by_site", "blocked/insufficient") ->
                "I could not read enough product information from that webpage."
            else ->
                "I need better product information before I can continue."
        }
        val nextStep = when {
            assessment.status == "needs_food_ingredients" ->
                "Please paste the ingredient list or upload a clear photo of the ingredient panel. You do not need to re-enter the same URL."
            assessment.status in setOf("needs_better_url", "blocked_by_site", "blocked/insufficient") ->
                "Please paste the product name/description plus the material or ingredient list, or upload product/package images instead."
            else -> assessment.recommendedNextStep
        }
        return buildString {
            appendLine(heading)
            appendLine()
            appendLine("Reason: ${assessment.reason}")
            appendLine()
            append("Next step: $nextStep")
        }
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
            materialText = turn.materialText.ifBlank { response.urlContext.materialsText },
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
                appendAssistantMessage(composeUrlIntakeFailureMessage(preview, url))
                statusText = "Needs better URL input"
                nextStepText = when (preview.intakeAssessment.status) {
                    "needs_food_ingredients" ->
                        "Paste the ingredient list or upload a clear ingredient-panel photo."
                    else -> preview.intakeAssessment.recommendedNextStep
                }
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
                materialText = preview.urlContext.materialsText,
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
        return effectiveIngredientText.isBlank()
    }

    private fun formatResult(response: AnalyzeProductResponseDto, turn: PreparedTurn): String {
        val summary = response.structuredRiskOutput.productSummary
        val risks = response.structuredRiskOutput.identifiedRisks
        val effectiveIngredientText = cleanProductInfoIngredientText(
            turn.ingredientText.ifBlank { response.urlContext.ingredientsText }
        )
        val effectiveNutritionText = turn.nutritionText.ifBlank { response.urlContext.nutritionText }
        val productName = summary.productName.ifBlank { turn.productName.ifBlank { "Unknown product" } }
        val category = displayCategory(response, summary.productCategory)
        val isFood = summary.isFood ||
            response.inferredCategory.productUseCategory.lowercase().contains("food") ||
            likelyFoodText("${turn.productName}\n${turn.rawText}")
        return if (isFood) {
            formatFoodReport(
                productName = productName,
                category = category,
                ingredients = effectiveIngredientText,
                nutritionAvailable = effectiveNutritionText.isNotBlank(),
                nutritionText = effectiveNutritionText,
                nutritionFlags = response.risklensScore?.nutritionFlags.orEmpty(),
                risks = risks,
            )
        } else {
            formatNonFoodReport(
                productName = productName,
                category = category,
                ingredients = effectiveIngredientText,
                risks = risks,
                useGuidance = summary.useGuidance,
            )
        }
    }

    private fun formatFoodReport(
        productName: String,
        category: String,
        ingredients: String,
        nutritionAvailable: Boolean,
        nutritionText: String,
        nutritionFlags: List<String>,
        risks: List<IdentifiedRiskDto>,
    ): String {
        return buildString {
            appendLine("## Product Identity")
            appendLine("Product: **$productName**")
            appendLine("Category: **${category.ifBlank { "Food" }}**")
            appendLine()
            appendLine("## Composition (What it is made of)")
            appendLine("Ingredients: ${ingredients.ifBlank { "Missing" }}")
            appendLine("Nutrition facts: ${if (nutritionAvailable) nutritionText else "Missing"}")
            appendLine()
            appendLine("## Potential Chemical Signals")
            appendLine(formatChemicalSignalsSection(risks))
            appendLine()
            formatNutritionNote(nutritionFlags, nutritionAvailable, nutritionText)?.let {
                appendLine(it)
                appendLine()
            }
            appendLine("## Recommendation")
            appendLine(practicalRecommendation(risks, nutritionFlags, ingredients.isNotBlank(), nutritionAvailable))
            appendLine()
            appendLine("## Caveat")
            appendLine(commonCaveat())
        }.trim()
    }

    private fun formatNonFoodReport(
        productName: String,
        category: String,
        ingredients: String,
        risks: List<IdentifiedRiskDto>,
        useGuidance: List<String>,
    ): String {
        return buildString {
            appendLine("## Product Identity")
            appendLine("Product: **$productName**")
            appendLine("Category: **${category.ifBlank { "Non-food" }}**")
            appendLine()
            appendLine("## Composition (What it is made of)")
            appendLine("Materials / Ingredients: ${ingredients.ifBlank { "Missing" }}")
            appendLine()
            appendLine("---")
            appendLine()
            appendLine("## Potential Chemical Signals")
            appendLine(formatChemicalSignalsSection(risks))
            appendLine()
            appendLine("---")
            appendLine()
            appendLine("## Use Guidance")
            appendLine(
                useGuidance.takeIf { it.isNotEmpty() }?.joinToString("\n") { "- $it" }
                    ?: "No specific use guidance identified for the detected signals."
            )
            appendLine()
            appendLine("---")
            appendLine()
            appendLine("## Caveat")
            appendLine(commonCaveat())
        }.trim()
    }

    private fun displayCategory(response: AnalyzeProductResponseDto, summaryCategory: String): String {
        val rawParts = listOf(
            response.inferredCategory.productUseCategory,
            response.inferredCategory.materialSubcategory,
            summaryCategory,
        )
        val tokens = mutableListOf<String>()
        rawParts.forEach { part ->
            part.split(Regex("""\s*[/;]\s*"""))
                .map { it.trim() }
                .filter { it.isNotBlank() && !it.equals("unknown", ignoreCase = true) }
                .forEach { token ->
                    if (tokens.none { it.equals(token, ignoreCase = true) }) {
                        tokens += token
                    }
                }
        }
        return tokens.joinToString(" / ").ifBlank { "unknown" }
    }

    private fun cleanProductInfoIngredientText(value: String): String {
        if (value.isBlank()) return ""
        val strongStop = Regex(
            """(?is)\b(?:nutrition\s+facts|valeur\s+nutritive|amount\s*/?\s*serving|amount\s+per\s+serving|%\s*dv|%\s*daily\s+value|daily\s+value)\b"""
        )
        val beforeNutrition = strongStop.split(value, limit = 2).firstOrNull().orEmpty()
        val nutritionRow = Regex(
            """(?i)\b(?:calories?|total\s+fat|saturated\s+fat|trans\s+fat|cholesterol|sodium|fat\s*/\s*lipides|total\s+carbohydrates?|carbohydrate\s*/\s*glucides|fibre|fiber|sugars?\s*/\s*sucres?|protein|calcium|iron|potassium)\b"""
        )
        val keptLines = beforeNutrition.lineSequence()
            .filterNot { line -> nutritionRow.containsMatchIn(line) && Regex("""\d|%""").containsMatchIn(line) }
            .joinToString("\n")
        return keptLines
            .replace(
                Regex(
                    """(?is)\s*\|\s*(?:PRODUCT|INGREDIENTS?|NUTRITION FACTS|WARNINGS/CLAIMS)\s*:\s*NO READABLE TEXT.*$"""
                ),
                "",
            )
            .replace(
                Regex("""(?im)^\s*(?:(?:PRODUCT|INGREDIENTS?|NUTRITION FACTS|WARNINGS/CLAIMS)\s*:\s*)+$"""),
                "",
            )
            .replace(Regex("""(?im)^\s*NO READABLE TEXT\s*$"""), "")
            .replace(Regex("""(?i)\b(?:amount\s*/?\s*serving|amount\s+per\s+serving)\b.*$"""), "")
            .replace(Regex("""\s+"""), " ")
            .trim(' ', '|', ',', ';')
    }

    private fun formatChemicalSignalsSection(risks: List<IdentifiedRiskDto>): String {
        if (risks.isEmpty()) {
            return "No major risk warnings were identified from the available ingredient and category information."
        }
        return risks.joinToString("\n\n") { risk ->
            val name = risk.chemicalName.ifBlank { "Risk signal" }
            val why = risk.consumerExplanation.ifBlank { "Screening signal from available product information." }
            val meaning = risk.meaning.ifBlank { why }
            val listedSources = risk.riskSources
                .filter { it.isListedOrWarned && it.source.isNotBlank() }
                .joinToString("\n") { "  - ${it.source}: ${it.riskReason.ifBlank { "Substance of concern" }}" }
                .ifBlank { "  - (Inferred from category or material clues)" }
            buildString {
                appendLine("### $name")
                appendLine("- Why flagged: $why")
                appendLine("- Type: ${riskSignalType(risk)}")
                appendLine("- Confidence: ${displayConfidence(risk)}")
                appendLine("- Evidence source: ${risk.evidenceSource.ifBlank { "general_info" }}")
                appendLine("- Route relevance: ${risk.routeRelevance.ifBlank { "uncertain" }}")
                appendLine("- Exposure likelihood: ${risk.exposureLikelihood.ifBlank { "theoretical" }}")
                appendLine("- Risk points: ${risk.riskPoints}")
                appendLine("- Sources:")
                appendLine(listedSources)
                append("- Meaning: $meaning")
            }
        }
    }

    private fun formatNutritionNote(
        nutritionFlags: List<String>,
        nutritionAvailable: Boolean,
        nutritionText: String,
    ): String? {
        if (!nutritionAvailable && nutritionFlags.isEmpty()) return null
        return buildString {
            appendLine("## Optional Nutrition Note")
            when {
                !nutritionAvailable -> append(
                    "Nutrition facts were not provided, so nutrition-level assessment is limited."
                )
                nutritionFlags.isEmpty() -> append(
                    "No major added sugar, sodium, saturated fat, or calorie flag was identified from the available Nutrition Facts text."
                )
                else -> nutritionFlags.forEachIndexed { index, flag ->
                    if (index > 0) appendLine()
                    append("- **$flag**: ${nutritionDetail(flag, nutritionText)}")
                }
            }
        }.trim()
    }

    private fun practicalRecommendation(
        risks: List<IdentifiedRiskDto>,
        nutritionFlags: List<String>,
        ingredientAvailable: Boolean,
        nutritionAvailable: Boolean,
    ): String {
        val strongest = risks
            .map { it.cautionLevel.ifBlank { it.userRecommendation }.lowercase() }
            .toSet()
        val lines = mutableListOf<String>()
        when {
            "avoid for sensitive groups" in strongest || "avoid if allergic" in strongest ->
                lines += "Review the matched concern(s), especially for sensitive groups, allergies, pregnancy, children, or frequent use."
            "limit frequent exposure" in strongest ->
                lines += "Occasional use may be reasonable for many consumers, but consider limiting frequent repeated exposure."
            risks.isNotEmpty() ->
                lines += "No major high-confidence concern was identified; use normal product-specific judgment."
            else ->
                lines += "No major risk warnings were identified from the available information."
        }
        if (nutritionFlags.isNotEmpty()) {
            lines += "Nutrition-wise, note: ${nutritionFlags.joinToString(", ")}."
        }
        val missing = buildList {
            if (!ingredientAvailable) add("ingredient list")
            if (!nutritionAvailable) add("Nutrition Facts panel")
        }
        if (missing.isNotEmpty()) {
            lines += "Note: A more complete assessment would benefit from the missing ${missing.joinToString(", ")}."
        }
        return lines.joinToString("\n")
    }

    private fun riskSignalType(risk: IdentifiedRiskDto): String {
        val text = listOf(
            risk.identificationMethod,
            risk.detectionBasis,
            risk.evidenceFromProduct,
            risk.chemicalName,
        ).joinToString(" ").lowercase()
        return when {
            listOf("process", "acrylamide", "pah", "nitrosamine", "glycidyl", "3-mcpd").any { it in text } ->
                "Process-derived"
            listOf("packaging", "material", "bpa", "phthalate", "pfas", "ptfe").any { it in text } ->
                "Material-based / Packaging-related"
            "use" in text -> "Use-related"
            listOf("nutrition", "added sugar", "corn syrup").any { it in text } -> "Nutrition-related"
            "ingredient" in text || risk.identificationMethod == "listed ingredient" -> "Ingredient-based"
            else -> "Unknown / Screening signal"
        }
    }

    private fun displayConfidence(risk: IdentifiedRiskDto): String {
        val raw = risk.confidenceLevel.ifBlank { risk.confidence }.lowercase()
        return when (raw) {
            "explicit", "confirmed", "high" -> "Confirmed"
            "likely", "medium" -> "Likely"
            "possible", "low" -> "Possible"
            "weak inference", "unknown" -> "Unknown"
            else -> raw.replaceFirstChar { if (it.isLowerCase()) it.titlecase() else it.toString() }.ifBlank { "Unknown" }
        }
    }

    private fun nutritionDetail(flag: String, nutritionText: String): String {
        fun labelClue(regex: Regex, label: String): String? {
            val match = regex.find(nutritionText) ?: return null
            val clue = match.groupValues.drop(1).filter { it.isNotBlank() }.joinToString(" ").trim()
            return clue.takeIf { it.isNotBlank() }?.let { "Label clue: $label $it." }
        }
        return when {
            flag == "High added sugar" ->
                labelClue(
                    Regex("""(?i)(?:includes?\s+)?added\s+sugars?\s*([\d.]+\s*g)?\s*(\d+\s*%)?"""),
                    "added sugars",
                ) ?: "Sugar or added-sugar wording appears in the available ingredient or nutrition text."
            flag.contains("saturated", ignoreCase = true) ->
                labelClue(
                    Regex("""(?i)saturated\s+fat\s*([\d.]+\s*g)?\s*(\d+\s*%)?"""),
                    "saturated fat",
                ) ?: "Palm oil, palm kernel, vegetable fats, or saturated-fat wording appears in the available label text."
            flag.contains("sodium", ignoreCase = true) ->
                labelClue(
                    Regex("""(?i)sodium\s*([\d.]+\s*mg)?\s*(\d+\s*%)?"""),
                    "sodium",
                ) ?: "Sodium or salt wording appears in the available label text."
            else -> "Nutrition-related screening flag from available label text."
        }
    }

    private fun commonCaveat(): String {
        return "This is a screening result only. It does not confirm the presence or amount of any chemical in this specific product. Product-specific confirmation would require a full ingredient/material disclosure, SDS, supplier data, regulatory notice, or lab testing."
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
                    nextStepText = "Upload ingredients, or paste them as text. Nutrition Facts are optional for nutrition notes."
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
                val details = buildList {
                    response.userFeedbackId?.let { add("feedback $it") }
                    response.reviewQueueId?.let { add("case $it") }
                }
                feedbackStatus = if (details.isNotEmpty()) {
                    "Feedback submitted for review (${details.joinToString(", ")})."
                } else {
                    "Feedback submitted for review."
                }
            }.onFailure { exc ->
                isProcessing = false
                feedbackStatus = "Could not submit feedback: ${exc.message ?: "Unknown error"}"
            }
        }
    }
}
