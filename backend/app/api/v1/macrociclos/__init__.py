"""El macrociclo visto desde el API: endpoints, schemas y presentación.

Antes era `app/modules/plans/`. Lo que ha cambiado no es el nombre sino de
dónde salen los datos: las consultas y el filtro de acceso están en
`persistencia/repositorios/macrociclos.py`, y las reglas puras
(`semana_actual`, `estado_efectivo`) en `dominio/entidades/Macrociclo`.

Las **escrituras** todavía construyen filas del ORM desde aquí. No es un
descuido: `Inscripcion`, `PruebaObjetivo` y `Semana` (§5.6–5.8) aún no son
entidades, así que no hay nada que `repo.guardar(...)` pudiera recibir. Cuando
existan, el camino de escritura pasa detrás del repositorio igual que ya lo
está el de lectura.
"""
