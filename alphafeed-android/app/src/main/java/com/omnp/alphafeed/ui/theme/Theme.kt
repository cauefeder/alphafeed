package com.omnp.alphafeed.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val AlphaFeedColorScheme = darkColorScheme(
    primary = GreenStrong,
    onPrimary = BgDark,
    secondary = AmberValue,
    onSecondary = BgDark,
    tertiary = BlueAccent,
    onTertiary = BgDark,
    background = BgDark,
    onBackground = OnSurfaceDark,
    surface = SurfaceDark,
    onSurface = OnSurfaceDark,
    surfaceVariant = SurfaceAltDark,
    onSurfaceVariant = SecondaryDark,
    outline = LineDark,
    outlineVariant = ChipDark,
    error = AmberValue,
    onError = BgDark
)

/**
 * AlphaFeed "Bold Sport" theme — committed dark, no light variant.
 */
@Composable
fun AlphaFeedTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = AlphaFeedColorScheme,
        typography = AlphaFeedType,
        content = content
    )
}
