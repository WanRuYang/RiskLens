package good.gemma4good.android.ui

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.clickable
import androidx.compose.foundation.Image
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
import androidx.compose.foundation.layout.width
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
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.graphics.Color
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage
import good.gemma4good.android.R

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
        Image(
            painter = painterResource(id = R.drawable.risklens_logo),
            contentDescription = "RiskLens",
            modifier = Modifier
                .fillMaxWidth()
                .height(72.dp),
            contentScale = ContentScale.Fit,
            alignment = Alignment.CenterStart,
        )
        Text(
            text = "Analyze one product at a time from a URL, product label text, or uploaded product images. For food images, include the front label, ingredients, and Nutrition Facts table so RiskLens can show the RiskLens Score plus separate food flags.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        // Settings Accordion
        SettingsAccordion(viewModel)

        // Single composer to mirror the web identify flow.
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(24.dp),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
        ) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Text("Product input", fontWeight = FontWeight.Bold)
                Text(
                    text = "Type product text, paste a product URL, or attach product / ingredient / nutrition images.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                OutlinedTextField(
                    value = viewModel.messageInput,
                    onValueChange = { viewModel.messageInput = it },
                    placeholder = { Text("Type product text, paste a product URL, or attach label images…") },
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 3,
                    shape = RoundedCornerShape(16.dp),
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
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
            }
        }

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

        RiskLensScoreCard(viewModel.latestAnalysis?.risklensScore)
        RiskLensFlagsCard(viewModel.latestAnalysis?.risklensScore)
        ResultExplanationCard(viewModel)

        Spacer(modifier = Modifier.height(24.dp))
        Text(
            text = "Disclaimer: RiskLens is for informational screening only and does not provide medical, legal, or regulatory advice. Actual risk depends on dose, frequency, and individual sensitivity.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        FeedbackCard(viewModel)
    }
}

@Composable
private fun RiskLensScoreCard(score: good.gemma4good.contract.RiskLensScoreDto?) {
    if (score == null) return

    val grades = listOf(
        Triple("A", "Low", Color(0xFF2E9E5D)),
        Triple("B", "Mild", Color(0xFF2F9C95)),
        Triple("C", "Moderate", Color(0xFFF4C542)),
        Triple("D", "High", Color(0xFFF28A2E)),
        Triple("E", "Very high", Color(0xFFD94747)),
    )

    val primaryBlue = Color(0xFF1E5A7A)

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFFD8E2EA))
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(score.title, fontWeight = FontWeight.ExtraBold, color = primaryBlue, fontSize = 20.sp)
                Surface(
                    shape = RoundedCornerShape(999.dp),
                    color = Color(0xFFFEF3C7),
                ) {
                    Text(
                        text = "Grade ${score.score} - ${gradeLabel(score.score)} chemical/process concern",
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp),
                        style = MaterialTheme.typography.labelMedium,
                        color = Color(0xFF17212B),
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                grades.forEach { (grade, _, color) ->
                    val selected = grade == score.score
                    Surface(
                        modifier = Modifier
                            .weight(1f)
                            .height(48.dp),
                        shape = RoundedCornerShape(8.dp),
                        color = color.copy(alpha = if (selected) 1f else 0.35f),
                        border = if (selected) {
                            androidx.compose.foundation.BorderStroke(2.dp, Color.White)
                        } else {
                            null
                        },
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Text(
                                text = grade,
                                color = if (selected) Color.White else color.copy(alpha = 0.9f),
                                fontWeight = FontWeight.Black,
                                fontSize = if (selected) 18.sp else 16.sp
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
                        color = Color(0xFF5C6B78),
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            Text(
                text = score.description,
                style = MaterialTheme.typography.bodyMedium,
                color = Color(0xFF17212B),
                lineHeight = 20.sp
            )
            Text(
                text = "RiskLens Score reflects chemical, regulatory, contaminant, material-safety, and processing-related signals. Nutrition, allergen, and ingredient notes are shown separately as additional context.",
                style = MaterialTheme.typography.bodySmall,
                color = Color(0xFF5C6B78),
                lineHeight = 18.sp
            )
        }
    }
}

private fun gradeLabel(score: String): String {
    return when (score) {
        "A" -> "Low"
        "B" -> "Minor"
        "C" -> "Moderate"
        "D" -> "High"
        "E" -> "Very high"
        else -> "Unknown"
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun RiskLensFlagsCard(score: good.gemma4good.contract.RiskLensScoreDto?) {
    if (score == null) return
    val primaryBlue = Color(0xFF1E5A7A)
    val mutedSlate = Color(0xFF5C6B78)

    val scoringFlagTypes = setOf(
        "chemical_process",
        "regulatory",
        "contaminant",
        "material_safety",
        "confirmed_hazardous_ingredient",
    )
    
    val chemicalFlags = score.flags.filter { it.type in scoringFlagTypes }
    val nutritionFlags = score.flags.filter { it.type == "nutrition" }
    val allergenFlags = score.flags.filter { it.type == "allergen" }
    val ingredientFlags = score.flags.filter { it.type == "ingredient_note" }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFFD8E2EA))
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text("RiskLens Flags", fontWeight = FontWeight.ExtraBold, color = primaryBlue, fontSize = 18.sp)
            
            if (score.flags.isEmpty() && score.riskSignals.isEmpty() && score.nutritionFlags.isEmpty()) {
                Text(
                    text = "No additional hazard or food flags were identified from the available input.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = mutedSlate,
                )
            } else {
                @Composable
                fun FlagSection(title: String, flags: List<good.gemma4good.contract.RiskLensFlagDto>) {
                    if (flags.isEmpty()) return
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(
                            text = title,
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold,
                            color = primaryBlue
                        )
                        FlowRow(
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            flags.forEach { flag ->
                                val (bg, border, text) = when (flag.type) {
                                    in scoringFlagTypes -> Triple(Color(0xFFFEF3C7), Color(0xFFFCD34D), Color(0xFF78350F))
                                    "nutrition" -> Triple(Color(0xFFF3F4F6), Color(0xFFD1D5DB), Color(0xFF374151))
                                    "allergen" -> Triple(Color(0xFFF3F0FF), Color(0xFFB7A8F5), Color(0xFF44336B))
                                    else -> Triple(Color(0xFFFFF1F5), Color(0xFFFDA4AF), Color(0xFF7F1D1D))
                                }
                                
                                Surface(
                                    shape = RoundedCornerShape(999.dp),
                                    color = bg,
                                    border = androidx.compose.foundation.BorderStroke(1.dp, border)
                                ) {
                                    Text(
                                        text = flag.label,
                                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                                        style = MaterialTheme.typography.bodySmall,
                                        color = text,
                                        fontWeight = FontWeight.SemiBold
                                    )
                                }
                            }
                        }
                    }
                }

                FlagSection("Ingredient notes", ingredientFlags)
                FlagSection("Chemical & processing signals", chemicalFlags)
                FlagSection("Nutrition notes", nutritionFlags)
                FlagSection("Allergen notes", allergenFlags)

                Text(
                    text = "Informational notes do not affect the A-E RiskLens Score.",
                    style = MaterialTheme.typography.labelSmall,
                    color = mutedSlate,
                    fontStyle = androidx.compose.ui.text.font.FontStyle.Italic
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
            .height(320.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        shape = RoundedCornerShape(24.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFFD8E2EA)),
    ) {
        Column(modifier = Modifier.padding(horizontal = 20.dp, vertical = 16.dp)) {
            Text("Result explanation", fontWeight = FontWeight.ExtraBold, color = Color(0xFF1E5A7A), fontSize = 18.sp)
            if (viewModel.isProcessing) {
                Text(
                    text = "Gemma is processing...",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
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
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                ReportMarkdownText(
                    text = viewModel.resultExplanation.ifBlank {
                        "Upload a product image, paste a URL, or enter label text to begin."
                    }
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
private fun ReportMarkdownText(text: String) {
    val lines = text.lineSequence().toList()
    lines.forEach { rawLine ->
        val line = rawLine.trim()
        when {
            line.isBlank() -> Spacer(modifier = Modifier.height(4.dp))
            line == "---" -> Spacer(modifier = Modifier.height(6.dp))
            line.startsWith("## ") -> Text(
                text = stripInlineMarkdown(line.removePrefix("## ")),
                fontWeight = FontWeight.ExtraBold,
                fontSize = 16.sp,
                color = Color(0xFF17212B),
                modifier = Modifier.padding(top = 6.dp),
            )
            line.startsWith("### ") -> Text(
                text = stripInlineMarkdown(line.removePrefix("### ")),
                fontWeight = FontWeight.Bold,
                fontSize = 14.sp,
                color = Color(0xFF17212B),
                modifier = Modifier.padding(top = 4.dp),
            )
            line.startsWith("- ") -> Row(
                verticalAlignment = Alignment.Top,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("•", style = MaterialTheme.typography.bodySmall, color = Color(0xFF17212B))
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = stripInlineMarkdown(line.removePrefix("- ")),
                    style = MaterialTheme.typography.bodySmall,
                    color = Color(0xFF17212B),
                    modifier = Modifier.weight(1f),
                )
            }
            else -> Text(
                text = stripInlineMarkdown(line),
                style = MaterialTheme.typography.bodySmall,
                color = Color(0xFF17212B),
            )
        }
    }
}

private fun stripInlineMarkdown(value: String): String {
    return value
        .replace("**", "")
        .replace("__", "")
        .trim()
}

@Composable
private fun FeedbackCard(viewModel: Gemma4GoodViewModel) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        shape = RoundedCornerShape(24.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFFD8E2EA)),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("Submit feedback", fontWeight = FontWeight.Bold)
            Text(
                text = "If the response looks wrong, tell us what should be corrected, such as the product name, ingredient read, category, or a missing signal.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedTextField(
                value = viewModel.feedbackInput,
                onValueChange = { viewModel.feedbackInput = it },
                placeholder = { Text("Example: This is Oreo cookies, not cake mix.") },
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
