package com.omnp.alphafeed

import app.cash.turbine.test
import com.omnp.alphafeed.data.BoardResult
import com.omnp.alphafeed.domain.Row
import com.omnp.alphafeed.domain.model.Bet
import com.omnp.alphafeed.domain.model.Confidence
import com.omnp.alphafeed.ui.bets.BetsUi
import com.omnp.alphafeed.ui.bets.BetsViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class BetsViewModelTest {
    private val mainDispatcher = StandardTestDispatcher()

    @Before fun setUp() {
        Dispatchers.setMain(mainDispatcher)
    }

    @After fun tearDown() {
        Dispatchers.resetMain()
    }

    private fun bet(id: String) = Bet(id, "m", 40, 50, 30, Confidence.VALUE, "MLB", null, 3.0)

    private class FakeRepo(val res: BoardResult) {
        suspend fun load() = res
    }

    @Test fun free_content_is_gated_to_three() = runTest {
        val repo = FakeRepo(BoardResult((1..8).map { bet("b$it") }, false, "now"))
        val vm = BetsViewModel(loader = { repo.load() }, isProFlow = MutableStateFlow(false))
        vm.state.test {
            assertTrue(awaitItem() is BetsUi.Loading)
            val c = awaitItem() as BetsUi.Content
            assertEquals(3, c.rows.count { it is Row.BetRow })
            cancelAndIgnoreRemainingEvents()
        }
    }

    @Test fun offline_flag_surfaces() = runTest {
        val vm = BetsViewModel(loader = { BoardResult(listOf(bet("a")), true, null) }, isProFlow = MutableStateFlow(true))
        vm.state.test {
            awaitItem()
            val c = awaitItem() as BetsUi.Content
            assertTrue(c.isOffline)
            cancelAndIgnoreRemainingEvents()
        }
    }
}
