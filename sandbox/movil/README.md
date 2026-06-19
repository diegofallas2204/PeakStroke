# PeakStroke Sandbox — App móvil

App de pruebas para Android. Pide los datos de un nadador (prueba, estilo, tiempo
actual, meta, perfil, piscina) y muestra el mismo reporte que `sandbox/run.py`:
diagnóstico, zonas (desde el tiempo actual vs. la meta) y la tabla semana a semana
del macrociclo de 15 semanas.

Es **solo para hacer cálculos rápidos desde el teléfono**. La lógica del motor es un
port directo de `sandbox/engine.py` (mismas tablas, mismas fórmulas). Verificado
contra la salida de Python (incluido el redondeo banker's de los km).

## Abrir y compilar

1. Abrir Android Studio → **Open** → seleccionar esta carpeta (`sandbox/movil`).
2. Android Studio sincroniza Gradle y genera el `gradle-wrapper.jar` y el
   `local.properties` (ruta del SDK) automáticamente en el primer *sync*.
3. Conectar el teléfono (depuración USB) o un emulador → **Run ▶**.

Para generar un APK instalable: **Build → Build Bundle(s)/APK(s) → Build APK(s)**.
El APK queda en `app/build/outputs/apk/debug/`.

Requisitos: Android Studio reciente (AGP 8.7), JDK 17, `minSdk 26` (Android 8.0+).

## Estructura

```
movil/
├── app/
│   └── src/main/
│       ├── java/com/peakstroke/movil/
│       │   ├── MainActivity.kt            # UI Compose (formulario + reporte)
│       │   └── engine/
│       │       ├── EngineTables.kt        # constantes científicas (port de engine.py)
│       │       ├── ScienceEngine.kt       # motor de progresión (generatePlan)
│       │       ├── TimeUtils.kt           # parseTime / fmt
│       │       └── Report.kt              # arma el texto del reporte (port de run.py)
│       └── res/...
├── build.gradle.kts · settings.gradle.kts · gradle.properties
```

## Mantener sincronizado con el sandbox

La fuente de verdad es Python (`sandbox/engine.py`); esta app es un espejo portátil.
Si cambian las tablas o la lógica del motor en Python, hay que reflejar el mismo
cambio en `engine/EngineTables.kt` y `engine/ScienceEngine.kt` (y en `Report.kt`
si cambia el formato de salida).

Para **comprobar que ambos motores coinciden**:

```bash
python sandbox/movil/parity/check_parity.py
```

Corre un set de casos por los dos motores y compara los resultados. Debe imprimir
`PARITY OK`. Si difieren, muestra exactamente qué línea/valor cambió, así sabés qué
te falta portar. (Requiere Java; descarga `kotlinc` una sola vez a una caché local.)

Detalle de la regla de coordinación: ver la sección **"Sandbox móvil — paridad de
motor"** en el `CLAUDE.md` raíz, que se carga en cada sesión de Claude Code.
