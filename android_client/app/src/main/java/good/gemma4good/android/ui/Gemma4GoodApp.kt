package good.gemma4good.android.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel

@Composable
fun Gemma4GoodApp(
    viewModel: Gemma4GoodViewModel = viewModel(),
) {
    val scroll = rememberScrollState()
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
            .verticalScroll(scroll),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("gemma4good Android MVP")
        Text("Single-composer product shell. Type product text, paste a URL, or add image placeholders and OCR review text; the app detects the right path behind the scenes.")

        OutlinedTextField(
            value = viewModel.userId,
            onValueChange = { viewModel.userId = it },
            label = { Text("User ID") },
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = viewModel.region,
            onValueChange = { viewModel.region = it },
            label = { Text("Region") },
            modifier = Modifier.fillMaxWidth(),
        )

        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Message")
                Text("Paste a product URL, type product details, or add notes about the images you are uploading. The app will decide whether this turn is URL-driven, text-driven, or image-driven.")
                OutlinedTextField(
                    value = viewModel.messageInput,
                    onValueChange = { viewModel.messageInput = it },
                    label = { Text("Product message") },
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 6,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { viewModel.previewUrlFetch() }) {
                        Text("Preview URL fetch")
                    }
                    Button(onClick = { viewModel.analyze() }) {
                        Text("Analyze")
                    }
                }
                if (viewModel.urlPreviewText.isNotBlank()) {
                    OutlinedTextField(
                        value = viewModel.urlPreviewText,
                        onValueChange = {},
                        label = { Text("URL fetch preview") },
                        modifier = Modifier.fillMaxWidth(),
                        minLines = 8,
                        readOnly = true,
                    )
                }
            }
        }

        Card(modifier = Modifier.fillMaxWidth()) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Text("Optional image attachments")
                Text("For now, enter image URIs or notes here, then create an OCR review draft. This card can represent product photos, ingredient panels, or a Prop 65 warning sticker.")
                OutlinedTextField(
                    value = viewModel.frontImageUri,
                    onValueChange = { viewModel.frontImageUri = it },
                    label = { Text("Front image URI or note") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = viewModel.ingredientsImageUri,
                    onValueChange = { viewModel.ingredientsImageUri = it },
                    label = { Text("Ingredients image URI or note") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = viewModel.warningImageUri,
                    onValueChange = { viewModel.warningImageUri = it },
                    label = { Text("Warning image URI or note") },
                    modifier = Modifier.fillMaxWidth(),
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { viewModel.prepareOcrDraft() }) {
                        Text("Create OCR review draft")
                    }
                    Button(onClick = { viewModel.clearImageFlow() }) {
                        Text("Clear image attachments")
                    }
                }
                OutlinedTextField(
                    value = viewModel.ocrReviewText,
                    onValueChange = { viewModel.ocrReviewText = it },
                    label = { Text("OCR review text") },
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 8,
                )
            }
        }

        Spacer(modifier = Modifier.height(8.dp))
        Text("Status: ${viewModel.statusText}")
        if (viewModel.errorText.isNotBlank()) {
            Text("Issue: ${viewModel.errorText}")
        }
        if (viewModel.nextStepText.isNotBlank()) {
            Text("Suggested next step: ${viewModel.nextStepText}")
        }
        if (viewModel.resultSummary.isNotBlank()) {
            Text(viewModel.resultSummary)
        }
    }
}
