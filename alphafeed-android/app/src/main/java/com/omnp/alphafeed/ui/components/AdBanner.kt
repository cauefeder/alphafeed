package com.omnp.alphafeed.ui.components

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView
import com.google.android.gms.ads.AdRequest
import com.google.android.gms.ads.AdSize
import com.google.android.gms.ads.AdView

/** Google's public AdMob test unit ID — safe to ship, never serves real ads. */
private const val BANNER_TEST_AD_UNIT_ID = "ca-app-pub-3940256099942544/6300978111"

/**
 * Real AdMob banner slot shown in place of [AdRowPlaceholder] for free-tier users.
 * Uses the AdMob test unit ID; swap for a production unit ID before release.
 */
@Composable
fun AdBanner(modifier: Modifier = Modifier) {
    AndroidView(
        modifier = modifier.fillMaxWidth(),
        factory = { context ->
            AdView(context).apply {
                setAdSize(AdSize.BANNER)
                adUnitId = BANNER_TEST_AD_UNIT_ID
                loadAd(AdRequest.Builder().build())
            }
        }
    )
}
