package com.omnp.alphafeed.ui.detail

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.omnp.alphafeed.domain.EdgeCalc
import com.omnp.alphafeed.domain.model.Bet
import com.omnp.alphafeed.domain.model.Confidence
import com.omnp.alphafeed.ui.components.EdgeBar
import com.omnp.alphafeed.ui.theme.AlphaFeedTheme
import com.omnp.alphafeed.ui.theme.AmberValue
import com.omnp.alphafeed.ui.theme.ChipDark
import com.omnp.alphafeed.ui.theme.GreenStrong
import com.omnp.alphafeed.ui.theme.TabularNums

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BetDetailScreen(
    ui: DetailUi,
    onBack: () -> Unit,
    onTrack: () -> Unit,
    onShare: () -> Unit
) {
    val bet = ui.bet
    val confidenceColor = if (bet.confidence == Confidence.STRONG) GreenStrong else AmberValue

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(bet.market, style = MaterialTheme.typography.titleLarge) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    LeagueBadge(bet.leagueLabel)
                    Spacer(modifier = Modifier.padding(end = 8.dp))
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background
                )
            )
        },
        bottomBar = {
            Surface(color = MaterialTheme.colorScheme.background) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    OutlinedButton(
                        onClick = onShare,
                        modifier = Modifier
                            .weight(1f)
                            .height(52.dp)
                    ) {
                        Icon(Icons.Filled.Share, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.padding(start = 4.dp))
                        Text("Share")
                    }
                    Button(
                        onClick = onTrack,
                        modifier = Modifier
                            .weight(1f)
                            .height(52.dp)
                    ) {
                        Text("Track", fontWeight = FontWeight.Bold)
                    }
                }
            }
        },
        containerColor = MaterialTheme.colorScheme.background
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .padding(horizontal = 16.dp)
        ) {
            Spacer(modifier = Modifier.height(8.dp))
            HeroCard(evPercent = bet.evPercent)
            Spacer(modifier = Modifier.height(20.dp))
            EdgeBar(modelWinPct = ui.edge.modelWinPct, marketPct = ui.edge.marketPct)
            Spacer(modifier = Modifier.height(20.dp))
            StatRow(bet = bet, confidenceColor = confidenceColor)
            Spacer(modifier = Modifier.height(24.dp))
            Text(
                text = "Why this pick",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurface
            )
            Spacer(modifier = Modifier.height(10.dp))
            ui.reasons.forEach { reason ->
                ReasonRow(reason)
                Spacer(modifier = Modifier.height(8.dp))
            }
            Spacer(modifier = Modifier.height(12.dp))
            HorizontalDivider(color = MaterialTheme.colorScheme.outline)
            Spacer(modifier = Modifier.height(12.dp))
            Text(
                text = ui.disclaimer,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}

@Composable
private fun LeagueBadge(label: String) {
    Surface(
        color = ChipDark,
        shape = RoundedCornerShape(8.dp)
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp)
        )
    }
}

@Composable
private fun HeroCard(evPercent: Int) {
    Surface(
        color = GreenStrong.copy(alpha = 0.12f),
        shape = RoundedCornerShape(18.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(20.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = "Expected ROI",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = "+$evPercent%",
                style = MaterialTheme.typography.displayLarge.merge(TabularNums),
                color = GreenStrong
            )
        }
    }
}

@Composable
private fun StatRow(bet: Bet, confidenceColor: androidx.compose.ui.graphics.Color) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        StatItem(label = "Price", value = "${bet.priceCents}¢")
        StatItem(label = "Payout", value = "${bet.payoutX}×")
        StatItem(label = "Confidence", value = bet.confidence.name, valueColor = confidenceColor)
    }
}

@Composable
private fun StatItem(
    label: String,
    value: String,
    valueColor: androidx.compose.ui.graphics.Color = MaterialTheme.colorScheme.onSurface
) {
    Column(horizontalAlignment = Alignment.Start) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(modifier = Modifier.padding(top = 2.dp))
        Text(
            text = value,
            style = MaterialTheme.typography.titleMedium.merge(TabularNums),
            color = valueColor
        )
    }
}

@Composable
private fun ReasonRow(text: String) {
    Row(verticalAlignment = Alignment.Top) {
        Box(
            modifier = Modifier
                .padding(top = 7.dp, end = 10.dp)
                .size(6.dp)
                .clip(RoundedCornerShape(50))
                .background(GreenStrong)
        )
        Text(
            text = text,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface
        )
    }
}

@Preview(showBackground = true, backgroundColor = 0xFF0D1016)
@Composable
private fun BetDetailScreenPreview() {
    val bet = Bet(
        id = "id",
        market = "Red Sox −1.5",
        evPercent = 47,
        winPercent = 53,
        priceCents = 33,
        confidence = Confidence.STRONG,
        leagueLabel = "MLB",
        url = null,
        payoutX = 3.0
    )
    val ui = DetailUi(
        bet = bet,
        edge = EdgeCalc.of(0.53, 0.33),
        reasons = listOf(
            "4 of 5 tracked smart-money traders are on this side",
            "Spread/total market — historically stronger hit rate",
            "Same-day game (most stable signal)",
            "Priced below model fair value (~53¢)"
        ),
        disclaimer = "Informational analytics only — not betting or financial advice. " +
            "AlphaFeed does not accept or place wagers. 18+."
    )
    AlphaFeedTheme {
        BetDetailScreen(ui = ui, onBack = {}, onTrack = {}, onShare = {})
    }
}
