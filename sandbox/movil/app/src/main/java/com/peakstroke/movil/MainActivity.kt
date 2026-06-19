package com.peakstroke.movil

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.peakstroke.movil.engine.*

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = darkColorScheme()) {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    CalculatorScreen()
                }
            }
        }
    }
}

private val DISTANCES = listOf(50, 100, 200, 400, 800, 1500)
private val PROFILES = listOf("velocidad", "medio fondo", "fondo")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CalculatorScreen() {
    var distance by remember { mutableStateOf(100) }
    var stroke by remember { mutableStateOf("libre") }
    var current by remember { mutableStateOf("") }
    var goal by remember { mutableStateOf("") }
    var profile by remember { mutableStateOf(profileForEvent(100)) }
    var pool by remember { mutableStateOf("50") }

    var report by remember { mutableStateOf<Report?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    val strokes = allowedStrokes(distance)
    // Mantener estilo/perfil coherentes al cambiar la distancia.
    LaunchedEffect(distance) {
        if (stroke !in strokes) stroke = strokes.first()
        profile = profileForEvent(distance)
    }

    val scroll = rememberScrollState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(scroll)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Text("PeakStroke — Sandbox", style = MaterialTheme.typography.headlineSmall)
        Text("Zonas ancladas al ritmo · macro 15 sem", style = MaterialTheme.typography.bodySmall)

        Dropdown("Prueba (m)", distance.toString(), DISTANCES.map { it.toString() }) {
            distance = it.toInt()
        }
        Dropdown("Estilo", stroke, strokes) { stroke = it }

        OutlinedTextField(
            value = current, onValueChange = { current = it },
            label = { Text("Tiempo actual (mm:ss.cc)") },
            placeholder = { Text("1:05.30") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text),
            modifier = Modifier.fillMaxWidth()
        )
        OutlinedTextField(
            value = goal, onValueChange = { goal = it },
            label = { Text("Tiempo meta (mm:ss.cc)") },
            placeholder = { Text("1:02.00") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text),
            modifier = Modifier.fillMaxWidth()
        )

        Dropdown("Perfil", profile, PROFILES) { profile = it }

        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Piscina: ", modifier = Modifier.padding(end = 8.dp))
            FilterChip(selected = pool == "50", onClick = { pool = "50" }, label = { Text("50m") })
            Spacer(Modifier.width(8.dp))
            FilterChip(selected = pool == "25", onClick = { pool = "25" }, label = { Text("25m") })
        }

        Button(
            onClick = {
                error = null
                report = null
                try {
                    val c = parseTime(current)
                    val g = parseTime(goal)
                    val plan = ScienceEngine().generatePlan(
                        currentTime = c, goalTime = g, distance = distance,
                        stroke = stroke, pool = pool, profile = profile,
                    )
                    report = buildReport(plan)
                } catch (e: Exception) {
                    error = "Revisa los tiempos (usa mm:ss.cc o segundos). ${e.message ?: ""}"
                }
            },
            modifier = Modifier.fillMaxWidth()
        ) { Text("Calcular") }

        error?.let {
            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
                Text(it, modifier = Modifier.padding(12.dp), color = MaterialTheme.colorScheme.onErrorContainer)
            }
        }

        report?.let { r ->
            ResultCard("Resumen", r.diagnosis)
            ResultCard("Zonas (actual vs meta)", r.zonesTable)
            ResultCard("Semana a semana", r.weekTable)
            Text(r.footer, style = MaterialTheme.typography.bodySmall)
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun ResultCard(title: String, body: String) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(6.dp))
            Text(
                body,
                fontFamily = FontFamily.Monospace,
                fontSize = 12.sp,
                softWrap = false,
                modifier = Modifier.horizontalScroll(rememberScrollState())
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun Dropdown(label: String, selected: String, options: List<String>, onSelect: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = selected,
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            maxLines = 1,
            modifier = Modifier
                .fillMaxWidth()
                .menuAnchor(MenuAnchorType.PrimaryNotEditable)
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { opt ->
                DropdownMenuItem(
                    text = { Text(opt, overflow = TextOverflow.Ellipsis) },
                    onClick = {
                        onSelect(opt)
                        expanded = false
                    }
                )
            }
        }
    }
}
