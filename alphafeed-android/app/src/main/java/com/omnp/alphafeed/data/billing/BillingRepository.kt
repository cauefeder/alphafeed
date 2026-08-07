package com.omnp.alphafeed.data.billing

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
}
