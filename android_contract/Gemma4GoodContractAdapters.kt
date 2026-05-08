package good.gemma4good.contract

object Gemma4GoodContractAdapters {
    fun envelopeToAnalyzeRequest(envelope: GroundedQueryEnvelopeDto): AnalyzeProductRequestDto {
        val ingredientsText = listOf(
            envelope.payload.ingredientText,
            envelope.payload.categoryClues,
        ).filter { it.isNotBlank() }
            .joinToString(" | ")

        val warningText = listOf(
            envelope.payload.warningText,
            envelope.payload.safetyCautionText,
        ).filter { it.isNotBlank() }
            .joinToString(" | ")

        return AnalyzeProductRequestDto(
            userId = envelope.userId,
            sessionId = envelope.sessionId,
            productName = envelope.payload.productName,
            productPageUrl = envelope.payload.productPageUrl,
            rawOcrText = envelope.payload.rawOcrText,
            ingredientsText = ingredientsText,
            warningText = warningText,
            region = envelope.payload.region,
            inputMode = envelope.payload.inputMode,
            userCorrectedText = envelope.review.userCorrectedText,
            userCorrectedCategory = envelope.review.userCorrectedCategory,
            queueForReview = envelope.review.queueForReview,
            reviewNotes = envelope.review.reviewNotes,
            saveToHistory = true,
        )
    }
}
