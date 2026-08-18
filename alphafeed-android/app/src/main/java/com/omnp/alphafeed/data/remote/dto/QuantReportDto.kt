package com.omnp.alphafeed.data.remote.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class QuantReportDto(
    val generatedAt: String? = null,
    val opportunities: List<OpportunityDto> = emptyList()
)

@Serializable
data class OpportunityDto(
    val title: String? = null,
    val slug: String? = null,
    val url: String? = null,
    val curPrice: Double? = null,
    val expectedValue: Double? = null,
    val winProbEst: Double? = null,
    val qSource: String? = null,
    val betEligible: Boolean? = null,
    val kellyBet: Double? = null,
    val betDirection: String? = null,
    val category: String? = null,
    @SerialName("days_left") val daysLeft: Double? = null,
    val estimatedEdge: Double? = null,
    val countSignal: Double? = null,
    val nSmartTraders: Int? = null,
    val totalTradersChecked: Int? = null,
    val smartTraderNames: List<String>? = null
)
