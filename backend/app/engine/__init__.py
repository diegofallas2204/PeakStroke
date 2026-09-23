"""Lo que queda de `app/engine/` tras la fusión de motores (C4).

**Ya no hay motor aquí.** El cálculo científico —zonas, plan, envolvente,
factibilidad, kilometraje, curvas, temporada e intervalos— vive en
`app/dominio/servicios/`, y los siete módulos que lo adaptaban se borraron.

Sobreviven dos que no son motor y que C4 no absorbe a propósito:

    aerobic.py     análisis de un test aeróbico (T-30, T-15, N×D, CSS). Lo usa
                   el endpoint de previsualización, que analiza sin guardar; la
                   escritura y la lectura ya pasan por `entidades.TestAerobico`.
    time_utils.py  conversión `m:ss.cc` ↔ segundos, que es formato y no ciencia.
"""
