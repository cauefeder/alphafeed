package com.omnp.alphafeed

import com.omnp.alphafeed.data.remote.dto.OpportunityDto
import com.omnp.alphafeed.domain.model.Confidence
import com.omnp.alphafeed.domain.model.toBet
import org.junit.Assert.*
import org.junit.Test

class BetMapperTest {
    @Test fun maps_dto_to_display_bet() {
        val bet = OpportunityDto(title="Red Sox −1.5", curPrice=0.30, expectedValue=0.47,
                winProbEst=0.53, category="sports", daysLeft=0.5, betEligible=true,
                slug="mlb-bos-nyy-2026-08-07-spread-home-1pt5", url="x").toBet()
        assertEquals("Red Sox −1.5", bet.market)
        assertEquals(47, bet.evPercent)
        assertEquals(53, bet.winPercent)
        assertEquals(30, bet.priceCents)
        assertEquals(Confidence.STRONG, bet.confidence)   // ev>=0.40 STRONG else VALUE
        assertEquals("MLB", bet.leagueLabel)              // slug prefix -> league; else "SPORTS"
    }

    @Test fun value_confidence_below_threshold() {
        val b = OpportunityDto(title="x", curPrice=0.4, expectedValue=0.10, winProbEst=0.5, slug="nba-a-b").toBet()
        assertEquals(Confidence.VALUE, b.confidence)
        assertEquals("NBA", b.leagueLabel)
    }
}
