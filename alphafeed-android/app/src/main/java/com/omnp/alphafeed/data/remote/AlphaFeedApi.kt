package com.omnp.alphafeed.data.remote

import com.omnp.alphafeed.data.remote.dto.QuantReportDto
import retrofit2.http.GET

interface AlphaFeedApi {
    @GET("api/quant-report")
    suspend fun quantReport(): QuantReportDto
}
