package com.omnp.alphafeed.data.billing

import android.app.Activity
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class PurchaseInfo(
    val productId: String,
    val isActive: Boolean,
    val acknowledged: Boolean
)

interface BillingGateway {
    suspend fun queryPurchases(): List<PurchaseInfo>
}

class BillingRepository(private val gateway: BillingGateway) {
    private val _isPro = MutableStateFlow(false)
    val isPro: StateFlow<Boolean> = _isPro.asStateFlow()

    suspend fun refresh() {
        _isPro.value = gateway.queryPurchases().any { it.productId == "pro_monthly" && it.isActive }
    }

    /**
     * Launches the real Play purchase flow (when the gateway supports it) and refreshes
     * entitlement afterwards. No-ops the purchase step for gateways that don't implement it
     * (e.g. test fakes), but still refreshes.
     */
    suspend fun purchasePro(activity: Activity) {
        (gateway as? PlayBillingGateway)?.launchPurchase(activity)
        refresh()
    }
}
