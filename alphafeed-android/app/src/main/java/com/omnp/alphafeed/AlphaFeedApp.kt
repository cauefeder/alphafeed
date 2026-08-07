package com.omnp.alphafeed

import android.app.Application
import com.omnp.alphafeed.di.AppContainer

class AlphaFeedApp : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
    }
}
