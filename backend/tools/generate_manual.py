"""Genera el manual en PDF de ajuste de predicciones de PeakStroke.

Reproducible: re-ejecutar regenera 'Manual_Ajuste_Predicciones.pdf' junto a
este archivo. Documentación, no código de runtime (reportlab es solo dev).

    .venv\\Scripts\\python -m tools.generate_manual
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, ListFlowable, ListItem, PageBreak, Paragraph,
    Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle,
)

OUT = Path(__file__).resolve().parent / "Manual_Ajuste_Predicciones.pdf"

INK = colors.HexColor("#0f172a")      # texto principal
MUTED = colors.HexColor("#475569")    # texto secundario
CYAN = colors.HexColor("#0e7490")     # acento Tier 1 / fondo
VIOLET = colors.HexColor("#6d28d9")   # acento Tier 2 / velocidad
AMBER = colors.HexColor("#b45309")    # avisos
LINE = colors.HexColor("#cbd5e1")
CODE_BG = colors.HexColor("#f1f5f9")
HEAD_BG = colors.HexColor("#0f172a")
ROW_BG = colors.HexColor("#f8fafc")

styles = getSampleStyleSheet()


def _style(name: str, **kw) -> ParagraphStyle:
    base = kw.pop("parent", styles["Normal"])
    return ParagraphStyle(name, parent=base, **kw)


H1 = _style("H1", fontName="Helvetica-Bold", fontSize=22, leading=26,
            textColor=INK, spaceAfter=4)
SUB = _style("SUB", fontSize=11, leading=15, textColor=MUTED, spaceAfter=14)
H2 = _style("H2", fontName="Helvetica-Bold", fontSize=14, leading=18,
            textColor=CYAN, spaceBefore=16, spaceAfter=6)
H3 = _style("H3", fontName="Helvetica-Bold", fontSize=11.5, leading=15,
            textColor=INK, spaceBefore=10, spaceAfter=3)
BODY = _style("BODY", fontSize=10, leading=15, textColor=INK, spaceAfter=6,
              alignment=TA_LEFT)
SMALL = _style("SMALL", fontSize=8.5, leading=12, textColor=MUTED)
CODE = _style("CODE", fontName="Courier", fontSize=8.5, leading=12,
              textColor=INK, backColor=CODE_BG, borderPadding=8,
              borderColor=LINE, borderWidth=0.5, spaceBefore=4, spaceAfter=10)
CELL = _style("CELL", fontSize=8.7, leading=11.5, textColor=INK)
CELLB = _style("CELLB", parent=CELL, fontName="Helvetica-Bold")
CELLH = _style("CELLH", fontSize=8.7, leading=11.5, textColor=colors.white,
               fontName="Helvetica-Bold")
CELLC = _style("CELLC", fontName="Courier", fontSize=8.3, leading=11.5, textColor=VIOLET)


def bullets(items: list[str], style=BODY) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(t, style), leftIndent=10, value="–") for t in items],
        bulletType="bullet", start="–", leftIndent=12,
    )


def param_table(rows: list[list], header: list[str], accent) -> Table:
    data = [[Paragraph(h, CELLH) for h in header]]
    for r in rows:
        data.append([
            Paragraph(r[0], CELLC),
            Paragraph(r[1], CELL),
            Paragraph(r[2], CELL),
            Paragraph(r[3], CELLB),
        ])
    t = Table(data, colWidths=[34 * mm, 58 * mm, 52 * mm, 22 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), accent),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_BG]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def callout(title: str, text: str, accent) -> Table:
    inner = [
        Paragraph(title, _style("ct", fontName="Helvetica-Bold", fontSize=9.5,
                                textColor=accent, spaceAfter=2)),
        Paragraph(text, _style("cb", fontSize=9, leading=13, textColor=INK)),
    ]
    t = Table([[inner]], colWidths=[166 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ROW_BG),
        ("LINEBEFORE", (0, 0), (0, -1), 3, accent),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def build() -> list:
    s: list = []
    s.append(Paragraph("PeakStroke", H1))
    s.append(Paragraph("Manual de ajuste de predicciones de entrenamiento", SUB))
    s.append(HRFlowable(width="100%", thickness=1.2, color=CYAN, spaceAfter=12))

    s.append(Paragraph("1. Qué controla qué", H2))
    s.append(Paragraph(
        "El motor produce <b>dos cosas independientes</b>. Entender la diferencia "
        "es la clave para ajustar sin dar palos de ciego:", BODY))
    s.append(bullets([
        "<b>La curva semana a semana</b> (la tabla de tiempos): solo interpola "
        "entre el tiempo actual y la meta. Su <i>forma</i> depende de la curva "
        "elegida (sigmoid / lineal / exponencial / logarítmica) y sus parámetros. "
        "No decide si la meta es realista, solo cómo se reparte la mejora en el tiempo.",
        "<b>El veredicto de factibilidad</b> (FACTIBLE / EXIGENTE / AGRESIVO): "
        "decide si la mejora pedida por microciclo es alcanzable. Aquí vive la "
        "<i>calidad</i> de la predicción. Si el simulador marca mal lo realista, "
        "se ajusta acá, no en la curva.",
    ]))
    s.append(callout(
        "Regla mental",
        "¿La <b>forma</b> de la bajada se ve rara? -> ajustá la curva (sección 4). "
        "¿El <b>veredicto</b> (agresivo/factible) está mal? -> ajustá los techos y "
        "ventanas (secciones 5 y 6).", CYAN))

    s.append(Paragraph("2. Correr el simulador", H2))
    s.append(Paragraph("Desde <font face='Courier'>peakstroke/backend</font>:", BODY))
    s.append(Preformatted(
        "REM  modo interactivo (recomendado para ajustar)\n"
        ".venv\\Scripts\\python -m tools.sim_cli\n\n"
        "REM  una sola corrida con datos directos\n"
        ".venv\\Scripts\\python -m tools.sim_cli --actual 1:05.0 --meta 1:01.0 "
        "--distancia 100 --estilo libre --semanas 16", CODE))
    s.append(Paragraph("Comandos dentro del modo interactivo:", BODY))
    s.append(bullets([
        "<font face='Courier'><b>n</b></font> — nuevo escenario (cambia tiempos, distancia, estilo, semanas, curva).",
        "<font face='Courier'><b>r</b></font> — recargar <font face='Courier'>tuning.json</font> y recalcular el mismo escenario.",
        "<font face='Courier'><b>z</b></font> — detalle de zonas de una semana (factor aplicado + min/mid/max).",
        "<font face='Courier'><b>t</b></font> — ver el tuning activo de un vistazo.",
        "<font face='Courier'><b>q</b></font> — salir.",
    ]))
    s.append(callout(
        "Flujo de ajuste",
        "1) Corré un escenario.  2) Abrí <b>tools/tuning.json</b> en otra ventana y "
        "cambiá un valor.  3) Volvé al simulador y presioná <b>r</b>.  4) Mirá cómo "
        "cambió el veredicto/curva. Repetí hasta que se sienta bien.", VIOLET))

    s.append(Paragraph("3. El archivo tuning.json", H2))
    s.append(Paragraph(
        "Vive en <font face='Courier'>tools/tuning.json</font>. Si lo borrás, se "
        "regenera con los valores por defecto del motor (útil para volver a cero). "
        "Tiene tres bloques:", BODY))
    s.append(bullets([
        "<b>curvas</b> — forma de la progresión semana a semana.",
        "<b>tier1_fondo</b> — realismo del veredicto para pruebas de <b>400 m o más</b> (regla aeróbica).",
        "<b>tier2_velocidad</b> — realismo del veredicto para pruebas de <b>menos de 400 m</b> (ventanas de velocidad).",
        "<b>zonas_entrenamiento</b> — los <b>tiempos de zona por semana</b> (R1, R2, MVO2, RL, V). "
        "Es la tabla que ve cada atleta; lo que más se afina.",
    ]))

    s.append(PageBreak())

    s.append(Paragraph("4. Parámetros de la curva", H2))
    s.append(Paragraph(
        "Solo cambian <i>cómo se reparte</i> la mejora en el tiempo, no el total. "
        "Lo más rápido suele ser elegir otra curva en el escenario (tecla "
        "<font face='Courier'>n</font>) antes que tocar estos números.", BODY))
    s.append(param_table([
        ["exponential_k", "Curva exponencial: mejora muy adelantada (atleta que "
         "retoma forma).", "Subir = mejora aún más temprana; bajar = más pareja.", "4.0"],
        ["logarithmic_scale", "Curva logarítmica: mejoras grandes al inicio y "
         "meseta (atleta cerca de su techo).", "Subir = arranque más brusco.", "9.0"],
        ["sigmoid_steepness", "Curva sigmoidal: lento-rápido-lento (adaptación, "
         "construcción, taper).", "Subir = inicio/fin más planos y centro más "
         "brusco; bajar = más lineal.", "10.0"],
    ], ["Parámetro", "Qué hace", "Cómo ajustar", "Default"], CYAN))
    s.append(Spacer(1, 6))
    s.append(Paragraph(
        "Cuándo usar cada curva: <b>sigmoid</b> (default, periodización clásica), "
        "<b>logarítmica</b> (atleta avanzado, poco margen), <b>exponencial</b> "
        "(regreso de lesión/pretemporada), <b>lineal</b> (referencia neutra).", SMALL))

    s.append(Paragraph("5. Parámetros de factibilidad (la predicción)", H2))
    s.append(Paragraph(
        "Aquí se decide el veredicto. Cada tier usa una lógica distinta.", BODY))

    s.append(Paragraph("5.1 Tier 1 — fondo (>= 400 m)", H3))
    s.append(Paragraph(
        "El techo de mejora realista por microciclo se calcula así:", BODY))
    s.append(Preformatted(
        "techo_verde = base_por_micro x factor_distancia x factor_estilo x ratio_aerobico\n"
        "agresivo    = requerido > techo_verde x multiplicador_techo", CODE))
    s.append(param_table([
        ["base_por_micro", "Mejora base en s/microciclo antes de factores.",
         "Sube/baja TODO el techo de fondo a la vez.", "1.0"],
        ["multiplicador_techo", "Margen entre EXIGENTE y AGRESIVO.",
         "Subir = más tolerante (menos agresivos).", "1.5"],
        ["factores_distancia", "Escala por distancia (50..1500). Más distancia, "
         "más segundos en juego.", "Ajustá la distancia que veas mal.", "100->0.45"],
        ["ratio_aerobico", "Proporción aeróbica de la prueba por distancia.",
         "Subir = se permite más mejora.", "100->0.325"],
        ["factores_estilo", "Escala por estilo (libre=1.0 ref).",
         "Subir el estilo que quede corto.", "pecho->0.68"],
    ], ["Parámetro", "Qué hace", "Cómo ajustar", "Default"], CYAN))

    s.append(Paragraph("5.2 Tier 2 — velocidad (< 400 m)", H3))
    s.append(Paragraph(
        "No usa fórmula: usa una <b>ventana realista</b> (min, max) de s/microciclo "
        "por cada combinación distancia+estilo. El veredicto compara lo requerido "
        "contra esa ventana.", BODY))
    s.append(param_table([
        ["ventanas", "Ventana (min, max) por clave \"distancia|estilo\", "
         "ej. \"100|libre\": [0.40, 0.60].", "Subir el max = objetivos más "
         "ambiciosos pasan a FACTIBLE.", "100|libre [0.40, 0.60]"],
        ["ventana_default", "Ventana usada si la combinación no está listada.",
         "Red de seguridad para casos raros.", "[0.20, 0.50]"],
        ["multiplicador_alerta", "Margen entre EXIGENTE y AGRESIVO.",
         "Subir = más tolerante.", "1.5"],
    ], ["Parámetro", "Qué hace", "Cómo ajustar", "Default"], VIOLET))
    s.append(Spacer(1, 4))
    s.append(callout(
        "Cómo se lee el veredicto",
        "<b>FACTIBLE</b>: requerido <= techo/max.   <b>EXIGENTE</b>: entre el "
        "techo y el techo x multiplicador.   <b>AGRESIVO</b>: lo supera; el "
        "simulador sugiere cuántas semanas harían falta.", AMBER))

    s.append(Paragraph("5.3 Tiempos de zona por semana (lo que más se afina)", H3))
    s.append(Paragraph(
        "Cada zona (R1, R2, MVO2, RL, V) tiene un par de factores (min, max) que "
        "se multiplican por el <b>pace/100m</b> del tiempo esperado de la semana "
        "para dar el rango objetivo de esa zona. Los factores se agrupan por "
        "<b>banda de distancia</b> (la clave es la distancia máxima de la banda: "
        "50, 100, 200, 500, 1000, 10000) porque a mayor distancia de prueba los "
        "factores se comprimen. <font face='Courier'>null</font> = la zona no se "
        "prescribe para esa distancia (aparece como \"no aplica\").", BODY))
    s.append(Preformatted(
        "tiempo_zona_min = pace_100m x factor_min\n"
        "tiempo_zona_max = pace_100m x factor_max\n"
        "ejemplo 400m, R1 [1.15, 1.20], pace 1:01.0  ->  1:10.2 - 1:13.2", CODE))
    s.append(param_table([
        ["zonas_entrenamiento.\"500\".R1", "Factor [min, max] de R1 para pruebas "
         "de hasta 500 m (incluye 400 m).", "Subir = zona más lenta (tiempos más "
         "altos); bajar = más rápida.", "[1.15, 1.20]"],
        ["...\"100\".V", "Factor de Velocidad para 100 m.",
         "Ajustá la zona+banda que no cuadre con la tabla del atleta.", "[1.02, 1.05]"],
        ["cualquier zona = null", "La zona no se entrena a esa distancia.",
         "Poné un [min, max] para activarla o null para ocultarla.", "RL/V en fondo"],
    ], ["Clave en el JSON", "Qué hace", "Cómo ajustar", "Default"], CYAN))
    s.append(Spacer(1, 4))
    s.append(callout(
        "Flujo recomendado para zonas",
        "Corré el escenario del atleta, mirá la <b>matriz de zonas</b> (o usá "
        "<b>z</b> para una semana con su factor), compará con la tabla real del "
        "atleta y subí/bajá el factor de la zona+banda que no cuadre. Recargá con "
        "<b>r</b>.", VIOLET))

    s.append(PageBreak())

    s.append(Paragraph("6. Recetas de ajuste", H2))
    s.append(Paragraph(
        "Síntomas típicos cuando \"los tiempos están un poco mal\" y qué tocar:", BODY))
    fixes = [
        ["Marca AGRESIVO un objetivo que en la práctica sí se logra",
         "Tier 2: subir el <b>max</b> de la ventana de esa distancia|estilo. "
         "Tier 1: subir <b>base_por_micro</b> o el factor de esa distancia/estilo."],
        ["Marca FACTIBLE objetivos que son irreales",
         "Bajar el <b>max</b> de la ventana (Tier 2) o <b>base_por_micro</b> / "
         "factores (Tier 1)."],
        ["Demasiados objetivos caen en EXIGENTE",
         "Subir <b>multiplicador_techo</b> (Tier 1) o <b>multiplicador_alerta</b> "
         "(Tier 2) para ampliar el rango factible."],
        ["Un solo estilo (ej. pecho) predice siempre mal",
         "Tier 1: ajustar su <b>factor_estilo</b>. Tier 2: ajustar sus ventanas "
         "por distancia."],
        ["La curva baja demasiado rápido al inicio o al final",
         "Cambiar de curva (sigmoid <-> lineal) o ajustar "
         "<b>sigmoid_steepness</b> / <b>exponential_k</b>."],
        ["Los tiempos de una zona no coinciden con la tabla del atleta",
         "Ajustar su factor [min, max] en <b>zonas_entrenamiento</b>, en la banda "
         "de distancia correspondiente (sección 5.3)."],
    ]
    data = [[Paragraph("Síntoma", CELLH), Paragraph("Qué ajustar", CELLH)]]
    for sym, fix in fixes:
        data.append([Paragraph(sym, CELLB), Paragraph(fix, CELL)])
    t = Table(data, colWidths=[70 * mm, 96 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AMBER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_BG]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]))
    s.append(t)
    s.append(Spacer(1, 6))
    s.append(callout(
        "Ajustá de a un parámetro",
        "Cambiá un valor, recargá con <b>r</b> y comprobá contra un caso real que "
        "conozcas (un atleta cuyo resultado ya sepas). Mover varios a la vez hace "
        "imposible saber qué causó la mejora.", CYAN))

    s.append(Paragraph("7. Hacer el cambio permanente", H2))
    s.append(Paragraph(
        "<font face='Courier'>tuning.json</font> ajusta el simulador. Cuando un "
        "valor te convenza y quieras que la app lo use siempre, copialo a la "
        "constante correspondiente del motor:", BODY))
    data = [[Paragraph("Parámetro del JSON", CELLH), Paragraph("Constante en el código", CELLH)]]
    mapping = [
        ["curvas.*", "app/engine/curves.py (EXP_K, LOG_SCALE, SIGMOID_STEEPNESS)"],
        ["tier1_fondo.base_por_micro", "app/engine/feasibility.py -> TIER1_BASE_PER_MICRO"],
        ["tier1_fondo.multiplicador_techo", "feasibility.py -> TIER1_CEILING_MULT"],
        ["tier1_fondo.factores_distancia", "feasibility.py -> DISTANCE_FACTORS"],
        ["tier1_fondo.ratio_aerobico", "feasibility.py -> AEROBIC_RATIO"],
        ["tier1_fondo.factores_estilo", "feasibility.py -> STROKE_FACTORS"],
        ["tier2_velocidad.ventanas", "feasibility.py -> SPEED_WINDOWS"],
        ["tier2_velocidad.multiplicador_alerta", "feasibility.py -> TIER2_WARNING_MULT"],
        ["zonas_entrenamiento", "app/engine/zones.py -> _ZONE_BANDS"],
    ]
    for a, b in mapping:
        data.append([Paragraph(a, CELLC), Paragraph(b, CELL)])
    t = Table(data, colWidths=[66 * mm, 100 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_BG]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
    ]))
    s.append(t)
    s.append(Spacer(1, 6))
    s.append(Paragraph(
        "Tras editar el código, validá con <font face='Courier'>"
        ".venv\\Scripts\\python -m pytest tests/</font> que los 33 tests del motor "
        "sigan en verde.", SMALL))

    s.append(Paragraph("8. Glosario", H2))
    s.append(bullets([
        "<b>Microciclo</b>: bloque de 3-4 semanas de carga + 1 de descarga. La "
        "unidad en la que se mide el ritmo de mejora.",
        "<b>Tier 1 / Tier 2</b>: fondo (>= 400 m, gobernado por la base aeróbica) "
        "vs. velocidad (< 400 m, ventanas empíricas).",
        "<b>Pace/100</b>: tiempo por cada 100 m; unidad central de todos los cálculos.",
        "<b>Techo verde</b>: máxima mejora por microciclo considerada plenamente "
        "realista; pasarlo lleva a EXIGENTE y luego a AGRESIVO.",
    ], style=SMALL))
    s.append(Spacer(1, 10))
    s.append(HRFlowable(width="100%", thickness=0.6, color=LINE, spaceAfter=6))
    s.append(Paragraph(
        "PeakStroke — generado con tools/generate_manual.py. Los valores por "
        "defecto reflejan el motor al momento de generar este PDF.", SMALL))
    return s


def main() -> None:
    doc = SimpleDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=22 * mm, rightMargin=22 * mm,
        topMargin=20 * mm, bottomMargin=18 * mm,
        title="PeakStroke — Manual de ajuste de predicciones",
        author="PeakStroke",
    )
    doc.build(build())
    print(f"PDF generado: {OUT}")


if __name__ == "__main__":
    main()
