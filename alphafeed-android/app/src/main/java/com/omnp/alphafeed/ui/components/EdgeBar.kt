package com.omnp.alphafeed.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.omnp.alphafeed.ui.theme.AlphaFeedTheme
import com.omnp.alphafeed.ui.theme.GreenStrong
import com.omnp.alphafeed.ui.theme.LineDark
import kotlin.math.max
import kotlin.math.min

/**
 * Horizontal bar comparing the model's win probability against the market-implied price.
 * A green gradient fill runs to [modelWinPct]% width; a thin white marker sits at [marketPct]%.
 */
@Composable
fun EdgeBar(modelWinPct: Int, marketPct: Int, modifier: Modifier = Modifier) {
    val modelFraction = clampPct(modelWinPct)
    val marketFraction = clampPct(marketPct)

    Column(modifier = modifier.fillMaxWidth()) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(10.dp)
                .clip(RoundedCornerShape(50))
                .background(LineDark)
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth(modelFraction)
                    .height(10.dp)
                    .clip(RoundedCornerShape(50))
                    .background(
                        Brush.horizontalGradient(
                            listOf(GreenStrong.copy(alpha = 0.55f), GreenStrong)
                        )
                    )
            )
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(10.dp)
            ) {
                Box(
                    modifier = Modifier
                        .align(Alignment.CenterStart)
                        .padding(start = 0.dp)
                        .fillMaxWidth(marketFraction)
                ) {
                    Box(
                        modifier = Modifier
                            .align(Alignment.CenterEnd)
                            .width(2.dp)
                            .height(14.dp)
                            .background(Color.White)
                    )
                }
            }
        }
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 6.dp),
            horizontalArrangement = androidx.compose.foundation.layout.Arrangement.SpaceBetween
        ) {
            Text(
                text = "Model win $modelWinPct%",
                style = MaterialTheme.typography.labelSmall,
                color = GreenStrong
            )
            Text(
                text = "Market $marketPct%",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

private fun clampPct(pct: Int): Float = max(0, min(100, pct)) / 100f

@Preview(showBackground = true, backgroundColor = 0xFF0D1016)
@Composable
private fun EdgeBarPreview() {
    AlphaFeedTheme {
        Box(modifier = Modifier.padding(PaddingValues(16.dp))) {
            EdgeBar(modelWinPct = 53, marketPct = 33)
        }
    }
}
