package com.omnp.alphafeed.ui.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.omnp.alphafeed.domain.model.Bet
import com.omnp.alphafeed.domain.model.Confidence
import com.omnp.alphafeed.ui.theme.AlphaFeedTheme
import com.omnp.alphafeed.ui.theme.ChipDark
import com.omnp.alphafeed.ui.theme.TabularNums

/**
 * Primary board item: dark surface card, 14dp rounded corners, a left confidence stripe,
 * market title + league/tag chips, and a big EV readout on the right.
 */
@Composable
fun BetCard(bet: Bet, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val accent = bet.confidence.color()
    Card(
        modifier = modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Row(modifier = Modifier.height(IntrinsicSize.Min).fillMaxWidth()) {
            ConfidenceStripe(confidence = bet.confidence)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(start = 12.dp, top = 14.dp, bottom = 14.dp, end = 16.dp),
                horizontalArrangement = androidx.compose.foundation.layout.Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = bet.market,
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onSurface,
                        fontWeight = FontWeight.Bold,
                        maxLines = 2
                    )
                    Spacer(modifier = Modifier.padding(top = 8.dp))
                    Row {
                        Chip(bet.leagueLabel)
                        Spacer(modifier = Modifier.width(6.dp))
                        Chip(if (bet.confidence == Confidence.STRONG) "top pick" else "value")
                    }
                }
                Spacer(modifier = Modifier.width(12.dp))
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        text = "+${bet.evPercent}%",
                        style = MaterialTheme.typography.headlineMedium.merge(TabularNums),
                        color = accent,
                        fontWeight = FontWeight.ExtraBold
                    )
                    Spacer(modifier = Modifier.padding(top = 2.dp))
                    Text(
                        text = "win ${bet.winPercent}% · ${bet.priceCents}¢",
                        style = MaterialTheme.typography.bodySmall.merge(TabularNums),
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}

@Composable
private fun Chip(text: String) {
    Surface(color = ChipDark, shape = RoundedCornerShape(6.dp)) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
        )
    }
}

@Preview(showBackground = true, backgroundColor = 0xFF0D1016)
@Composable
private fun BetCardPreview() {
    AlphaFeedTheme {
        Column(modifier = Modifier.padding(12.dp)) {
            BetCard(
                bet = Bet("1", "Red Sox −1.5", 47, 53, 33, Confidence.STRONG, "MLB", null, 3.0),
                onClick = {}
            )
            Spacer(modifier = Modifier.padding(top = 12.dp))
            BetCard(
                bet = Bet("2", "Lakers ML", 18, 55, 60, Confidence.VALUE, "NBA", null, 1.67),
                onClick = {}
            )
        }
    }
}
