"""El macrociclo visto desde el API: endpoints, schemas y presentación.

Antes era `app/modules/plans/`. Lo que ha cambiado no es el nombre sino de
dónde salen los datos: las consultas y el filtro de acceso están en
`persistencia/repositorios/macrociclos.py`, y las reglas puras
(`semana_actual`, `estado_efectivo`) en `dominio/entidades/Macrociclo`.

La **inscripción** ya se escribe por su entidad (C9 punto 2, 2026-10-05):
`Macrociclo.inscribir()` → `RepositorioDeInscripciones.guardar`, con las rutas
en `router_nomina.py`. **Sus pruebas objetivo también** (punto 3, 2026-10-13):
`nomina.py` construye cada `PruebaObjetivo` y el repositorio arma las filas.
**Y la semana** (punto 4, mismo día): `semanas.py` recibe un `PlanDePrueba` de
`RepositorioDeSemanas`, les pide a las `Semana` que cambien y se las devuelve.
**Y el macrociclo en sí** (mismo día): `service.py` traduce el formulario a un
`Macrociclo` y `RepositorioDeMacrociclos.guardar` lo escribe. Con eso ninguna
escritura de esta rebanada arma filas del ORM: `service.py`, `nomina.py` y
`semanas.py` no importan tablas, y un test lo comprueba. Las que sí las leen son
`presentacion.py` (la respuesta se valida sobre ellas) y `resolver.py`.
"""
