package good.gemma4good.contract

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class NormalizedProductPayloadDto(
    @SerialName("product_name") val productName: String = "",
    @SerialName("product_page_url") val productPageUrl: String = "",
    @SerialName("raw_ocr_text") val rawOcrText: String = "",
    @SerialName("ingredient_text") val ingredientText: String = "",
    @SerialName("nutrition_text") val nutritionText: String = "",
    @SerialName("material_text") val materialText: String = "",
    @SerialName("processing_method") val processingMethod: String = "",
    @SerialName("packaging_material") val packagingMaterial: String = "",
    @SerialName("processing_derivatives") val processingDerivatives: String = "",
    @SerialName("concentration_assessment") val concentrationAssessment: String = "",
    @SerialName("warning_text") val warningText: String = "",
    @SerialName("safety_caution_text") val safetyCautionText: String = "",
    @SerialName("category_clues") val categoryClues: String = "",
    val region: String = "California, USA",
    @SerialName("input_mode") val inputMode: String = "image",
    @SerialName("user_question") val userQuestion: String = "",
)

@Serializable
data class Stage2DecisionDto(
    @SerialName("product_use_category") val productUseCategory: String = "unknown",
    @SerialName("material_or_form") val materialOrForm: String = "unknown",
    @SerialName("information_priority") val informationPriority: String = "material_first",
    @SerialName("confidence_notes") val confidenceNotes: String = "",
)

@Serializable
data class ReviewSignalDto(
    @SerialName("user_corrected_text") val userCorrectedText: Boolean = false,
    @SerialName("user_corrected_category") val userCorrectedCategory: Boolean = false,
    @SerialName("queue_for_review") val queueForReview: Boolean = false,
    @SerialName("review_notes") val reviewNotes: String = "",
    @SerialName("review_reasons") val reviewReasons: List<String> = emptyList(),
)

@Serializable
data class GroundedQueryEnvelopeDto(
    @SerialName("user_id") val userId: String = "local_demo_user",
    @SerialName("session_id") val sessionId: String = "",
    val payload: NormalizedProductPayloadDto = NormalizedProductPayloadDto(),
    val stage2: Stage2DecisionDto = Stage2DecisionDto(),
    val review: ReviewSignalDto = ReviewSignalDto(),
)

@Serializable
data class AnalyzeProductRequestDto(
    @SerialName("user_id") val userId: String? = null,
    @SerialName("session_id") val sessionId: String? = null,
    @SerialName("product_name") val productName: String? = null,
    @SerialName("product_page_url") val productPageUrl: String? = null,
    @SerialName("raw_ocr_text") val rawOcrText: String? = null,
    @SerialName("ingredients_text") val ingredientsText: String? = null,
    @SerialName("nutrition_text") val nutritionText: String? = null,
    @SerialName("warning_text") val warningText: String? = null,
    val region: String? = null,
    @SerialName("input_mode") val inputMode: String? = null,
    @SerialName("user_corrected_text") val userCorrectedText: Boolean = false,
    @SerialName("user_corrected_category") val userCorrectedCategory: Boolean = false,
    @SerialName("queue_for_review") val queueForReview: Boolean = false,
    @SerialName("review_notes") val reviewNotes: String? = null,
    @SerialName("save_to_history") val saveToHistory: Boolean = true,
)

@Serializable
data class PreviewUrlRequestDto(
    @SerialName("product_page_url") val productPageUrl: String,
    val region: String? = null,
)

@Serializable
data class IdentifyProductRequestDto(
    @SerialName("raw_text") val rawText: String,
    @SerialName("input_mode") val inputMode: String = "text",
)

@Serializable
data class ProductIdentificationDto(
    @SerialName("product_name") val productName: String = "",
    @SerialName("product_use_category") val productUseCategory: String = "unknown",
    @SerialName("ingredient_text") val ingredientText: String = "",
    @SerialName("nutrition_text") val nutritionText: String = "",
    @SerialName("material_text") val materialText: String = "",
    @SerialName("packaging_material") val packagingMaterial: String = "",
    @SerialName("processing_method") val processingMethod: String = "",
    @SerialName("processing_derivatives") val processingDerivatives: String = "",
    @SerialName("concentration_assessment") val concentrationAssessment: String = "",
    @SerialName("warning_text") val warningText: String = "",
    @SerialName("safety_claims") val safetyClaims: String = "",
    @SerialName("confidence_notes") val confidenceNotes: String = "",
)

@Serializable
data class UrlContextDto(
    @SerialName("fetch_attempted") val fetchAttempted: Boolean = false,
    @SerialName("fetch_success") val fetchSuccess: Boolean = false,
    @SerialName("fetch_error") val fetchError: String? = null,
    @SerialName("product_text") val productText: String = "",
    @SerialName("ingredients_text") val ingredientsText: String = "",
    @SerialName("nutrition_text") val nutritionText: String = "",
    @SerialName("warning_text") val warningText: String = "",
)

@Serializable
data class PreviewUrlResponseDto(
    @SerialName("product_page_url") val productPageUrl: String? = null,
    val region: String? = null,
    @SerialName("url_context") val urlContext: UrlContextDto = UrlContextDto(),
    @SerialName("intake_assessment") val intakeAssessment: IntakeAssessmentDto = IntakeAssessmentDto(),
)

@Serializable
data class ProductMatchDto(
    @SerialName("product_type_id") val productTypeId: Int? = null,
    @SerialName("canonical_name") val canonicalName: String? = null,
    @SerialName("product_use_category") val productUseCategory: String? = null,
    @SerialName("material_subcategory") val materialSubcategory: String? = null,
    @SerialName("matched_text") val matchedText: String? = null,
    val score: Double? = null,
)

@Serializable
data class ChemicalMatchDto(
    @SerialName("chemical_id") val chemicalId: String? = null,
    @SerialName("preferred_name") val preferredName: String? = null,
    @SerialName("matched_text") val matchedText: String? = null,
    @SerialName("matched_term") val matchedTerm: String? = null,
    val score: Double? = null,
)

@Serializable
data class RegulatoryEvidenceDto(
    @SerialName("chemical_id") val chemicalId: String? = null,
    @SerialName("preferred_name") val preferredName: String? = null,
    @SerialName("source_authority") val sourceAuthority: String? = null,
    @SerialName("country_or_jurisdiction") val countryOrJurisdiction: String? = null,
    @SerialName("regulatory_status") val regulatoryStatus: String? = null,
    @SerialName("hazard_basis") val hazardBasis: String? = null,
    @SerialName("product_scope") val productScope: String? = null,
    @SerialName("threshold_value") val thresholdValue: String? = null,
    @SerialName("threshold_unit") val thresholdUnit: String? = null,
    @SerialName("citation_url") val citationUrl: String? = null,
)

@Serializable
data class WarningInterpretationDto(
    @SerialName("warning_type") val warningType: String? = null,
    @SerialName("signal_text") val signalText: String? = null,
    @SerialName("interpretation_summary") val interpretationSummary: String? = null,
)

@Serializable
data class LiteratureEvidenceDto(
    @SerialName("topic_name") val topicName: String? = null,
    @SerialName("chemical_id") val chemicalId: String? = null,
    @SerialName("evidence_type") val evidenceType: String? = null,
    @SerialName("evidence_strength") val evidenceStrength: String? = null,
    @SerialName("claim_summary") val claimSummary: String? = null,
    @SerialName("citation_url") val citationUrl: String? = null,
)

@Serializable
data class ControversyTopicDto(
    @SerialName("topic_name") val topicName: String? = null,
    @SerialName("topic_slug") val topicSlug: String? = null,
    @SerialName("regulatory_view") val regulatoryView: String? = null,
    @SerialName("literature_view") val literatureView: String? = null,
    @SerialName("consumer_takeaway") val consumerTakeaway: String? = null,
)

@Serializable
data class InferredCategoryDto(
    @SerialName("product_use_category") val productUseCategory: String = "unknown",
    @SerialName("material_subcategory") val materialSubcategory: String = "unknown",
)

@Serializable
data class ServingRecommendationDto(
    @SerialName("product_use_category") val productUseCategory: String? = null,
    @SerialName("material_subcategory") val materialSubcategory: String? = null,
    @SerialName("top_chemical_families") val topChemicalFamilies: String? = null,
    @SerialName("top_chemicals") val topChemicals: String? = null,
    @SerialName("recommendation_priority") val recommendationPriority: String? = null,
    @SerialName("recommended_caution_text") val recommendedCautionText: String? = null,
    @SerialName("why_this_matters") val whyThisMatters: String? = null,
)

@Serializable
data class RecommendationDto(
    @SerialName("recommendation_bucket") val recommendationBucket: String = "insufficient_info",
    @SerialName("recommendation_reason") val recommendationReason: String = "",
)

@Serializable
data class ConcernSourceDto(
    @SerialName("source_authority") val sourceAuthority: String? = null,
    @SerialName("country_or_jurisdiction") val countryOrJurisdiction: String? = null,
    @SerialName("regulatory_status") val regulatoryStatus: String? = null,
    val count: Int? = null,
)

@Serializable
data class EvidenceScopeSummaryDto(
    @SerialName("has_direct_chemical_match") val hasDirectChemicalMatch: Boolean = false,
    @SerialName("direct_chemical_match_count") val directChemicalMatchCount: Int = 0,
    @SerialName("has_warning_text_signal") val hasWarningTextSignal: Boolean = false,
    @SerialName("has_category_level_signal_only") val hasCategoryLevelSignalOnly: Boolean = false,
)

@Serializable
data class IntakeAssessmentDto(
    @SerialName("can_proceed") val canProceed: Boolean = true,
    val status: String = "sufficient",
    @SerialName("recommended_next_step") val recommendedNextStep: String = "continue",
    val reason: String = "",
)

@Serializable
data class UserOverlapSummaryDto(
    @SerialName("chemical_id") val chemicalId: String? = null,
    @SerialName("preferred_name") val preferredName: String? = null,
    @SerialName("product_count") val productCount: Int? = null,
)

@Serializable
data class HazardlyFlagDto(
    val label: String = "",
    val type: String = "",
    val severity: String = "",
    val confidence: String = "",
    @SerialName("evidence_source") val evidenceSource: String = "",
    @SerialName("route_relevance") val routeRelevance: String = "",
    @SerialName("exposure_likelihood") val exposureLikelihood: String = "",
    @SerialName("population_factor") val populationFactor: String = "",
    @SerialName("score_impact") val scoreImpact: String = "none",
    @SerialName("risk_points") val riskPoints: Double = 0.0,
    val reason: String = "",
)

@Serializable
data class HazardlyScoreDto(
    val score: String = "A",
    val title: String = "Hazardly Score",
    val description: String = "",
    @SerialName("risk_signals") val riskSignals: List<String> = emptyList(),
    @SerialName("is_food") val isFood: Boolean = false,
    @SerialName("nutrition_flags") val nutritionFlags: List<String> = emptyList(),
    val flags: List<HazardlyFlagDto> = emptyList(),
    @SerialName("total_risk_points") val totalRiskPoints: Double = 0.0,
)

@Serializable
data class ProductRiskSourceDto(
    val source: String = "",
    @SerialName("is_listed_or_warned") val isListedOrWarned: Boolean = false,
    @SerialName("risk_reason") val riskReason: String = "",
    @SerialName("source_summary") val sourceSummary: String = "",
    @SerialName("citation_url") val citationUrl: String = "",
)

@Serializable
data class IdentifiedRiskDto(
    @SerialName("chemical_name") val chemicalName: String = "",
    @SerialName("identification_method") val identificationMethod: String = "",
    @SerialName("detection_basis") val detectionBasis: String = "",
    @SerialName("evidence_from_product") val evidenceFromProduct: String = "",
    @SerialName("dose_context") val doseContext: String = "",
    @SerialName("risk_sources") val riskSources: List<ProductRiskSourceDto> = emptyList(),
    @SerialName("consumer_explanation") val consumerExplanation: String = "",
    @SerialName("caution_level") val cautionLevel: String = "",
    @SerialName("user_recommendation") val userRecommendation: String = "",
    val confidence: String = "",
    @SerialName("confidence_level") val confidenceLevel: String = "",
    @SerialName("evidence_source") val evidenceSource: String = "",
    @SerialName("route_relevance") val routeRelevance: String = "",
    @SerialName("exposure_likelihood") val exposureLikelihood: String = "",
    @SerialName("population_factor") val populationFactor: String = "",
    @SerialName("risk_points") val riskPoints: Double = 0.0,
    val meaning: String = "",
)

@Serializable
data class ProductRiskSummaryDto(
    @SerialName("product_name") val productName: String = "",
    @SerialName("product_category") val productCategory: String = "",
    @SerialName("ingredient_material_status") val ingredientMaterialStatus: String = "",
    @SerialName("overall_recommendation") val overallRecommendation: String = "",
    @SerialName("is_food") val isFood: Boolean = false,
    @SerialName("use_guidance") val useGuidance: List<String> = emptyList(),
)

@Serializable
data class StructuredRiskOutputDto(
    @SerialName("product_summary") val productSummary: ProductRiskSummaryDto = ProductRiskSummaryDto(),
    @SerialName("identified_risks") val identifiedRisks: List<IdentifiedRiskDto> = emptyList(),
    @SerialName("final_consumer_guidance") val finalConsumerGuidance: String = "",
    val disclaimer: String = "",
)

@Serializable
data class AnalyzeProductResponseDto(
    @SerialName("product_matches") val productMatches: List<ProductMatchDto> = emptyList(),
    @SerialName("chemical_matches") val chemicalMatches: List<ChemicalMatchDto> = emptyList(),
    @SerialName("regulatory_evidence") val regulatoryEvidence: List<RegulatoryEvidenceDto> = emptyList(),
    @SerialName("warning_interpretations") val warningInterpretations: List<WarningInterpretationDto> = emptyList(),
    @SerialName("literature_evidence") val literatureEvidence: List<LiteratureEvidenceDto> = emptyList(),
    @SerialName("controversy_topics") val controversyTopics: List<ControversyTopicDto> = emptyList(),
    @SerialName("product_page_url") val productPageUrl: String? = null,
    @SerialName("url_context") val urlContext: UrlContextDto = UrlContextDto(),
    @SerialName("inferred_category") val inferredCategory: InferredCategoryDto = InferredCategoryDto(),
    @SerialName("serving_recommendation") val servingRecommendation: ServingRecommendationDto? = null,
    val recommendation: RecommendationDto = RecommendationDto(),
    @SerialName("concern_sources") val concernSources: List<ConcernSourceDto> = emptyList(),
    @SerialName("evidence_scope_summary") val evidenceScopeSummary: EvidenceScopeSummaryDto = EvidenceScopeSummaryDto(),
    @SerialName("user_overlap_summary") val userOverlapSummary: List<UserOverlapSummaryDto> = emptyList(),
    @SerialName("hazardly_score") val hazardlyScore: HazardlyScoreDto? = null,
    @SerialName("structured_risk_output") val structuredRiskOutput: StructuredRiskOutputDto = StructuredRiskOutputDto(),
    @SerialName("intake_assessment") val intakeAssessment: IntakeAssessmentDto = IntakeAssessmentDto(),
    @SerialName("review_reasons") val reviewReasons: List<String> = emptyList(),
    @SerialName("saved_user_product_id") val savedUserProductId: Int? = null,
    @SerialName("review_queue_id") val reviewQueueId: Int? = null,
    @SerialName("user_feedback_id") val userFeedbackId: Int? = null,
)

@Serializable
data class HealthResponseDto(
    val status: String = "ok",
)

@Serializable
data class ReviewQueueItemDto(
    @SerialName("review_id") val reviewId: Int,
    @SerialName("source_flow") val sourceFlow: String? = null,
    @SerialName("user_id") val userId: String? = null,
    @SerialName("session_id") val sessionId: String? = null,
    @SerialName("input_mode") val inputMode: String? = null,
    @SerialName("product_name") val productName: String? = null,
    @SerialName("product_page_url") val productPageUrl: String? = null,
    @SerialName("region_label") val regionLabel: String? = null,
    @SerialName("raw_ocr_text") val rawOcrText: String? = null,
    @SerialName("extracted_ingredient_text") val extractedIngredientText: String? = null,
    @SerialName("extracted_warning_text") val extractedWarningText: String? = null,
    @SerialName("inferred_product_use_category") val inferredProductUseCategory: String? = null,
    @SerialName("inferred_material_subcategory") val inferredMaterialSubcategory: String? = null,
    @SerialName("recommendation_bucket") val recommendationBucket: String? = null,
    @SerialName("review_reasons") val reviewReasons: List<String> = emptyList(),
    @SerialName("review_notes") val reviewNotes: String? = null,
    @SerialName("status") val status: String? = null,
    @SerialName("priority") val priority: String? = null,
    @SerialName("review_payload") val reviewPayload: JsonElement? = null,
)

@Serializable
data class CuratedCorrectionRequestDto(
    @SerialName("correction_type") val correctionType: String,
    @SerialName("original_value") val originalValue: String? = null,
    @SerialName("corrected_value") val correctedValue: String,
    @SerialName("reviewer_notes") val reviewerNotes: String? = null,
    val approved: Boolean = false,
)
