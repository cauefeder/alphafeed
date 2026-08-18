package com.omnp.alphafeed.ui.bets

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.omnp.alphafeed.domain.Row as BoardRow
import com.omnp.alphafeed.domain.model.Bet
import com.omnp.alphafeed.domain.model.Confidence
import com.omnp.alphafeed.ui.components.AdBanner
import com.omnp.alphafeed.ui.components.BetCard
import com.omnp.alphafeed.ui.components.LockedRow
import com.omnp.alphafeed.ui.theme.AlphaFeedTheme
import com.omnp.alphafeed.ui.theme.AmberValue

@Composable
fun BetsScreen(
    state: BetsUi,
    onBet: (Bet) -> Unit,
    onUpgrade: () -> Unit,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background
    ) {
        when (state) {
            is BetsUi.Loading -> LoadingState()
            is BetsUi.Error -> ErrorState(message = state.message, onRetry = onRetry)
            is BetsUi.Content -> ContentState(state = state, onBet = onBet, onUpgrade = onUpgrade, onRetry = onRetry)
        }
    }
}

@Composable
private fun LoadingState() {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
            Spacer(modifier = Modifier.padding(top = 16.dp))
            Text(
                text = "Loading today's board — the first load can take up to a minute while the free server wakes up.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                modifier = Modifier.padding(horizontal = 32.dp)
            )
        }
    }
}

@Composable
private fun ErrorState(message: String, onRetry: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            text = message,
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(modifier = Modifier.padding(top = 16.dp))
        Button(onClick = onRetry) {
            Text("Retry")
        }
    }
}

@Composable
private fun ContentState(
    state: BetsUi.Content,
    onBet: (Bet) -> Unit,
    onUpgrade: () -> Unit,
    onRetry: () -> Unit
) {
    // Offline with nothing cached (e.g. a fresh install where the first fetch failed):
    // show an actionable retry instead of an empty board.
    if (state.isOffline && state.rows.isEmpty()) {
        ErrorState(
            message = "Couldn't reach the server. It may be waking up (up to a minute) — please try again.",
            onRetry = onRetry
        )
        return
    }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Header(updatedAt = state.updatedAt)
        }
        if (state.isOffline) {
            item { OfflineBanner() }
        }
        items(state.rows) { row ->
            when (row) {
                is BoardRow.BetRow -> BetCard(bet = row.bet, onClick = { onBet(row.bet) })
                is BoardRow.AdRow -> AdBanner()
                is BoardRow.LockedRow -> LockedRow(remaining = row.remaining, onUpgrade = onUpgrade)
            }
        }
    }
}

@Composable
private fun Header(updatedAt: String?) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = "Today's Edge",
            style = MaterialTheme.typography.headlineLarge,
            color = MaterialTheme.colorScheme.onSurface,
            fontWeight = FontWeight.ExtraBold
        )
        if (updatedAt != null) {
            Spacer(modifier = Modifier.padding(top = 4.dp))
            Text(
                text = "Updated $updatedAt",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun OfflineBanner() {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(10.dp),
        color = AmberValue.copy(alpha = 0.15f)
    ) {
        Row(modifier = Modifier.padding(12.dp)) {
            Text(
                text = "You're offline — showing the last cached board.",
                style = MaterialTheme.typography.labelMedium,
                color = AmberValue
            )
        }
    }
}

@Preview(showBackground = true, backgroundColor = 0xFF0D1016)
@Composable
private fun BetsScreenContentPreview() {
    val sample = BetsUi.Content(
        rows = listOf(
            BoardRow.BetRow(Bet("1", "Red Sox −1.5", 47, 53, 33, Confidence.STRONG, "MLB", null, 3.0)),
            BoardRow.BetRow(Bet("2", "Lakers ML", 18, 55, 60, Confidence.VALUE, "NBA", null, 1.67)),
            BoardRow.AdRow,
            BoardRow.LockedRow(6)
        ),
        isOffline = true,
        updatedAt = "2m ago"
    )
    AlphaFeedTheme {
        BetsScreen(state = sample, onBet = {}, onUpgrade = {}, onRetry = {})
    }
}

@Preview(showBackground = true, backgroundColor = 0xFF0D1016)
@Composable
private fun BetsScreenLoadingPreview() {
    AlphaFeedTheme {
        BetsScreen(state = BetsUi.Loading, onBet = {}, onUpgrade = {}, onRetry = {})
    }
}

@Preview(showBackground = true, backgroundColor = 0xFF0D1016)
@Composable
private fun BetsScreenErrorPreview() {
    AlphaFeedTheme {
        BetsScreen(state = BetsUi.Error("Couldn't load the board"), onBet = {}, onUpgrade = {}, onRetry = {})
    }
}
