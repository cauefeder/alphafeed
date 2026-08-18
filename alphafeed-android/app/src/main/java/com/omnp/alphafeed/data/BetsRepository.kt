package com.omnp.alphafeed.data

import com.omnp.alphafeed.data.cache.BetDao
import com.omnp.alphafeed.data.cache.toBet
import com.omnp.alphafeed.data.cache.toEntity
import com.omnp.alphafeed.data.remote.AlphaFeedApi
import com.omnp.alphafeed.domain.model.toBet

class BetsRepository(
    private val api: AlphaFeedApi,
    private val dao: BetDao
) {
    suspend fun load(): BoardResult {
        return try {
            val report = api.quantReport()
            val bets = report.opportunities
                .filter { it.betEligible == true }
                .map { it.toBet() }
                .sortedByDescending { it.evPercent }
            dao.replaceAll(bets.map { it.toEntity() })
            BoardResult(bets, false, report.generatedAt)
        } catch (e: Exception) {
            BoardResult(dao.getAll().map { it.toBet() }, true, null)
        }
    }
}
