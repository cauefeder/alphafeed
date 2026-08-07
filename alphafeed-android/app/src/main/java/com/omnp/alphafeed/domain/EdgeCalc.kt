package com.omnp.alphafeed.domain

object EdgeCalc {
    data class Edge(
        val modelWinPct: Int,
        val marketPct: Int,
        val gapPct: Int,
        val payoutX: Double,
        val fairValueCents: Int
    )

    fun of(winProb: Double, price: Double): Edge {
        val modelWinPct = Math.round(winProb * 100).toInt()
        val marketPct = Math.round(price * 100).toInt()
        return Edge(
            modelWinPct = modelWinPct,
            marketPct = marketPct,
            gapPct = modelWinPct - marketPct,
            payoutX = if (price > 0) 1.0 / price else 0.0,
            fairValueCents = Math.round(winProb * 100).toInt()
        )
    }
}
