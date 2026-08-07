package com.omnp.alphafeed

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.google.android.gms.ads.MobileAds
import com.google.android.ump.ConsentRequestParameters
import com.google.android.ump.UserMessagingPlatform
import com.omnp.alphafeed.ui.bets.BetsViewModel
import com.omnp.alphafeed.ui.nav.AlphaFeedNav
import com.omnp.alphafeed.ui.theme.AlphaFeedTheme
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private val container by lazy { (application as AlphaFeedApp).container }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        initMobileAds()
        requestConsentIfNeeded()

        // Warm up billing on start so entitlement is fresh by the time Compose collects it.
        lifecycleScope.launch {
            container.billingGateway.connect()
            container.billingRepository.refresh()
        }

        setContent {
            AlphaFeedTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    val isPro by container.billingRepository.isPro.collectAsStateWithLifecycle()
                    val betsViewModel: BetsViewModel = viewModel(
                        factory = viewModelFactory {
                            initializer {
                                BetsViewModel(
                                    loader = container.betsRepository::load,
                                    isProFlow = container.billingRepository.isPro
                                )
                            }
                        }
                    )
                    val betsState by betsViewModel.state.collectAsStateWithLifecycle()

                    AlphaFeedNav(
                        betsState = betsState,
                        isPro = isPro,
                        onRetryBets = betsViewModel::retry,
                        onSubscribe = {
                            lifecycleScope.launch {
                                container.billingRepository.purchasePro(this@MainActivity)
                            }
                        }
                    )
                }
            }
        }
    }

    private fun initMobileAds() {
        MobileAds.initialize(this)
    }

    /**
     * Minimal UMP consent request. Wrapped defensively: a failure here (no network, SDK
     * hiccup, etc.) must never block app startup — ads simply fall back to non-personalized.
     */
    private fun requestConsentIfNeeded() {
        try {
            val consentInformation = UserMessagingPlatform.getConsentInformation(this)
            val params = ConsentRequestParameters.Builder().build()
            consentInformation.requestConsentInfoUpdate(
                this,
                params,
                {
                    if (consentInformation.isConsentFormAvailable) {
                        UserMessagingPlatform.loadAndShowConsentFormIfRequired(this) { }
                    }
                },
                { }
            )
        } catch (e: Exception) {
            // Best-effort only; never crash startup over consent plumbing.
        }
    }
}
