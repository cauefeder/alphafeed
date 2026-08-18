package com.omnp.alphafeed.ui.more

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.omnp.alphafeed.R
import com.omnp.alphafeed.ui.theme.AlphaFeedTheme
import com.omnp.alphafeed.ui.theme.GreenStrong

private data class MoreRow(val label: String, val highlighted: Boolean = false, val onClick: () -> Unit = {})

@Composable
fun MoreScreen(onUpgrade: () -> Unit, modifier: Modifier = Modifier) {
    var showDisclaimers by remember { mutableStateOf(false) }
    val rows = listOf(
        MoreRow("Go Pro", highlighted = true, onClick = onUpgrade),
        MoreRow("Restore purchases"),
        MoreRow("Disclaimers", onClick = { showDisclaimers = true }),
        MoreRow("Privacy"),
        MoreRow("About")
    )
    Surface(
        modifier = modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background
    ) {
        Column(modifier = Modifier.padding(vertical = 8.dp)) {
            rows.forEachIndexed { index, row ->
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable(onClick = row.onClick)
                        .padding(horizontal = 20.dp, vertical = 18.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = row.label,
                        style = MaterialTheme.typography.titleMedium,
                        color = if (row.highlighted) GreenStrong else MaterialTheme.colorScheme.onSurface,
                        fontWeight = if (row.highlighted) FontWeight.Bold else FontWeight.Normal
                    )
                }
                if (index != rows.lastIndex) {
                    HorizontalDivider(color = MaterialTheme.colorScheme.outline)
                }
            }
        }
    }

    if (showDisclaimers) {
        AlertDialog(
            onDismissRequest = { showDisclaimers = false },
            title = { Text(stringResource(R.string.disclaimer_title)) },
            text = { Text(stringResource(R.string.disclaimer_full)) },
            confirmButton = {
                TextButton(onClick = { showDisclaimers = false }) {
                    Text(stringResource(R.string.disclaimer_accept))
                }
            }
        )
    }
}

@Preview(showBackground = true, backgroundColor = 0xFF0D1016)
@Composable
private fun MoreScreenPreview() {
    AlphaFeedTheme {
        MoreScreen(onUpgrade = {})
    }
}
