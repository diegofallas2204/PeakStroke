"""El macrociclo visto desde el API: endpoints, schemas y presentación.

Antes era `app/modules/plans/`. Lo que ha cambiado no es el nombre sino de
dónde salen los datos: las consultas y el filtro de acceso están en
`persistencia/repositorios/macrociclos.py`, y las reglas puras
(`semana_actual`, `estado_efectivo`) en `dominio/entidades/Macrociclo`.

La **inscripción** ya se escribe por su entidad (C9 punto 2, 2026-10-05):
`Macrociclo.inscribir()` → `RepositorioDeInscripciones.guardar`, con las rutas
en `router_nomina.py`. **Sus pruebas objetivo también** (punto 3, 2026-10-13):
`nomina.py` construye cada `PruebaObjetivo` y el repositorio arma las filas.
Lo que queda fuera es la **semana**: apuntar un tiempo o un parón y recalcular
la curva (`semanas.py`) todavía toca filas del ORM desde aquí, hasta que
`Semana` (§5.8) sea entidad, el punto 4 de C9.
"""
