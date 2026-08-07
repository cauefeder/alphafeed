package com.omnp.alphafeed

import com.omnp.alphafeed.domain.EdgeCalc
import org.junit.Assert.*
import org.junit.Test

class EdgeCalcTest {
    @Test fun edge_is_model_win_minus_market_price() {
        val e = EdgeCalc.of(winProb = 0.53, price = 0.33)
        assertEquals(53, e.modelWinPct); assertEquals(33, e.marketPct)
        assertEquals(20, e.gapPct)
        assertEquals(3.0, e.payoutX, 0.05)
        assertEquals(53, e.fairValueCents)   // round(winProb*100)
    }

    @Test fun zero_price_safe() { assertEquals(0.0, EdgeCalc.of(0.5, 0.0).payoutX, 1e-9) }
}
