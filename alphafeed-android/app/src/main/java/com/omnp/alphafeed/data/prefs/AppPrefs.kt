package com.omnp.alphafeed.data.prefs

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "alphafeed_prefs")

/** Small DataStore wrapper for the handful of local flags the app needs to persist. */
class AppPrefs(private val context: Context) {
    private object Keys {
        val SEEN_ONBOARDING = booleanPreferencesKey("seen_onboarding")
    }

    val seenOnboarding: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[Keys.SEEN_ONBOARDING] ?: false
    }

    suspend fun setSeenOnboarding(seen: Boolean) {
        context.dataStore.edit { prefs -> prefs[Keys.SEEN_ONBOARDING] = seen }
    }
}
