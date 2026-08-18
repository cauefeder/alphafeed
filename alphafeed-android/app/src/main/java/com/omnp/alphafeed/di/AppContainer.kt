package com.omnp.alphafeed.di

import android.content.Context
import androidx.room.Room
import com.omnp.alphafeed.BuildConfig
import com.omnp.alphafeed.data.BetsRepository
import com.omnp.alphafeed.data.billing.BillingRepository
import com.omnp.alphafeed.data.billing.PlayBillingGateway
import com.omnp.alphafeed.data.cache.AppDatabase
import com.omnp.alphafeed.data.prefs.AppPrefs
import com.omnp.alphafeed.data.remote.AlphaFeedApi
import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit

private const val BASE_URL = "https://alphafeed-api.onrender.com/"

/**
 * Manual dependency container built once from the [Application] [Context]. No DI framework —
 * just plain constructor wiring, kept small enough to hand-audit.
 */
class AppContainer(context: Context) {
    private val appContext = context.applicationContext

    private val json = Json { ignoreUnknownKeys = true }

    // Generous timeouts: the Render free-tier backend spins down when idle and its
    // cold start can take ~30-50s. With the default 10s timeout the first request
    // after the server sleeps times out and the app shows "offline". 60s read/call
    // lets the cold start finish and the board load.
    private val okHttpClient = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .callTimeout(70, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    private val retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()

    val api: AlphaFeedApi = retrofit.create(AlphaFeedApi::class.java)

    val db: AppDatabase = Room.databaseBuilder(appContext, AppDatabase::class.java, "alphafeed.db").build()

    val betsRepository = BetsRepository(api, db.betDao())

    val billingGateway = PlayBillingGateway(appContext)

    val billingRepository = BillingRepository(billingGateway, forcePro = BuildConfig.FORCE_PRO)

    val appPrefs = AppPrefs(appContext)
}
