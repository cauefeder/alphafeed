package com.omnp.alphafeed.data

import com.omnp.alphafeed.domain.model.Bet

data class BoardResult(
    val bets: List<Bet>,
    val isOffline: Boolean,
    val updatedAt: String?
)
