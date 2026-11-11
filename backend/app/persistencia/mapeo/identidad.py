"""Fila ↔ entidad para la identidad: la cuenta (§5.1) y sus sesiones abiertas
(TODO-30), el club y la pertenencia (§5.2) y el código de vinculación (§5.13).

Aparte de `desde_modelos.py`/`hacia_modelos.py` porque esos dos son del agregado
de planificación y la identidad tiene sus propias reglas de escritura: **este es
el único archivo de `app/` que asigna `token_version`, `refresh_rotation`,
`expires_at` o `password_hash`** sobre una fila ya creada (lo comprueba
`tests/test_usuario_entidad.py` por AST), **ni `owner_id` ni `role`**
(`tests/test_equipo_entidad.py`), **ni `used_at`, `used_by` ni `revoked_at`**
(`tests/test_codigo_entidad.py`). Quien quiera cambiarlos se lo pide a la
entidad y la guarda por su repositorio.
"""
from __future__ import annotations

from sqlalchemy import Update, update
from sqlalchemy.orm.attributes import set_committed_value

from app.dominio.entidades import (
    CodigoDeVinculacion,
    Equipo,
    Pertenencia,
    SesionAbierta,
    Usuario,
)
from app.persistencia.tablas.codigos import LinkCode
from app.persistencia.tablas.equipos import Team, TeamMember
from app.persistencia.tablas.usuarios import OpenSession, User


def usuario_desde_fila(fila: User) -> Usuario:
    return Usuario(
        id=fila.id, correo=fila.email, nombre=fila.name,
        hash_de_password=fila.password_hash, activo=fila.is_active,
        version_de_token=fila.token_version,
        creado=fila.created_at, ultimo_login=fila.last_login_at,
        password_temporal=fila.password_temporal,
    )


def volcar_usuario(usuario: Usuario, fila: User) -> None:
    """Escribe en la fila **solo lo que la entidad gobierna**: el hash y el último
    acceso. El correo, el nombre y la baja de la cuenta tienen otras puertas (el
    alta y la edición del miembro). La rotación del refresh ya no es de la
    cuenta: es de cada `SesionAbierta` (TODO-30).

    **La generación tampoco**: sube con `subir_generacion`, relativa en SQL.
    Escribirla como «la leída + 1» dejaba que un corte leído antes de un cambio
    de contraseña pisara su subida, y la generación podía bajar (vuelta 3 del
    revisor de TODO-30)."""
    fila.password_hash = usuario.hash_de_password
    fila.last_login_at = usuario.ultimo_login


def subir_generacion(usuario: Usuario, fila: User) -> Update | None:
    """El `UPDATE token_version = token_version + n` de lo que la entidad subió
    desde que se construyó (`subidas_de_generacion`), o `None` si no subió.
    Relativo, así que dos cortes —o un corte y un cambio de contraseña— a la
    vez se suman."""
    cuanto = usuario.subidas_de_generacion()
    if cuanto <= 0:
        return None
    return (
        update(User)
        .where(User.id == fila.id)
        .values(token_version=User.token_version + cuanto)
        .execution_options(synchronize_session=False)
    )


def asentar_generacion(usuario: Usuario, fila: User) -> None:
    """Tras `subir_generacion`: la base ya la tiene; se apunta en la fila sin
    otro `UPDATE` (sumada a lo que la fila traiga: puede venir releída con la
    subida de otro). Quien confirma con `guardar` la relee de todas formas."""
    set_committed_value(fila, "token_version", fila.token_version + usuario.subidas_de_generacion())


def acceso_condicional(usuario: Usuario) -> Update:
    """El `UPDATE` del login: sella el acceso (y el rehash, si lo hubo) **solo
    si la contraseña sigue siendo la que se verificó** (`hash_leido`).

    Sin la condición, un login con la contraseña vieja que se solapara con un
    cambio de contraseña firmaba tokens de la generación nueva —quien probara la
    vieja en bucle seguía dentro después del cambio— y, con rehash, escribía el
    hash de la vieja encima del nuevo (revisor de TODO-30, anterior a él).
    """
    return (
        update(User)
        .where(User.id == usuario.id, User.password_hash == usuario.hash_leido)
        .values(last_login_at=usuario.ultimo_login, password_hash=usuario.hash_de_password)
        .execution_options(synchronize_session=False)
    )


def cambio_condicional(usuario: Usuario) -> Update:
    """El `UPDATE` del cambio de contraseña: el hash nuevo y la generación
    `token_version + 1` **en SQL**, solo si la contraseña sigue siendo la que se
    verificó (`hash_leido`).

    Escribir «la generación leída + 1» dejaba que dos cambios a la vez la
    subieran una sola vez, y la sesión del primero sobrevivía al cambio del
    segundo: si la víctima cambiaba la contraseña para echar al atacante, podía
    no echarlo (vuelta 2 del revisor de TODO-30, anterior a él).
    """
    return (
        update(User)
        .where(User.id == usuario.id, User.password_hash == usuario.hash_leido)
        .values(
            password_hash=usuario.hash_de_password, token_version=User.token_version + 1,
            # Viaja con el hash: es de ESA contraseña (TODO-27).
            password_temporal=usuario.password_temporal,
        )
        .execution_options(synchronize_session=False)
    )


def sesion_desde_fila(fila: OpenSession) -> SesionAbierta:
    return SesionAbierta(
        id=fila.id, usuario_id=fila.user_id, caduca=fila.expires_at,
        rotacion=fila.refresh_rotation, abierta=fila.created_at,
    )


def fila_de_sesion(sesion: SesionAbierta) -> OpenSession:
    """La fila de una sesión recién abierta: rotación 0 y su caducidad."""
    return OpenSession(
        id=sesion.id, user_id=sesion.usuario_id, refresh_rotation=sesion.rotacion,
        created_at=sesion.abierta, expires_at=sesion.caduca,
    )


def rotacion_condicional(sesion: SesionAbierta) -> Update:
    """El `UPDATE` que gasta la rotación de esa sesión **solo si nadie la gastó
    antes** (TODO-25, movido aquí con TODO-30).

    Leer-comparar-escribir en Python dejaba pasar dos refresh a la vez con la
    misma cookie. Con la condición en el `WHERE`, la base decide quién llegó
    primero y la otra ve 0 filas. Se compara contra `rotacion_leida` —de la que
    partió la entidad—, nunca contra una fila releída, que ya traería la de quien
    ganó. El `user_id` va en el `WHERE` aunque el `id` baste: ninguna consulta de
    sesiones se hace sin la cuenta.
    """
    if not sesion.roto():
        raise ValueError("La sesión no rotó: no hay nada que gastar")
    return (
        update(OpenSession)
        .where(
            OpenSession.id == sesion.id,
            OpenSession.user_id == sesion.usuario_id,
            OpenSession.refresh_rotation == sesion.rotacion_leida,
        )
        .values(refresh_rotation=sesion.rotacion, expires_at=sesion.caduca)
        .execution_options(synchronize_session=False)
    )


def equipo_desde_fila(fila: Team) -> Equipo:
    return Equipo(id=fila.id, nombre=fila.name, dueno_id=fila.owner_id, activo=fila.is_active)


def volcar_equipo(equipo: Equipo, fila: Team) -> None:
    """El nombre y el dueño: lo único que la entidad cambia. La baja del club no
    tiene puerta todavía."""
    fila.name = equipo.nombre
    fila.owner_id = equipo.dueno_id


def pertenencia_desde_fila(fila: TeamMember) -> Pertenencia:
    return Pertenencia(
        id=fila.id, usuario_id=fila.user_id, equipo_id=fila.team_id, rol=fila.role,
        activa=fila.is_active, desde=fila.joined_at,
    )


def volcar_pertenencia(pertenencia: Pertenencia, fila: TeamMember) -> None:
    """El rol y el acceso. **Ni el club ni la persona**: una pertenencia no se
    muda de equipo, se revoca y se crea otra."""
    fila.role = pertenencia.rol
    fila.is_active = pertenencia.activa


def codigo_desde_fila(fila: LinkCode) -> CodigoDeVinculacion:
    return CodigoDeVinculacion(
        id=fila.id, equipo_id=fila.team_id, ficha_id=fila.swimmer_id,
        emitido_por=fila.created_by, codigo=fila.code, caduca=fila.expires_at,
        correo_invitado=fila.invited_email, usado_en=fila.used_at,
        usado_por=fila.used_by, revocado_en=fila.revoked_at, creado=fila.created_at,
    )


def fila_de_codigo(codigo: CodigoDeVinculacion) -> LinkCode:
    """La fila de un código recién emitido. El equipo, la ficha y quien lo emite
    los puso `emitir()` desde la sesión, no desde la petición."""
    return LinkCode(
        team_id=codigo.equipo_id, swimmer_id=codigo.ficha_id,
        created_by=codigo.emitido_por, code=codigo.codigo, expires_at=codigo.caduca,
        invited_email=codigo.correo_invitado,
    )


def volcar_codigo(codigo: CodigoDeVinculacion, fila: LinkCode) -> None:
    """Solo el ciclo de vida: gastado, por quién y revocado. Lo demás no cambia
    después de emitirlo."""
    fila.used_at = codigo.usado_en
    fila.used_by = codigo.usado_por
    fila.revoked_at = codigo.revocado_en
