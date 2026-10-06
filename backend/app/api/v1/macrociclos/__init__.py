"""El macrociclo visto desde el API: endpoints, schemas y presentación.

Antes era `app/modules/plans/`. Lo que ha cambiado no es el nombre sino de
dónde salen los datos: las consultas y el filtro de acceso están en
`persistencia/repositorios/macrociclos.py`, y las reglas puras
(`semana_actual`, `estado_efectivo`) en `dominio/entidades/Macrociclo`.

La **inscripción** ya se escribe por su entidad (C9 punto 2, 2026-10-05):
`Macrociclo.inscribir()` → `RepositorioDeInscripciones.guardar`, con las rutas
en `router_nomina.py`. **Sus pruebas objetivo y semanas** todavía se construyen
como filas del ORM desde aquí: `PruebaObjetivo` y `Semana` (§5.7–5.8) son los
puntos 3 y 4 de C9. Cuando existan, ese camino pasa también detrás del
repositorio.
"""
