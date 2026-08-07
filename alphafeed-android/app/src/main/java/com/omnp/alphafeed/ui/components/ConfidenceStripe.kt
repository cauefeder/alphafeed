package com.omnp.alphafeed.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.omnp.alphafeed.domain.model.Confidence
import com.omnp.alphafeed.ui.theme.AmberValue
import com.omnp.alphafeed.ui.theme.GreenStrong

/** 4dp vertical stripe: green for STRONG confidence, amber for VALUE. */
@Composable
fun ConfidenceStripe(confidence: Confidence, modifier: Modifier = Modifier) {
    androidx.compose.foundation.layout.Box(
        modifier = modifier
            .fillMaxHeight()
            .width(4.dp)
            .clip(RoundedCornerShape(topStart = 14.dp, bottomStart = 14.dp))
            .background(confidence.color())
    )
}

fun Confidence.color(): Color = if (this == Confidence.STRONG) GreenStrong else AmberValue
