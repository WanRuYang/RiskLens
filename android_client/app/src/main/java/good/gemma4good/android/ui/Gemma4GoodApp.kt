package good.gemma4good.android.ui

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.PhotoCamera
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.graphics.Color
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage

@Composable
fun Gemma4GoodApp(
    viewModel: Gemma4GoodViewModel = viewModel(),
) {
    val context = LocalContext.current
    val scroll = rememberScrollState()

    // Activity Result Launchers
    val galleryLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetMultipleContents()
    ) { uris ->
        uris.forEach { viewModel.addImage(it) }
    }

    val cameraLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.TakePicture()
    ) { success ->
        if (success) {
            viewModel.onCameraCaptureSuccess()
        }
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (isGranted) {
            val uri = viewModel.getTempCameraUri(context)
            cameraLauncher.launch(uri)
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
            .verticalScroll(scroll),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        // Header Mimic
        Text(
            text = "Hazardly",
            style = MaterialTheme.typography.headlineLarge.copy(
                fontWeight = FontWeight.Bold,
                letterSpacing = (-0.06).sp
            )
        )
        Text(
            text = "Send a product URL, type a product name/description, or attach product label images. For food images, include front label, ingredients, and nutrition facts.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        // Settings Accordion
        SettingsAccordion(viewModel)

        HazardlyScoreCard(viewModel.latestAnalysis?.hazardlyScore)
        HazardlyFlagsCard(viewModel.latestAnalysis?.hazardlyScore)
        ResultExplanationCard(viewModel)
        FeedbackCard(viewModel)

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Button(
                onClick = { viewModel.submit(context) },
                modifier = Modifier.weight(1f),
                shape = RoundedCornerShape(999.dp),
            ) {
                Text("Analyze Product")
            }
            OutlinedButton(
                onClick = { viewModel.reset() },
                modifier = Modifier.weight(1f),
                shape = RoundedCornerShape(999.dp),
            ) {
                Text("Start new analysis")
            }
        }

        // Image-first composer for phone identify flow.
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(24.dp),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
        ) {
            Column(modifier = Modifier.padding(12.dp)) {
                Text("1. Capture or upload product images", fontWeight = FontWeight.Bold)
                Text(
                    text = "Start with the product front, then add ingredient and Nutrition Facts photos when available.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    OutlinedButton(
                        onClick = { permissionLauncher.launch(android.Manifest.permission.CAMERA) },
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(999.dp),
                    ) {
                        Icon(Icons.Default.PhotoCamera, contentDescription = null)
                        Spacer(modifier = Modifier.size(6.dp))
                        Text("Camera")
                    }
                    OutlinedButton(
                        onClick = { galleryLauncher.launch("image/*") },
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(999.dp),
                    ) {
                        Icon(Icons.Default.Add, contentDescription = null)
                        Spacer(modifier = Modifier.size(6.dp))
                        Text("Gallery")
                    }
                }

                // Image thumbnails
                if (viewModel.attachedImages.isNotEmpty()) {
                    LazyRow(
                        contentPadding = PaddingValues(horizontal = 4.dp, vertical = 8.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(viewModel.attachedImages) { uri ->
                            Box(modifier = Modifier.size(80.dp)) {
                                AsyncImage(
                                    model = uri,
                                    contentDescription = null,
                                    modifier = Modifier
                                        .fillMaxSize()
                                        .clip(RoundedCornerShape(12.dp)),
                                    contentScale = ContentScale.Crop
                                )
                                IconButton(
                                    onClick = { viewModel.removeImage(uri) },
                                    modifier = Modifier
                                        .align(Alignment.TopEnd)
                                        .size(24.dp)
                                        .padding(4.dp)
                                ) {
                                    Surface(
                                        shape = RoundedCornerShape(12.dp),
                                        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.7f)
                                    ) {
                                        Icon(Icons.Default.Close, contentDescription = "Remove", modifier = Modifier.size(16.dp))
                                    }
                                }
                            }
                        }
                    }
                }

                OutlinedTextField(
                    value = viewModel.messageInput,
                    onValueChange = { viewModel.messageInput = it },
                    placeholder = { Text("Optional: type product text or paste a URL…") },
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 3,
                    shape = RoundedCornerShape(16.dp),
                )

                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 8.dp),
                    horizontalArrangement = Arrangement.End,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Button(
                        onClick = { viewModel.submit(context) },
                        shape = RoundedCornerShape(999.dp)
                    ) {
                        Text("Analyze Product")
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(24.dp))
        Text(
            text = "Disclaimer: Hazardly is for informational screening only. Actual risk depends on dose, frequency, and individual sensitivity.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
private fun HazardlyScoreCard(score: good.gemma4good.contract.HazardlyScoreDto?) {
    if (score == null) return

    val grades = listOf(
        Triple("A", "Low", Color(0xFF1F9D55)),
        Triple("B", "Mild", Color(0xFF78C850)),
        Triple("C", "Moderate", Color(0xFFF2CF3A)),
        Triple("D", "High", Color(0xFFF28C28)),
        Triple("E", "Very high", Color(0xFFD64545)),
    )

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(score.title, fontWeight = FontWeight.Bold)
                Surface(
                    shape = RoundedCornerShape(999.dp),
                    color = MaterialTheme.colorScheme.surfaceVariant,
                ) {
                    Text(
                        text = "Grade ${score.score}",
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                        style = MaterialTheme.typography.labelMedium,
                    )
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                grades.forEach { (grade, _, color) ->
                    val selected = grade == score.score
                    Surface(
                        modifier = Modifier
                            .weight(1f)
                            .height(46.dp),
                        shape = RoundedCornerShape(12.dp),
                        color = color,
                        border = if (selected) {
                            androidx.compose.foundation.BorderStroke(3.dp, MaterialTheme.colorScheme.onSurface)
                        } else {
                            null
                        },
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Text(
                                text = grade,
                                color = Color.White,
                                fontWeight = FontWeight.Bold,
                            )
                        }
                    }
                }
            }

            Row(modifier = Modifier.fillMaxWidth()) {
                grades.forEach { (_, label, _) ->
                    Text(
                        text = label,
                        modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            Text(
                text = score.description,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun HazardlyFlagsCard(score: good.gemma4good.contract.HazardlyScoreDto?) {
    if (score == null) return
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("Hazardly Flags", fontWeight = FontWeight.Bold)
            if (score.riskSignals.isEmpty() && score.nutritionFlags.isEmpty()) {
                Text(
                    text = "No additional hazard or food flags were identified from the available input.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (score.riskSignals.isNotEmpty()) {
                Text("Chemical / process flags", style = MaterialTheme.typography.labelMedium)
                score.riskSignals.take(5).forEach { signal ->
                    Surface(
                        shape = RoundedCornerShape(16.dp),
                        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f),
                    ) {
                        Text(
                            text = signal,
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }
            if (score.isFood && score.nutritionFlags.isNotEmpty()) {
                Text("Food flags", style = MaterialTheme.typography.labelMedium)
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    score.nutritionFlags.forEach { flag ->
                        Surface(
                            shape = RoundedCornerShape(999.dp),
                            color = MaterialTheme.colorScheme.surfaceVariant,
                        ) {
                            Text(
                                text = flag,
                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 7.dp),
                                style = MaterialTheme.typography.labelMedium,
                            )
                        }
                    }
                }
                Text(
                    text = "These food-only flags do not affect the A-E Hazardly Score.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun ResultExplanationCard(viewModel: Gemma4GoodViewModel) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .height(260.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f)),
        shape = RoundedCornerShape(24.dp),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text("Result explanation", fontWeight = FontWeight.Bold)
            Text(
                text = if (viewModel.isProcessing) "Gemma is processing..." else "Status: ${viewModel.statusText}",
                style = MaterialTheme.typography.labelMedium,
                color = if (viewModel.isProcessing) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.secondary,
            )
            if (viewModel.errorText.isNotBlank()) {
                Text(
                    text = "Issue: ${viewModel.errorText}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
            if (viewModel.nextStepText.isNotBlank()) {
                Text(
                    text = "Next step: ${viewModel.nextStepText}",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
            Spacer(modifier = Modifier.height(10.dp))
            val explanationScroll = rememberScrollState()
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(explanationScroll),
            ) {
                Text(
                    text = viewModel.resultExplanation.ifBlank {
                        "Analyze a product to see product identification, OCR / label extraction, ingredient and nutrition parsing, chemical/process screening, nutrition flags, and recommendation details."
                    },
                    style = MaterialTheme.typography.bodySmall,
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "Scroll for full explanation",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun FeedbackCard(viewModel: Gemma4GoodViewModel) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(24.dp),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("Submit feedback", fontWeight = FontWeight.Bold)
            OutlinedTextField(
                value = viewModel.feedbackInput,
                onValueChange = { viewModel.feedbackInput = it },
                placeholder = { Text("Correction or note for review…") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
                shape = RoundedCornerShape(16.dp),
            )
            Button(
                onClick = { viewModel.submitFeedback() },
                shape = RoundedCornerShape(999.dp),
            ) {
                Text("Submit feedback")
            }
            if (viewModel.feedbackStatus.isNotBlank()) {
                Text(
                    text = viewModel.feedbackStatus,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
fun SettingsAccordion(viewModel: Gemma4GoodViewModel) {
    var expanded by remember { mutableStateOf(false) }
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.3f))
    ) {
        Column {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { expanded = !expanded }
                    .padding(16.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("Settings", fontWeight = FontWeight.Bold)
                Icon(
                    if (expanded) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                    contentDescription = null
                )
            }
            AnimatedVisibility(visible = expanded) {
                Column(
                    modifier = Modifier
                        .padding(horizontal = 16.dp, vertical = 8.dp)
                        .padding(bottom = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    OutlinedTextField(
                        value = viewModel.userId,
                        onValueChange = { viewModel.userId = it },
                        label = { Text("User ID") },
                        modifier = Modifier.fillMaxWidth()
                    )
                    OutlinedTextField(
                        value = viewModel.region,
                        onValueChange = { viewModel.region = it },
                        label = { Text("Region") },
                        modifier = Modifier.fillMaxWidth()
                    )
                }
            }
        }
    }
}
