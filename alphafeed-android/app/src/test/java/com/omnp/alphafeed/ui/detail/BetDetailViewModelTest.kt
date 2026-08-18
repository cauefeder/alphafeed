package com.omnp.alphafeed.ui.detail

import com.omnp.alphafeed.domain.model.Bet
import com.omnp.alphafeed.domain.model.Confidence
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BetDetailViewModelTest {
    @Test
    fun builds_edge_and_reasons() {
        val bet = Bet("id", "Red Sox −1.5", 47, 53, 33, Confidence.STRONG, "MLB", null, 3.0)
        val ui = BetDetailViewModel(
            bet = bet,
            winProb = 0.53,
            smartCount = 4,
            smartTotal = 5,
            isPointMarket = true,
            sameDay = true
        ).ui
        assertEquals(20, ui.edge.gapPct)
        assertTrue(ui.reasons.isNotEmpty())
        assertTrue(ui.reasons.any { it.contains("4 of 5") })
        assertTrue(ui.disclaimer.isNotBlank())
    }
}
