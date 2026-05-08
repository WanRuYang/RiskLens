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
        Text("Pixel 8 product-serving shell. Choose one input method: images, URL, or typed text.")

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
                Text("Input mode")
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { viewModel.inputMode = "image" }) { Text("Images") }
                    Button(onClick = { viewModel.inputMode = "url" }) { Text("URL") }
                    Button(onClick = { viewModel.inputMode = "text" }) { Text("Text") }
                }
                Text("Selected: ${viewModel.inputMode}")
            }
        }

        OutlinedTextField(
            value = viewModel.productName,
            onValueChange = { viewModel.productName = it },
            label = { Text("Product name") },
            modifier = Modifier.fillMaxWidth(),
        )

        if (viewModel.inputMode == "image") {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Text("Image intake")
                    Text("Enter image URIs or notes, then review the OCR text before analysis. If the text is still unreadable, switch to URL or Text mode.")
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
                            Text("Clear image flow")
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
        }

        if (viewModel.inputMode == "url") {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Text("URL input")
                    Text("Paste a product page URL. If the page cannot be read, the app should ask you to retry the URL or switch to images/text.")
                    OutlinedTextField(
                        value = viewModel.productPageUrl,
                        onValueChange = { viewModel.productPageUrl = it },
                        label = { Text("Product page URL") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }
        }

        if (viewModel.inputMode == "text") {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.padding(12.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Text("Typed text input")
                    Text("Paste the product name, ingredient list, warning text, or a fuller product description. If the text is too incomplete, the app should recommend URL or image mode.")
                    OutlinedTextField(
                        value = viewModel.directText,
                        onValueChange = { viewModel.directText = it },
                        label = { Text("Typed product description / ingredients / warning text") },
                        modifier = Modifier.fillMaxWidth(),
                        minLines = 8,
                    )
                }
            }
        }

        Button(onClick = { viewModel.analyze() }) {
            Text("Analyze")
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
