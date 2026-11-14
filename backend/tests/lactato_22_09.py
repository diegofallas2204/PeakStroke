"""Cuatro series reales del test de lactato del 22/09/2026, **anonimizadas**.

Son datos de salud de menores: aquí no hay nombres, edades ni marcas que
identifiquen a nadie. La correspondencia con la hoja del entrenador
(`Tabla Medición Camacho.xlsx`) vive solo en el vault (nota 26), fuera del repo.

Cada serie es 400 libre en piscina de 50 m, 30 s de pausa fija y las brazadas
del 2.º 50 de cada 100 (cuatro conteos por repetición).

- A01: la serie limpia de referencia (10×400): estado estable, deriva de
  brazada del +34 %. De ella salen los números que la suite tiene que dar.
- A06: la muestra contaminada (5.5 en la rep. 2) y la repetición 30 s más lenta.
- A08: lactato por debajo del reposo (0.9) en esfuerzo.
- A16: la FC que cae de 169 a 109 mientras sube el esfuerzo, y el salto de
  0.8 a 6.9 mmol/L entre repeticiones seguidas al mismo ritmo.
"""
from __future__ import annotations

# (tiempo s, lactato, fc, esfuerzo, brazadas)
A01 = {
    "referencia": 245.12, "propuesto": (304.0, 306.0),
    "reps": [
        (291.0, None, 170, 5.0, (31, 31, 30, 30)),
        (291.0, 3.3, 174, 5.0, (30, 30, 30, 30)),
        (292.0, None, 176, None, (30, 30, 30, 30)),
        (291.0, 2.5, 179, 5.0, (30, 30, 30, 30)),
        (295.0, None, 177, 6.0, (30, 30, 30, 31)),
        (297.0, None, 173, 7.0, (32, 33, 35, 36)),
        (293.0, 2.9, 175, 8.0, (38, 38, 38, 39)),
        (293.0, 3.0, 175, 8.0, (39, 39, 39, 40)),
        (293.0, None, 177, 8.0, (40, 40, 40, 41)),
        (289.0, 3.2, 180, 9.0, (41, 41, 41, 40)),
    ],
}

A06 = {
    "referencia": 264.99, "propuesto": (328.0, 331.0),
    "reps": [
        (316.0, None, 166, None, (42, 42, 42, 44)),
        (317.0, 5.5, 164, None, (44, 44, 44, 45)),
        (332.0, None, 155, None, (45, 44, 44, 45)),
        (327.0, None, 163, None, (44, 43, 45, 45)),
        (325.0, None, 163, 6.0, (44, 45, 46, 45)),
        (357.0, 1.3, 163, 7.0, (45, 45, 45, 46)),
        (320.0, None, 167, 7.0, (45, 45, 46, 46)),
        (316.0, 2.1, 170, 8.0, (45, 46, 44, 47)),
    ],
}

A08 = {
    "referencia": None, "propuesto": (342.0, 345.0),
    "reps": [
        (338.0, None, 133, 5.0, (44, 44, 42, 41)),
        (343.0, 2.8, 135, 5.0, (42, 43, 42, 44)),
        (341.0, None, 138, 6.0, (43, 44, 43, 43)),
        (340.0, 3.3, 137, 6.0, (43, 43, 43, 43)),
        (344.0, None, 138, 7.0, (44, 43, 42, 43)),
        (347.0, 1.6, 149, 8.0, (43, 44, 43, 42)),
        (343.0, None, 144, 8.0, (45, 43, 46, 45)),
        (336.0, 0.9, 136, 8.0, (43, 43, 44, 44)),
    ],
}

A16 = {
    "referencia": None, "propuesto": (340.0, 345.0),
    "reps": [
        (338.0, None, 166, 4.0, (42, 43, 43, 44)),
        (330.0, 2.0, 169, 5.0, (42, 43, 44, 44)),
        (323.0, None, 128, 6.0, (42, 45, 44, 44)),
        (317.0, None, 122, 7.0, (44, 46, 47, 45)),
        (315.0, 0.8, 115, 7.0, (45, 45, 45, 45)),
        (315.0, 6.9, 109, 8.0, (46, 45, 46, 45)),
        (321.0, None, 116, 8.0, (46, 45, 47, 48)),
        (319.0, 4.9, 128, 8.0, (45, 45, 45, 47)),
    ],
}
