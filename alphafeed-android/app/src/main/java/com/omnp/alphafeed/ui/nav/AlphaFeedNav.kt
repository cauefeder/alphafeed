package com.omnp.alphafeed.ui.nav

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.omnp.alphafeed.domain.BoardGating
import com.omnp.alphafeed.domain.model.Bet
import com.omnp.alphafeed.domain.model.Confidence
import com.omnp.alphafeed.ui.bets.BetsScreen
import com.omnp.alphafeed.ui.bets.BetsUi
import com.omnp.alphafeed.ui.detail.BetDetailScreen
import com.omnp.alphafeed.ui.detail.BetDetailViewModel
import com.omnp.alphafeed.ui.feed.FeedScreen
import com.omnp.alphafeed.ui.more.MoreScreen
import com.omnp.alphafeed.ui.paywall.PaywallSheet
import com.omnp.alphafeed.ui.record.RecordScreen
import com.omnp.alphafeed.ui.theme.AlphaFeedTheme

private sealed class Dest(val route: String, val label: String) {
    data object Bets : Dest("bets", "Bets")
    data object Feed : Dest("feed", "Feed")
    data object Record : Dest("record", "Record")
    data object More : Dest("more", "More")
}

private const val ROUTE_BET_DETAIL = "betDetail"

private val SAMPLE_BOARD = listOf(
    Bet("1", "Red Sox −1.5", 47, 53, 33, Confidence.STRONG, "MLB", null, 3.0),
    Bet("2", "Lakers ML", 18, 55, 60, Confidence.VALUE, "NBA", null, 1.67),
    Bet("3", "Man City -1 AH", 22, 51, 45, Confidence.STRONG, "EPL", null, 2.2),
    Bet("4", "Yankees o8.5", 14, 52, 62, Confidence.VALUE, "MLB", null, 1.6),
    Bet("5", "Celtics -4.5", 31, 54, 41, Confidence.STRONG, "NBA", null, 2.4)
)

/**
 * App shell: bottom navigation across Bets / Feed / Record / More, with Bets pushing to a
 * bet-detail route. Data isn't wired end-to-end yet — screens run on remembered sample state
 * so the navigation graph compiles and previews.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AlphaFeedNav() {
    val navController = rememberNavController()
    // Local paywall/entitlement state for now — real purchase wiring is a later task.
    var isPro by remember { mutableStateOf(false) }
    var showPaywall by remember { mutableStateOf(false) }
    var selectedBet by remember { mutableStateOf<Bet?>(null) }

    val betsUi = remember(isPro) {
        BetsUi.Content(
            rows = BoardGating.rows(SAMPLE_BOARD, isPro),
            isOffline = false,
            updatedAt = "just now"
        )
    }

    val items = listOf(Dest.Bets, Dest.Feed, Dest.Record, Dest.More)

    Scaffold(
        bottomBar = {
            val backStackEntry by navController.currentBackStackEntryAsState()
            val currentDestination = backStackEntry?.destination
            NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                items.forEach { dest ->
                    val selected = currentDestination?.hierarchy?.any { it.route == dest.route } == true
                    NavigationBarItem(
                        selected = selected,
                        onClick = {
                            navController.navigate(dest.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Icon(dest.icon(), contentDescription = dest.label) },
                        label = { Text(dest.label) }
                    )
                }
            }
        },
        containerColor = MaterialTheme.colorScheme.background
    ) { padding ->
        NavHost(
            navController = navController,
            startDestination = Dest.Bets.route,
            modifier = Modifier.padding(padding)
        ) {
            composable(Dest.Bets.route) {
                BetsScreen(
                    state = betsUi,
                    onBet = { bet ->
                        selectedBet = bet
                        navController.navigate(ROUTE_BET_DETAIL)
                    },
                    onUpgrade = { showPaywall = true },
                    onRetry = {}
                )
            }
            composable(Dest.Feed.route) { FeedScreen() }
            composable(Dest.Record.route) {
                RecordScreen(isPro = isPro, onUpgrade = { showPaywall = true })
            }
            composable(Dest.More.route) {
                MoreScreen(onUpgrade = { showPaywall = true })
            }
            composable(ROUTE_BET_DETAIL) {
                val bet = selectedBet ?: SAMPLE_BOARD.first()
                val detailUi = remember(bet) {
                    BetDetailViewModel(
                        bet = bet,
                        winProb = bet.winPercent / 100.0,
                        smartCount = 4,
                        smartTotal = 5,
                        isPointMarket = true,
                        sameDay = true
                    ).ui
                }
                BetDetailScreen(
                    ui = detailUi,
                    onBack = { navController.popBackStack() },
                    onTrack = {},
                    onShare = {}
                )
            }
        }
    }

    if (showPaywall) {
        PaywallSheet(
            onDismiss = { showPaywall = false },
            onSubscribe = {
                isPro = true
                showPaywall = false
            }
        )
    }
}

private fun Dest.icon() = when (this) {
    Dest.Bets -> Icons.AutoMirrored.Filled.List
    Dest.Feed -> Icons.Filled.Notifications
    Dest.Record -> Icons.Filled.Star
    Dest.More -> Icons.Filled.MoreVert
}

@Preview(showBackground = true, backgroundColor = 0xFF0D1016)
@Composable
private fun AlphaFeedNavPreview() {
    AlphaFeedTheme {
        AlphaFeedNav()
    }
}
