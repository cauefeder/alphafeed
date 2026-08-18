package com.omnp.alphafeed

import com.omnp.alphafeed.domain.BoardGating
import com.omnp.alphafeed.domain.Row
import com.omnp.alphafeed.domain.model.Bet
import com.omnp.alphafeed.domain.model.Confidence
import org.junit.Assert.*
import org.junit.Test

class BoardGatingTest {
    private fun fakeBet(id: String = "x", ev: Int = 40) =
        Bet(id, "m", ev, 50, 30, Confidence.VALUE, "MLB", null, 3.0)

    @Test fun free_shows_top_three_then_locked() {
        val board = (1..8).map { fakeBet(id = "b$it", ev = 50 - it) }
        val rows = BoardGating.rows(board, isPro = false)
        assertEquals(3, rows.count { it is Row.BetRow })
        assertTrue(rows.any { it is Row.LockedRow && (it as Row.LockedRow).remaining == 5 })
        assertTrue(rows.any { it is Row.AdRow })
    }

    @Test fun pro_shows_all_no_lock_no_ads() {
        val rows = BoardGating.rows((1..8).map { fakeBet(id = "b$it") }, isPro = true)
        assertEquals(8, rows.count { it is Row.BetRow })
        assertTrue(rows.none { it is Row.LockedRow }); assertTrue(rows.none { it is Row.AdRow })
    }
}
