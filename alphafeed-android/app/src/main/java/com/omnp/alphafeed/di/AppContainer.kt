package com.omnp.alphafeed.di

import android.content.Context
import androidx.room.Room
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

private const val BASE_URL = "https://alphafeed-api.onrender.com/"

/**
 * Manual dependency container built once from the [Application] [Context]. No DI framework —
 * just plain constructor wiring, kept small enough to hand-audit.
 */
class AppContainer(context: Context) {
    private val appContext = context.applicationContext

    private val json = Json { ignoreUnknownKeys = true }

    private val okHttpClient = OkHttpClient.Builder().build()

    private val retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()

    val api: AlphaFeedApi = retrofit.create(AlphaFeedApi::class.java)

    val db: AppDatabase = Room.databaseBuilder(appContext, AppDatabase::class.java, "alphafeed.db").build()

    val betsRepository = BetsRepository(api, db.betDao())

    val billingGateway = PlayBillingGateway(appContext)

    val billingRepository = BillingRepository(billingGateway)

    val appPrefs = AppPrefs(appContext)
}
