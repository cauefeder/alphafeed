package com.omnp.alphafeed.domain.model

import com.omnp.alphafeed.data.remote.dto.OpportunityDto

enum class Confidence { STRONG, VALUE }

data class Bet(
    val id: String,
    val market: String,
    val evPercent: Int,
    val winPercent: Int,
    val priceCents: Int,
    val confidence: Confidence,
    val leagueLabel: String,
    val url: String?,
    val payoutX: Double
)

private val KNOWN_LEAGUES = setOf(
    "mlb", "nba", "nhl", "nfl", "ncaa", "epl", "uel", "ucl", "wta", "atp", "mls", "kbo", "fifwc"
)

fun OpportunityDto.toBet(): Bet {
    val price = curPrice ?: 0.0
    val ev = expectedValue ?: 0.0
    val win = winProbEst ?: 0.0
    val prefix = slug?.substringBefore('-')?.lowercase()
    val leagueLabel = if (prefix != null && prefix in KNOWN_LEAGUES) prefix.uppercase() else "SPORTS"
    return Bet(
        id = slug ?: title ?: "",
        market = title ?: "",
        evPercent = Math.round(ev * 100).toInt(),
        winPercent = Math.round(win * 100).toInt(),
        priceCents = Math.round(price * 100).toInt(),
        confidence = if (ev >= 0.40) Confidence.STRONG else Confidence.VALUE,
        leagueLabel = leagueLabel,
        url = url,
        payoutX = if (price > 0) 1.0 / price else 0.0
    )
}
