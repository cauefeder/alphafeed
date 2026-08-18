package com.omnp.alphafeed

import com.omnp.alphafeed.data.billing.BillingGateway
import com.omnp.alphafeed.data.billing.BillingRepository
import com.omnp.alphafeed.data.billing.PurchaseInfo
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test

class BillingRepositoryTest {
    private class FakeGateway(val purchases: List<PurchaseInfo>) : BillingGateway {
        override suspend fun queryPurchases() = purchases
    }

    @Test fun isPro_true_with_active_sub() = runTest {
        val repo = BillingRepository(FakeGateway(listOf(PurchaseInfo("pro_monthly", true, true))))
        repo.refresh()
        assertTrue(repo.isPro.value)
    }

    @Test fun isPro_false_without() = runTest {
        val repo = BillingRepository(FakeGateway(emptyList()))
        repo.refresh()
        assertFalse(repo.isPro.value)
    }
}
