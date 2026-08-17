"""`MotorCientifico` — **el** motor. Uno solo (§6.1).

Hasta el paso 4 había dos, y el que el CLAUDE.md declaraba fuente de verdad no
corría: `ScienceEngine.generate_plan()` solo se llamaba desde los tests, y los
planes que se guardaban salían de `engine/progression.py`. Compartían las tablas
pero no el algoritmo, así que divergían solos — y ya lo habían hecho tres veces.

**La fusión no es quedarse con uno.** Cada mitad acierta en cosas distintas:

    de ScienceEngine          la distribución F_FASE por fase científica, la
                              extensión a ritmo seguro y la proyección anual
    de progression            `_acotar_ritmo_semanal` (difiere el excedente en
                              vez de recortarlo), la curva elegible, el reparto
                              normalizado al km que puso el entrenador y las
                              fases definidas por el usuario

La ciencia de uno, la parametrización del otro: **la forma la pone la ciencia y
los límites los pone el entrenador** (R6). Lo que el motor científico hacía y ya
no hace es imponer su propio kilometraje y su macro fijo de 15 semanas; eso
sobrevive como *aviso* (`kilometraje.banda_de_aviso`) y como *recomendación*
(`Factibilidad.semanas_recomendadas`), que es lo que siempre debieron ser.

Los tiempos van en segundos (`float`): ver la cabecera de `envolvente.py`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..entidades import lunes_de
from ..valores import (
    Estilo,
    Fase,
    Perfil,
    Piscina,
    Zona,
    factores_de_zona,
)
from ..valores.tiempo import PASO_DE_RELOJ_S, Duracion, Tiempo
from .curvas import Curva
from .envolvente import Envolvente, envolvente_de, evento_de_referencia, nivel_de
from .kilometraje import reparto_de_km
from .tablas import (
    MEJORA_ANUAL_ESPERADA,
    PROYECCION_SPRINT_A_100,
    TOLERANCIA_DE_ESTADO,
    factor_juvenil,
    margen_de_confianza,
)

# Tolerancia de visualización alrededor del objetivo de zona (solo interfaz).
TOLERANCIA_DE_ZONA = 0.01

# Fases por defecto del macrociclo tal y como las ve el entrenador: cuatro
# tramos con su color. NO son las cinco fases científicas de `Fase` — el reparto
# entre los dos vocabularios sigue sin decidirse (ver `Fase.desde_texto`).
FASES_POR_DEFECTO: list[tuple[str, str, float, str]] = [
    ("Base", "base", 0.30, "#22d3ee"),
    ("Construcción", "build", 0.40, "#8b5cf6"),
    ("Pico", "peak", 0.20, "#fbbf24"),
    ("Descenso", "taper", 0.10, "#34d399"),
]


@dataclass
class SemanaGenerada:
    """Una fila del plan: qué se espera nadar esa semana y a qué ritmos."""

    numero: int
    fecha: date
    tiempo_esperado: float
    ritmo_100: float
    km: float
    fase: str
    mejora_vs_anterior: float
    mejora_acumulada: float
    zonas: dict = field(default_factory=dict)
    deshabilitada: bool = False


@dataclass(frozen=True, slots=True)
class MacroProyectado:
    n_mac: int
    tiempo_inicial: float
    tiempo_final: float
    mejora_s: float
    mejora_pct: float


@dataclass(frozen=True, slots=True)
class ProyeccionAnual:
    """La temporada = N macrociclos encadenados, con re-test entre cada uno."""

    nivel: str
    n_macros: int
    inicio: float
    fin: float
    mejora_s: float
    mejora_pct: float
    rango_bajo_pct: float
    rango_alto_pct: float
    veredicto: str
    mensaje: str
    macros: list[MacroProyectado]


def fases_por_defecto(semanas: int) -> list[dict]:
    """Base / Construcción / Pico / Descenso repartidas sobre las semanas."""
    rangos: list[dict] = []
    inicio = 1
    quedan = semanas
    for i, (nombre, tipo, fraccion, color) in enumerate(FASES_POR_DEFECTO):
        if i == len(FASES_POR_DEFECTO) - 1:
            largo = quedan
        else:
            largo = max(1, round(semanas * fraccion))
            largo = min(largo, quedan - (len(FASES_POR_DEFECTO) - 1 - i))
        rangos.append({
            "name": nombre, "type": tipo, "color": color,
            "week_start": inicio, "week_end": inicio + largo - 1, "sort": i,
        })
        inicio += largo
        quedan -= largo
    return rangos


def _fase_de_la_semana(semana: int, fases: list[dict]) -> str:
    for f in fases:
        if f["week_start"] <= semana <= f["week_end"]:
            return f["name"]
    return fases[-1]["name"] if fases else "—"


def _estilo(texto: str) -> Estilo:
    """El estilo, cayendo en libre si el texto no se reconoce.

    Cae en vez de reventar porque el motor lee filas ya guardadas: rechazar un
    estilo raro es trabajo de `Prueba`, en la entrada, y hacerlo aquí
    convertiría un dato viejo en un 500 al abrir el plan.
    """
    try:
        return Estilo.desde_texto(texto)
    except ValueError:
        return Estilo.LIBRE


def _piscina(texto: str) -> Piscina:
    """La piscina, cayendo en la de 50 m. Mismo motivo que `_estilo`."""
    try:
        return Piscina.desde_texto(texto)
    except ValueError:
        return Piscina.LARGA


class MotorCientifico:
    """Todo lo que el sistema sabe calcular sobre un plan de natación."""

    # ── Zonas ───────────────────────────────────────────────────────────────

    def zonas(
        self,
        ritmo_carrera_100: float,
        distancia: int,
        estilo: str = "libre",
        piscina: str = "50",
        distancia_rep: int = 100,
    ) -> dict[str, dict[str, float] | None]:
        """Ritmo objetivo y salida de cada zona, para un ritmo de carrera dado.

            zona = ritmo_carrera × factor[perfil][distancia] (+ estilo) × piscina

        Una prescripción son **dos** números —a qué ritmo y cada cuánto—, así
        que cada zona trae también su `send_off` y su `rest`: separarlos
        garantizaba que la mitad se olvidara en algún consumidor.

        `min`/`max` son ±1 % alrededor del objetivo. No es ciencia: es el ancho
        de banda que la interfaz enseña.
        """
        perfil = Perfil.para_distancia(distancia)
        factores = factores_de_zona(perfil, distancia)
        correccion = _estilo(estilo).correccion_tpace_s
        factor_piscina = _piscina(piscina).factor(perfil)
        proporcion_rep = max(distancia_rep, 1) / 100.0

        salida: dict[str, dict[str, float] | None] = {}
        for zona in Zona.ordenadas():
            factor = factores.get(zona)
            if factor is None:
                salida[zona.value] = None
                continue
            objetivo = (ritmo_carrera_100 * factor + correccion) * factor_piscina
            trabajo = objetivo * proporcion_rep
            intervalo = self._al_reloj(trabajo + self._descanso(zona, trabajo))
            salida[zona.value] = {
                "min": round(objetivo * (1 - TOLERANCIA_DE_ZONA), 2),
                "mid": round(objetivo, 2),
                "max": round(objetivo * (1 + TOLERANCIA_DE_ZONA), 2),
                "send_off": intervalo,
                "rest": round(intervalo - trabajo, 2),
                "rep_distance": distancia_rep,
            }
        return salida

    def _descanso(self, zona: Zona, trabajo: float) -> float:
        return zona.descanso_para(Tiempo(trabajo)).segundos

    def _al_reloj(self, segundos: float) -> float:
        """Cuadra al reloj de pared, siempre hacia arriba (ver `Zona`)."""
        return Duracion(segundos).al_reloj(PASO_DE_RELOJ_S).segundos

    # ── Envolvente y factibilidad ───────────────────────────────────────────

    def envolvente(
        self, distancia: int, tiempo_actual: float, semanas: int,
        n_mac: int = 1, edad: int | None = None,
    ) -> Envolvente:
        return envolvente_de(distancia, tiempo_actual, semanas, n_mac=n_mac, edad=edad)

    # ── Plan ────────────────────────────────────────────────────────────────

    def generar_plan(
        self,
        distancia: int,
        tiempo_actual: float,
        tiempo_meta: float,
        semanas: int,
        km_totales: float,
        curva: str,
        inicio: date,
        semanas_por_micro: int = 4,
        fases: list[dict] | None = None,
        estilo: str = "libre",
        piscina: str = "50",
        n_mac: int = 1,
        edad: int | None = None,
    ) -> list[SemanaGenerada]:
        """El plan completo, semana a semana.

        La curva elegida da la FORMA; la ciencia pone los dos límites:

        * la mejora dentro del macro no pasa del techo realista — una meta más
          agresiva continúa en la extensión, no en esta curva;
        * ninguna semana mejora más rápido que el pico fisiológico.

        Así la curva cierra justo donde la tarjeta de factibilidad dice que es
        realista, y la diferencia entre curvas es solo de forma.
        """
        fases = fases or fases_por_defecto(semanas)
        km = reparto_de_km(semanas, km_totales, semanas_por_micro)
        env = self.envolvente(distancia, tiempo_actual, semanas, n_mac=n_mac, edad=edad)

        meta_del_macro = max(tiempo_meta, env.techo_realista)
        mejora = max(tiempo_actual - meta_del_macro, 0.0)
        forma = Curva.desde_clave(curva)
        ideal = [tiempo_actual - mejora * forma.progreso((i + 1) / semanas)
                 for i in range(semanas)]
        acotado = self._acotar_ritmo_semanal(ideal, tiempo_actual, env.pico_semanal_s)

        plan: list[SemanaGenerada] = []
        anterior = tiempo_actual
        for i in range(semanas):
            esperado = acotado[i]
            ritmo = esperado / (distancia / 100)
            plan.append(SemanaGenerada(
                numero=i + 1,
                fecha=lunes_de(inicio, i + 1),
                tiempo_esperado=round(esperado, 2),
                ritmo_100=round(ritmo, 2),
                km=km[i],
                fase=_fase_de_la_semana(i + 1, fases),
                mejora_vs_anterior=round(esperado - anterior, 2),
                mejora_acumulada=round(tiempo_actual - esperado, 2),
                zonas=self.zonas(ritmo, distancia, estilo, piscina),
            ))
            anterior = esperado
        return plan

    def generar_extension(
        self,
        distancia: int,
        tiempo_actual: float,
        techo_realista: float,
        tiempo_meta: float,
        ritmo_seguro: float,
        n_extra: int,
        inicio: date,
        semanas_del_macro: int,
        km_semanales: float,
        estilo: str = "libre",
        piscina: str = "50",
    ) -> list[SemanaGenerada]:
        """Las semanas de después, cuando la meta supera el techo del macro.

        Mientras el plan principal comprime la mejora pedida en las semanas que
        puso el entrenador, estas filas enseñan la continuación REALISTA: parten
        del techo y bajan al ritmo seguro hasta tocar la meta.
        """
        semanas: list[SemanaGenerada] = []
        anterior = techo_realista
        for j in range(1, n_extra + 1):
            numero = semanas_del_macro + j
            esperado = max(techo_realista - ritmo_seguro * j, tiempo_meta)
            ritmo = esperado / (distancia / 100)
            semanas.append(SemanaGenerada(
                numero=numero,
                fecha=lunes_de(inicio, numero),
                tiempo_esperado=round(esperado, 2),
                ritmo_100=round(ritmo, 2),
                km=km_semanales,
                fase=Fase.EXTENSION.etiqueta,
                mejora_vs_anterior=round(esperado - anterior, 2),
                mejora_acumulada=round(tiempo_actual - esperado, 2),
                zonas=self.zonas(ritmo, distancia, estilo, piscina),
            ))
            anterior = esperado
        return semanas

    def recalcular_desde(
        self,
        semanas: list[SemanaGenerada],
        desde_semana: int,
        tiempo_ancla: float,
        tiempo_meta: float,
        curva: str,
        distancia: int,
        deshabilitadas: set[int] | None = None,
        estilo: str = "libre",
        piscina: str = "50",
        n_mac: int = 1,
        edad: int | None = None,
    ) -> list[SemanaGenerada]:
        """Reancla la curva en un tiempo real y reparte lo que queda.

        Las semanas de parón (lesión, vacaciones) no progresan: mantienen el
        tiempo del ancla previa y su mejora se redistribuye entre las activas
        que quedan. El tramo restante lleva su propia envolvente —calculada
        sobre esas semanas, no sobre el macro entero—, así que una meta que ya
        no cabe cierra en el techo del tramo en vez de forzarse.
        """
        deshabilitadas = deshabilitadas or set()
        restantes = [s for s in semanas if s.numero >= desde_semana]
        activas = [s for s in restantes if s.numero not in deshabilitadas]
        if not activas:
            return semanas

        n_activas = len(activas)
        env = self.envolvente(distancia, tiempo_ancla, n_activas, n_mac=n_mac, edad=edad)
        meta_del_tramo = max(tiempo_meta, env.techo_realista)
        mejora = max(tiempo_ancla - meta_del_tramo, 0.0)
        forma = Curva.desde_clave(curva)
        ideal = [tiempo_ancla - mejora * forma.progreso((k + 1) / n_activas)
                 for k in range(n_activas)]
        acotado = self._acotar_ritmo_semanal(ideal, tiempo_ancla, env.pico_semanal_s)

        anterior = tiempo_ancla
        i = 0
        for semana in restantes:
            if semana.numero in deshabilitadas:
                semana.deshabilitada = True
                semana.tiempo_esperado = round(anterior, 2)
                semana.mejora_vs_anterior = 0.0
            else:
                esperado = acotado[i]
                i += 1
                semana.deshabilitada = False
                semana.mejora_vs_anterior = round(esperado - anterior, 2)
                semana.tiempo_esperado = round(esperado, 2)
                anterior = esperado
            ritmo = semana.tiempo_esperado / (distancia / 100)
            semana.ritmo_100 = round(ritmo, 2)
            semana.zonas = self.zonas(ritmo, distancia, estilo, piscina)
        return semanas

    def _acotar_ritmo_semanal(
        self, esperados: list[float], tiempo_actual: float, pico_semanal_s: float,
    ) -> list[float]:
        """Ninguna semana mejora más de lo que la fisiología permite.

        Y lo que no cabe **se difiere a las siguientes** en vez de perderse: es
        un modelo causal —esa ganancia ocurre después, no desaparece—, así que
        la curva cierra en el mismo punto y solo cambia de forma. La científica
        nunca se recorta: su semana más rápida es la que define el tope.
        """
        if pico_semanal_s <= 0:
            return list(esperados)
        pedidos: list[float] = []
        ideal_anterior = tiempo_actual
        for e in esperados:
            pedidos.append(ideal_anterior - e)
            ideal_anterior = e

        salida: list[float] = []
        anterior = tiempo_actual
        diferido = 0.0
        for pedido in pedidos:
            quiere = pedido + diferido
            toma = min(quiere, pico_semanal_s) if quiere > 0 else quiere
            diferido = quiere - toma
            anterior = anterior - toma
            salida.append(anterior)
        return salida

    def estado_de_rendimiento(self, tiempo_real: float, tiempo_esperado: float) -> str:
        """El nado real contra el plan: ahead | on_track | behind."""
        diff = (tiempo_real - tiempo_esperado) / tiempo_esperado
        if diff < -TOLERANCIA_DE_ESTADO:
            return "ahead"
        if diff > TOLERANCIA_DE_ESTADO:
            return "behind"
        return "on_track"

    def margen(self, semana: int) -> int:
        """± segundos de confianza de la predicción de esa semana (§20.3)."""
        return margen_de_confianza(semana)

    def ritmo_de_carrera_100(self, tiempo: float, distancia: int) -> float:
        """Ritmo /100 m REALISTA: un 50 no se sostiene al doble de distancia."""
        ingenuo = tiempo / (distancia / 100.0)
        return ingenuo * PROYECCION_SPRINT_A_100.get(distancia, 1.0)

    # ── Temporada ───────────────────────────────────────────────────────────

    def proyectar_temporada(
        self,
        tiempo_actual: float,
        distancia: int,
        n_macros: int = 3,
        edad: int | None = None,
        perfil: str | None = None,
    ) -> ProyeccionAnual:
        """`n_macros` encadenados, cada uno partiendo del techo del anterior.

        Modela el re-test entre macros, y el potencial se degrada macro a macro
        (§4.3). Es un TECHO —cada macro llega a su máximo—, no la media
        esperada, y por eso se compara contra el rango típico de la literatura
        ajustado por edad. No sustituye al plan semanal: es la vista con la que
        el entrenador reparte la meta de la temporada.
        """
        # El perfil por defecto sale del EVENTO de referencia y no de la
        # distancia pedida: coinciden en las seis de tabla y solo divergen en una
        # intermedia (un 150 se indexa al 100, pero su perfil es medio fondo).
        # Se conserva tal cual porque es lo que la proyección lleva calculando
        # desde siempre, y cuál de las dos manda se decide con el defecto 1 de
        # §10.4, que es el mismo tema. El entrenador puede forzarlo.
        elegido = (
            Perfil.desde_texto(perfil) if perfil
            else Perfil.para_distancia(evento_de_referencia(distancia))
        )
        nivel = nivel_de(distancia, tiempo_actual, elegido)

        macros: list[MacroProyectado] = []
        t = tiempo_actual
        for n in range(1, max(1, n_macros) + 1):
            env = envolvente_de(distancia, t, 15, n_mac=n, edad=edad, perfil=elegido)
            fin = env.techo_realista
            macros.append(MacroProyectado(
                n_mac=n, tiempo_inicial=round(t, 2), tiempo_final=round(fin, 2),
                mejora_s=round(t - fin, 2),
                mejora_pct=round((t - fin) / t * 100, 2) if t else 0.0,
            ))
            t = fin

        mejora = tiempo_actual - t
        pct = mejora / tiempo_actual if tiempo_actual else 0.0
        juventud = factor_juvenil(edad)
        bajo_base, alto_base = MEJORA_ANUAL_ESPERADA.get(nivel.value, (0.0, 1.0))
        bajo, alto = bajo_base * juventud, alto_base * juventud

        if pct <= alto:
            veredicto = "ok"
            mensaje = (
                f"Realista — el techo de temporada proyecta {pct*100:.2f}%, "
                f"dentro del rango típico {bajo*100:.1f}–{alto*100:.1f}% para {nivel.value}"
                + (f" (ajustado por edad ×{juventud:g})" if juventud != 1.0 else "") + "."
            )
        elif pct <= alto * 1.8:
            veredicto = "optimistic"
            mensaje = (
                f"Optimista — el techo de temporada ({pct*100:.2f}%) supera el "
                f"rango típico {bajo*100:.1f}–{alto*100:.1f}% ({nivel.value}). Es el máximo de "
                f"{len(macros)} macros perfectos, no la media esperada."
            )
        else:
            veredicto = "unrealistic"
            mensaje = (
                f"Poco realista — {pct*100:.2f}% excede con mucho el techo "
                f"típico {bajo*100:.1f}–{alto*100:.1f}% ({nivel.value}). Revisa el tiempo "
                f"actual o reparte la meta en más temporadas."
            )

        return ProyeccionAnual(
            nivel=nivel.value, n_macros=len(macros),
            inicio=round(tiempo_actual, 2), fin=round(t, 2),
            mejora_s=round(mejora, 2), mejora_pct=round(pct * 100, 2),
            rango_bajo_pct=round(bajo * 100, 2), rango_alto_pct=round(alto * 100, 2),
            veredicto=veredicto, mensaje=mensaje, macros=macros,
        )


MOTOR = MotorCientifico()

__all__ = [
    "MOTOR",
    "FASES_POR_DEFECTO",
    "MacroProyectado",
    "MotorCientifico",
    "ProyeccionAnual",
    "SemanaGenerada",
    "fases_por_defecto",
]
