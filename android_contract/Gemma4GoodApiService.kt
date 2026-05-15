package good.gemma4good.contract

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface Gemma4GoodApiService {
    @GET("health")
    suspend fun getHealth(): HealthResponseDto

    @POST("analyze-product")
    suspend fun analyzeProduct(
        @Body request: AnalyzeProductRequestDto,
    ): AnalyzeProductResponseDto

    @POST("preview-url")
    suspend fun previewUrl(
        @Body request: PreviewUrlRequestDto,
    ): PreviewUrlResponseDto

    @POST("identify-product")
    suspend fun identifyProduct(
        @Body request: IdentifyProductRequestDto,
    ): ProductIdentificationDto

    @GET("users/{userId}/products")
    suspend fun listUserProducts(
        @Path("userId") userId: String,
    ): List<Map<String, kotlinx.serialization.json.JsonElement>>

    @GET("users/{userId}/chemicals")
    suspend fun listUserChemicals(
        @Path("userId") userId: String,
    ): List<UserOverlapSummaryDto>

    @GET("review-queue")
    suspend fun listReviewQueue(
        @Query("limit") limit: Int = 50,
    ): List<ReviewQueueItemDto>

    @POST("review-queue/{reviewId}/corrections")
    suspend fun submitCorrection(
        @Path("reviewId") reviewId: Int,
        @Body request: CuratedCorrectionRequestDto,
    ): Map<String, kotlinx.serialization.json.JsonElement>
}
