package com.omnp.alphafeed.ui.onboarding

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.omnp.alphafeed.R
import com.omnp.alphafeed.ui.theme.AlphaFeedTheme
import com.omnp.alphafeed.ui.theme.GreenStrong

private data class Slide(val title: String, val body: String)

private val SLIDES = listOf(
    Slide(
        title = "Model-ranked edges",
        body = "AlphaFeed scores sports markets against a quant model and surfaces the picks " +
            "with the biggest gap between model fair value and the market price."
    ),
    Slide(
        title = "Free daily picks, Pro for the full board",
        body = "See the top picks free, every day. Go Pro to unlock the full board, drop ads, " +
            "and get push alerts the moment a new edge appears."
    )
)

/**
 * First-run flow: a couple of quick slides, then a compliance gate the user must
 * explicitly accept before reaching the app. Acceptance is persisted by the caller.
 */
@Composable
fun OnboardingScreen(onFinished: () -> Unit, modifier: Modifier = Modifier) {
    var page by rememberSaveable { mutableIntStateOf(0) }

    Surface(modifier = modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp),
            verticalArrangement = Arrangement.SpaceBetween
        ) {
            if (page < SLIDES.size) {
                SlideContent(slide = SLIDES[page])
                Button(
                    onClick = { page++ },
                    modifier = Modifier.fillMaxWidth().height(52.dp)
                ) {
                    Text("Next", fontWeight = FontWeight.Bold)
                }
            } else {
                ConsentContent()
                Button(
                    onClick = onFinished,
                    modifier = Modifier.fillMaxWidth().height(52.dp),
                    colors = androidx.compose.material3.ButtonDefaults.buttonColors(containerColor = GreenStrong)
                ) {
                    Text(stringResource(R.string.disclaimer_accept), fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
private fun SlideContent(slide: Slide) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            text = slide.title,
            style = MaterialTheme.typography.displaySmall,
            color = MaterialTheme.colorScheme.onSurface,
            fontWeight = FontWeight.Black
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            text = slide.body,
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
private fun ConsentContent() {
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            text = stringResource(R.string.disclaimer_title),
            style = MaterialTheme.typography.displaySmall,
            color = MaterialTheme.colorScheme.onSurface,
            fontWeight = FontWeight.Black
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            text = stringResource(R.string.disclaimer_full),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Preview(showBackground = true, backgroundColor = 0xFF0D1016)
@Composable
private fun OnboardingScreenPreview() {
    AlphaFeedTheme {
        OnboardingScreen(onFinished = {})
    }
}
