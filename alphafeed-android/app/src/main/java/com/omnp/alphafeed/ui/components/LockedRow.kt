package com.omnp.alphafeed.ui.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.omnp.alphafeed.ui.theme.AlphaFeedTheme
import com.omnp.alphafeed.ui.theme.GreenStrong

/** Free-tier paywall teaser row shown at the bottom of the bets board. */
@Composable
fun LockedRow(remaining: Int, onUpgrade: () -> Unit, modifier: Modifier = Modifier) {
    val outline = MaterialTheme.colorScheme.outline
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .clickable(onClick = onUpgrade)
            .drawBehind {
                val stroke = Stroke(
                    width = 1.5.dp.toPx(),
                    pathEffect = PathEffect.dashPathEffect(floatArrayOf(10f, 8f), 0f)
                )
                drawRoundRect(
                    color = outline,
                    style = stroke,
                    cornerRadius = CornerRadius(14.dp.toPx())
                )
            },
        shape = RoundedCornerShape(14.dp),
        color = MaterialTheme.colorScheme.surface
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 18.dp),
            horizontalArrangement = androidx.compose.foundation.layout.Arrangement.Center,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "🔒 +$remaining more · Go Pro",
                style = MaterialTheme.typography.titleSmall,
                color = GreenStrong,
                fontWeight = FontWeight.Bold
            )
        }
    }
}

@Preview(showBackground = true, backgroundColor = 0xFF0D1016)
@Composable
private fun LockedRowPreview() {
    AlphaFeedTheme {
        LockedRow(remaining = 6, onUpgrade = {})
    }
}
