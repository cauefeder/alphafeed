package com.omnp.alphafeed.data.billing

import android.app.Activity
import android.content.Context
import com.android.billingclient.api.AcknowledgePurchaseParams
import com.android.billingclient.api.BillingClient
import com.android.billingclient.api.BillingClientStateListener
import com.android.billingclient.api.BillingFlowParams
import com.android.billingclient.api.BillingResult
import com.android.billingclient.api.PendingPurchasesParams
import com.android.billingclient.api.Purchase
import com.android.billingclient.api.PurchasesUpdatedListener
import com.android.billingclient.api.QueryProductDetailsParams
import com.android.billingclient.api.QueryPurchasesParams
import com.android.billingclient.api.acknowledgePurchase
import com.android.billingclient.api.queryProductDetails
import com.android.billingclient.api.queryPurchasesAsync
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine

private const val PRO_MONTHLY_PRODUCT_ID = "pro_monthly"

/**
 * [BillingGateway] backed by the real Google Play Billing Library (billing-ktx 7.0).
 * Kept intentionally minimal: a single subscription product, best-effort acknowledgement,
 * and a simple connect-then-call flow rather than a full retry/backoff strategy.
 */
class PlayBillingGateway(context: Context) : BillingGateway {

    private val purchasesUpdatedListener = PurchasesUpdatedListener { billingResult, purchases ->
        if (billingResult.responseCode == BillingClient.BillingResponseCode.OK && purchases != null) {
            purchases.forEach { purchase ->
                if (purchase.purchaseState == Purchase.PurchaseState.PURCHASED && !purchase.isAcknowledged) {
                    CoroutineScope(Dispatchers.IO).launch { acknowledge(purchase.purchaseToken) }
                }
            }
        }
    }

    private val billingClient: BillingClient = BillingClient.newBuilder(context.applicationContext)
        .setListener(purchasesUpdatedListener)
        .enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())
        .build()

    /** Starts the connection if needed; safe to call repeatedly. */
    suspend fun connect() {
        if (billingClient.isReady) return
        suspendCancellableCoroutine<Unit> { cont ->
            billingClient.startConnection(object : BillingClientStateListener {
                override fun onBillingSetupFinished(billingResult: BillingResult) {
                    if (cont.isActive) cont.resumeWith(Result.success(Unit))
                }

                override fun onBillingServiceDisconnected() {
                    // No-op: the next connect()/queryPurchases() call will retry.
                }
            })
        }
    }

    override suspend fun queryPurchases(): List<PurchaseInfo> {
        if (!billingClient.isReady) connect()
        val params = QueryPurchasesParams.newBuilder()
            .setProductType(BillingClient.ProductType.SUBS)
            .build()
        val result = billingClient.queryPurchasesAsync(params)
        return result.purchasesList.map { purchase ->
            PurchaseInfo(
                productId = purchase.products.firstOrNull().orEmpty(),
                isActive = purchase.purchaseState == Purchase.PurchaseState.PURCHASED,
                acknowledged = purchase.isAcknowledged
            )
        }
    }

    /** Queries the pro subscription's product details and launches the Play purchase flow. */
    suspend fun launchPurchase(activity: Activity) {
        if (!billingClient.isReady) connect()
        val productList = listOf(
            QueryProductDetailsParams.Product.newBuilder()
                .setProductId(PRO_MONTHLY_PRODUCT_ID)
                .setProductType(BillingClient.ProductType.SUBS)
                .build()
        )
        val queryParams = QueryProductDetailsParams.newBuilder()
            .setProductList(productList)
            .build()
        val result = billingClient.queryProductDetails(queryParams)
        val productDetails = result.productDetailsList?.firstOrNull() ?: return
        val offerToken = productDetails.subscriptionOfferDetails?.firstOrNull()?.offerToken ?: return
        val flowParams = BillingFlowParams.newBuilder()
            .setProductDetailsParamsList(
                listOf(
                    BillingFlowParams.ProductDetailsParams.newBuilder()
                        .setProductDetails(productDetails)
                        .setOfferToken(offerToken)
                        .build()
                )
            )
            .build()
        billingClient.launchBillingFlow(activity, flowParams)
    }

    /** Best-effort acknowledgement; failures don't propagate since entitlement is re-derived on refresh. */
    suspend fun acknowledge(purchaseToken: String) {
        try {
            val params = AcknowledgePurchaseParams.newBuilder()
                .setPurchaseToken(purchaseToken)
                .build()
            billingClient.acknowledgePurchase(params)
        } catch (e: Exception) {
            // Ignored: BillingRepository.refresh() will reflect the true entitlement next time.
        }
    }
}
