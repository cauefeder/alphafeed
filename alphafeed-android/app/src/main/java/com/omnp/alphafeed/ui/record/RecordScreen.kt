package com.omnp.alphafeed.ui.record

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.omnp.alphafeed.ui.theme.AlphaFeedTheme
import com.omnp.alphafeed.ui.theme.GreenStrong
import com.omnp.alphafeed.ui.theme.TabularNums

/** Track record: real stats for Pro users, a blurred teaser + upsell for free users. */
@Composable
fun RecordScreen(isPro: Boolean, onUpgrade: () -> Unit, modifier: Modifier = Modifier) {
    Surface(
        modifier = modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background
    ) {
        if (isPro) {
            ProStats()
        } else {
            FreeTeaser(onUpgrade = onUpgrade)
        }
    }
}

@Composable
private fun ProStats() {
    Column(modifier = Modifier.padding(16.dp)) {
        Text(
            text = "Track Record",
            style = MaterialTheme.typography.headlineLarge,
            color = MaterialTheme.colorScheme.onSurface,
            fontWeight = FontWeight.ExtraBold
        )
        Spacer(modifier = Modifier.padding(top = 16.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            StatCard(label = "90-day ROI", value = "+14.2%")
            StatCard(label = "Hit rate", value = "58%")
        }
    }
}

@Composable
private fun StatCard(label: String, value: String) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = RoundedCornerShape(14.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = label,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(modifier = Modifier.padding(top = 4.dp))
            Text(
                text = value,
                style = MaterialTheme.typography.headlineMedium.merge(TabularNums),
                color = GreenStrong
            )
        }
    }
}

@Composable
private fun FreeTeaser(onUpgrade: () -> Unit) {
    Box(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier
                .padding(16.dp)
                .blur(14.dp)
        ) {
            Text(
                text = "Track Record",
                style = MaterialTheme.typography.headlineLarge,
                color = MaterialTheme.colorScheme.onSurface,
                fontWeight = FontWeight.ExtraBold
            )
            Spacer(modifier = Modifier.padding(top = 16.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                StatCard(label = "90-day ROI", value = "+14.2%")
                StatCard(label = "Hit rate", value = "58%")
            }
        }
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Text(
                text = "See our full track record",
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onSurface,
                fontWeight = FontWeight.Bold
            )
            Spacer(modifier = Modifier.padding(top = 8.dp))
            Button(onClick = onUpgrade) {
                Text("Go Pro")
            }
        }
    }
}

@Preview(showBackground = true, backgroundColor = 0xFF0D1016)
@Composable
private fun RecordScreenProPreview() {
    AlphaFeedTheme {
        RecordScreen(isPro = true, onUpgrade = {})
    }
}

@Preview(showBackground = true, backgroundColor = 0xFF0D1016)
@Composable
private fun RecordScreenFreePreview() {
    AlphaFeedTheme {
        RecordScreen(isPro = false, onUpgrade = {})
    }
}
