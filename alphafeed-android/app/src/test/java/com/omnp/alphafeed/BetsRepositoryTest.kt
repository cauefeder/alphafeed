package com.omnp.alphafeed

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.omnp.alphafeed.data.BetsRepository
import com.omnp.alphafeed.data.cache.AppDatabase
import com.omnp.alphafeed.data.cache.BetEntity
import com.omnp.alphafeed.data.remote.AlphaFeedApi
import com.omnp.alphafeed.data.remote.dto.OpportunityDto
import com.omnp.alphafeed.data.remote.dto.QuantReportDto
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class BetsRepositoryTest {
    private lateinit var db: AppDatabase

    @Before fun s() {
        db = Room.inMemoryDatabaseBuilder(ApplicationProvider.getApplicationContext(), AppDatabase::class.java).allowMainThreadQueries().build()
    }

    @After fun t() {
        db.close()
    }

    private fun dto(id: String, ev: Double = 0.4, elig: Boolean = true) =
        OpportunityDto(title = id, slug = id, curPrice = 0.3, expectedValue = ev, winProbEst = 0.5, category = "sports", betEligible = elig)

    @Test fun network_success_caches_eligible_sorted() = runTest {
        val api = object : AlphaFeedApi {
            override suspend fun quantReport() = QuantReportDto(opportunities = listOf(dto("a", 0.2), dto("b", 0.5), dto("c", 0.3, elig = false)))
        }
        val res = BetsRepository(api, db.betDao()).load()
        assertFalse(res.isOffline)
        assertEquals(listOf("b", "a"), res.bets.map { it.id })
    }

    @Test fun network_error_falls_back_to_cache_offline() = runTest {
        db.betDao().replaceAll(listOf(BetEntity("cached", "m", 40, 50, 30, "VALUE", "MLB", null, 3.0)))
        val api = object : AlphaFeedApi {
            override suspend fun quantReport(): QuantReportDto = throw java.io.IOException()
        }
        val res = BetsRepository(api, db.betDao()).load()
        assertTrue(res.isOffline)
        assertEquals(listOf("cached"), res.bets.map { it.id })
    }
}
