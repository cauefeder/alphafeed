package com.omnp.alphafeed.ui.feed

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.omnp.alphafeed.ui.theme.AlphaFeedTheme
import com.omnp.alphafeed.ui.theme.BlueAccent

/** Phase 2 placeholder — the real-time signal feed isn't wired up yet. */
@Composable
fun FeedScreen(modifier: Modifier = Modifier) {
    Surface(
        modifier = modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background
    ) {
        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Column(
                modifier = Modifier.padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = "Signal feed",
                    style = MaterialTheme.typography.headlineMedium,
                    color = BlueAccent,
                    fontWeight = FontWeight.ExtraBold
                )
                Text(
                    text = "Coming soon",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Preview(showBackground = true, backgroundColor = 0xFF0D1016)
@Composable
private fun FeedScreenPreview() {
    AlphaFeedTheme {
        FeedScreen()
    }
}
