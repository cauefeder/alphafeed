package com.omnp.alphafeed.data.cache

import androidx.room.Entity
import androidx.room.PrimaryKey
import com.omnp.alphafeed.domain.model.Bet
import com.omnp.alphafeed.domain.model.Confidence

@Entity(tableName = "bets")
data class BetEntity(
    @PrimaryKey val id: String,
    val market: String,
    val evPercent: Int,
    val winPercent: Int,
    val priceCents: Int,
    val confidence: String,
    val leagueLabel: String,
    val url: String?,
    val payoutX: Double
)

fun BetEntity.toBet(): Bet = Bet(
    id = id,
    market = market,
    evPercent = evPercent,
    winPercent = winPercent,
    priceCents = priceCents,
    confidence = Confidence.valueOf(confidence),
    leagueLabel = leagueLabel,
    url = url,
    payoutX = payoutX
)

fun Bet.toEntity(): BetEntity = BetEntity(
    id = id,
    market = market,
    evPercent = evPercent,
    winPercent = winPercent,
    priceCents = priceCents,
    confidence = confidence.name,
    leagueLabel = leagueLabel,
    url = url,
    payoutX = payoutX
)
