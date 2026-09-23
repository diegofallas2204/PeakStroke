"""Las tablas de SQLAlchemy, del lado de fuera del dominio.

Hasta el paso 5 vivían en `app/modules/<feature>/models.py`, y por eso
`persistencia/mapeo/` tenía que **mirar hacia arriba** para traducir una fila a
una entidad. Con las tablas aquí, la dirección de dependencias del §2 del
rediseño se cumple de hecho y no solo por convención:

    api  →  persistencia  →  dominio          dominio → nada

Es también lo que hace innecesaria la vieja excepción de «lecturas explícitas de
modelos»: mientras ninguna tabla se declare fuera de aquí, leer una fila ajena es
mirar hacia abajo y no de lado. Lo comprueba `tests/test_dependencias_de_capas.py`.

**Sin reexportar nada a propósito.** Cada módulo se importa por su nombre
(`from app.persistencia.tablas.planes import Plan`), que es lo que hacen todos
los llamadores y `core/model_registry.py`. Un `__all__` aquí obligaría a añadir
cada tabla nueva en dos sitios, y el segundo es justo el que se olvida.
"""
