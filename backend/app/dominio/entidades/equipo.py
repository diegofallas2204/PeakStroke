"""El club y la pertenencia de una persona a él (REDISENO §5.2).

**El rol cuelga de la pertenencia, no de la cuenta**: ser entrenador es algo
que se es *en* un club. Y ser **dueño** no es un tercer rol, es una columna del
club (`Equipo.dueno_id`): `EntrenadorEnJefe` sale de juntar las dos cosas, que
es lo que hace `Pertenencia.rol_de_dominio(es_dueno)` —la fábrica de §4.2, que
hasta el 2026-10-14 vivía suelta en `core/principal.rol_de`—.

Lo que recupera esta clase, que hasta hoy repartían `api/v1/equipos/service.py`
y `api/v1/auth/members.py` con `if` sobre filas:

- **quién puede ser dueño** (`transferir_propiedad`): entrenador, de este club
  y con el acceso vivo. La FK compuesta garantiza lo segundo; lo primero y lo
  tercero, solo esto. Un club cuyo dueño es un atleta —o una cuenta revocada—
  se queda sin nadie capaz de administrarlo;
- **al dueño no se le quita el acceso ni el rol de entrenador por la puerta de
  atrás** (`admite_cambio`): primero se transfiere la propiedad;
- revocar y restaurar una pertenencia, idempotentes y diciendo si cambiaron.

**Revocada ≠ sin club.** Una `Pertenencia` revocada sigue existiendo y sigue
diciendo de qué club es: quien la tiene **no** es una cuenta del pool. Esta
clase no tiene forma de expresar «sin club» —eso es no tener pertenencia—, así
que las dos cosas no se pueden confundir aquí; donde se confundían era en una
consulta que filtraba por `is_active` (ver `RepositorioDeEquipos.pertenencia`).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Final

from ..roles import AtletaRol, Entrenador, EntrenadorEnJefe, Rol
from .base import CamposGobernados, PorIdentidad

# Las dos claves que guarda `team_members.role`. Copiadas y no importadas porque
# el dominio no importa hacia fuera; `tests/test_equipo_entidad.py` las compara
# con las de `persistencia/tablas/equipos.py`.
ROL_ENTRENADOR: Final = "coach"
ROL_ATLETA: Final = "athlete"
ROLES_DE_PERTENENCIA: Final = (ROL_ENTRENADOR, ROL_ATLETA)

# Un rol no tiene estado —solo contesta—: tres instancias bastan.
_ENTRENADOR = Entrenador()
_JEFE = EntrenadorEnJefe()
_ATLETA = AtletaRol()


class OperacionDeEquipoImposible(ValueError):
    """Lo que el club no admite. El mensaje es para quien lo intentó (un 400)."""


def rol_para(clave: str, *, es_dueno: bool) -> Rol:
    """De la clave guardada y la propiedad del club al rol de la jerarquía.

    **Una clave desconocida revienta.** Es una fila corrupta —`role` solo se
    escribe a través de un `Literal["coach","athlete"]`— y romper aquí es fallar
    CERRADO: devolver algo parecido a un atleta dejaría al filtro por nadador
    sin reconocerlo, que es un rol sin acotar. Ninguna clave produce
    `Administrador` (R3: ese rol es solo el hueco en la jerarquía).
    """
    if clave == ROL_ENTRENADOR:
        return _JEFE if es_dueno else _ENTRENADOR
    if clave == ROL_ATLETA:
        return _ATLETA
    raise ValueError(f"Rol desconocido en una pertenencia: {clave!r}")


@dataclass(slots=True, eq=False)
class Pertenencia(PorIdentidad, CamposGobernados):
    """Una persona en un club, con un rol. Se compara por `id`.

    El rol y el acceso solo cambian por `cambiar_rol`, `revocar` y `restaurar`;
    la persona y el club, nunca: una pertenencia no se muda de equipo.
    """

    _GOBERNADOS: ClassVar[frozenset[str]] = frozenset({"usuario_id", "equipo_id", "rol", "activa"})

    usuario_id: int
    equipo_id: int
    rol: str
    id: int | None = None
    activa: bool = True
    desde: datetime | None = None

    def __post_init__(self) -> None:
        if self.rol not in ROLES_DE_PERTENENCIA:
            raise ValueError(f"Rol desconocido en una pertenencia: {self.rol!r}")

    @property
    def es_entrenador(self) -> bool:
        return self.rol == ROL_ENTRENADOR

    def rol_de_dominio(self, es_dueno: bool) -> Rol:
        return rol_para(self.rol, es_dueno=es_dueno)

    def revocar(self) -> bool:
        """Le quita el acceso al club. Devuelve si cambió algo (idempotente)."""
        cambio = self.activa
        object.__setattr__(self, "activa", False)
        return cambio

    def restaurar(self) -> bool:
        """Le devuelve el acceso. Devuelve si cambió algo (idempotente)."""
        cambio = not self.activa
        object.__setattr__(self, "activa", True)
        return cambio

    def cambiar_rol(self, rol: str) -> None:
        if rol not in ROLES_DE_PERTENENCIA:
            raise ValueError(f"Rol desconocido en una pertenencia: {rol!r}")
        object.__setattr__(self, "rol", rol)


@dataclass(slots=True, eq=False)
class Equipo(PorIdentidad, CamposGobernados):
    """Un club. Su dueño es una columna, no un rol (ver la cabecera).

    `dueno_id` solo cambia por `transferir_propiedad`: asignarlo a mano saltaría
    las tres comprobaciones.
    """

    _GOBERNADOS: ClassVar[frozenset[str]] = frozenset({"dueno_id"})

    nombre: str
    id: int | None = None
    dueno_id: int | None = None
    activo: bool = True

    def es_jefe(self, usuario_id: int) -> bool:
        return self.dueno_id is not None and self.dueno_id == usuario_id

    def renombrar(self, nombre: str) -> None:
        """Sin validar el texto: qué nombre vale lo decide el formulario (2 a 120
        caracteres). Una entidad más estricta que él daría un 500, no un 422."""
        self.nombre = nombre

    def transferir_propiedad(self, nuevo: Pertenencia | None) -> None:
        """Cede la propiedad a `nuevo`: entrenador, de este club y activo.

        Recibe la pertenencia **con las revocadas incluidas** a propósito: así se
        puede decir «esa cuenta tiene el acceso revocado» en vez de «no
        pertenece a este equipo», que sería falso. `None` es que no pertenece a
        ningún club. Las tres comprobaciones, en este orden, y sin tocar nada si
        alguna falla. También sirve para el primer dueño de un club recién
        creado (`seed.py`, `tools/ops.py crear-equipo`).
        """
        if nuevo is None or nuevo.equipo_id != self.id:
            raise OperacionDeEquipoImposible("Esa cuenta no pertenece a este equipo")
        if not nuevo.es_entrenador:
            raise OperacionDeEquipoImposible("Solo un entrenador puede ser dueño del equipo")
        if not nuevo.activa:
            raise OperacionDeEquipoImposible("Esa cuenta tiene el acceso revocado")
        object.__setattr__(self, "dueno_id", nuevo.usuario_id)

    def admite_cambio(
        self, pertenencia: Pertenencia, *, revocar: bool, a_atleta: bool,
    ) -> None:
        """Al dueño no se le revoca ni se le baja a atleta: primero se transfiere."""
        if self.es_jefe(pertenencia.usuario_id) and (revocar or a_atleta):
            raise OperacionDeEquipoImposible(
                "Ese entrenador es el dueño del equipo. Transfiere la propiedad primero.",
            )

    def admite_liberar(self, pertenencia: Pertenencia) -> None:
        """Si esa pertenencia se puede **liberar**: dejar la cuenta en el pool.

        Liberar no es revocar (TODO-26, decidido el 2026-10-14). Revocado es
        «echado, y de este club», y no entra en ningún otro hasta que lo
        restauren; liberado es «sin club», a propósito. Por eso solo se libera
        lo que **ya está revocado**: quien libera tuvo que echar antes, y el
        orden de los dos gestos queda en la auditoría.

        **Solo a un atleta.** Un entrenador deja filas que lo citan por FK
        compuesta contra su pertenencia —los códigos que emitió, a quién lleva,
        qué macrociclos—, y esas FKs son `ON DELETE CASCADE`: borrar la
        pertenencia **borraría esa historia en silencio**. Un atleta que antes fue
        entrenador también la tiene; eso no lo sabe la entidad, lo mira
        `RepositorioDeEquipos.historia_de_entrenador` (/cso de D1). Sin tocar
        nada si alguna comprobación falla, en este orden.
        """
        if pertenencia.equipo_id != self.id:
            raise OperacionDeEquipoImposible("Esa cuenta no pertenece a este equipo")
        if self.es_jefe(pertenencia.usuario_id):
            raise OperacionDeEquipoImposible(
                "Esa cuenta es la dueña del equipo. Transfiere la propiedad primero.",
            )
        if pertenencia.es_entrenador:
            raise OperacionDeEquipoImposible(
                "Solo se libera a un atleta: un entrenador deja historia en el club "
                "(códigos, asignaciones, macrociclos)",
            )
        if pertenencia.activa:
            raise OperacionDeEquipoImposible(
                "Primero revoca el acceso: solo se libera una pertenencia revocada",
            )

    def __str__(self) -> str:
        return self.nombre
