package com.omnp.alphafeed.domain

import com.omnp.alphafeed.domain.model.Bet

sealed interface Row {
    data class BetRow(val bet: Bet) : Row
    data object AdRow : Row
    data class LockedRow(val remaining: Int) : Row
}

object BoardGating {
    private const val FREE_VISIBLE_COUNT = 3

    fun rows(board: List<Bet>, isPro: Boolean): List<Row> {
        if (isPro) {
            return board.map { Row.BetRow(it) }
        }
        val visible = board.take(FREE_VISIBLE_COUNT).map { Row.BetRow(it) }
        val remaining = board.size - FREE_VISIBLE_COUNT
        return visible + Row.AdRow + Row.LockedRow(remaining)
    }
}
