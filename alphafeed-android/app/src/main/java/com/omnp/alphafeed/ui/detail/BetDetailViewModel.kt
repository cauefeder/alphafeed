package com.omnp.alphafeed.ui.detail

import androidx.lifecycle.ViewModel
import com.omnp.alphafeed.domain.EdgeCalc
import com.omnp.alphafeed.domain.model.Bet

data class DetailUi(
    val bet: Bet,
    val edge: EdgeCalc.Edge,
    val reasons: List<String>,
    val disclaimer: String
)

private const val DISCLAIMER = "Informational analytics only — not betting or financial advice. " +
    "AlphaFeed does not accept or place wagers. 18+."

/**
 * Builds the bet-detail UI model: the model/market edge plus a plain-English list of
 * "why this pick" reasons derived from the inputs.
 */
class BetDetailViewModel(
    bet: Bet,
    winProb: Double,
    smartCount: Int,
    smartTotal: Int,
    isPointMarket: Boolean,
    sameDay: Boolean
) : ViewModel() {

    val ui: DetailUi

    init {
        val edge = EdgeCalc.of(winProb, bet.priceCents / 100.0)
        val reasons = buildList {
            if (smartCount > 0) {
                add("$smartCount of $smartTotal tracked smart-money traders are on this side")
            }
            if (isPointMarket) {
                add("Spread/total market — historically stronger hit rate")
            }
            if (sameDay) {
                add("Same-day game (most stable signal)")
            }
            add("Priced below model fair value (~${edge.fairValueCents}¢)")
        }
        ui = DetailUi(
            bet = bet,
            edge = edge,
            reasons = reasons,
            disclaimer = DISCLAIMER
        )
    }
}
