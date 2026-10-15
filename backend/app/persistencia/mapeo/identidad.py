"""Fila ↔ entidad para la identidad: la cuenta (§5.1), el club y la pertenencia
(§5.2) y el código de vinculación (§5.13).

Aparte de `desde_modelos.py`/`hacia_modelos.py` porque esos dos son del agregado
de planificación y la identidad tiene sus propias reglas de escritura: **este es
el único archivo de `app/` que asigna `token_version`, `refresh_rotation` o
`password_hash`** sobre una fila ya creada (lo comprueba
`tests/test_usuario_entidad.py` por AST), **ni `owner_id` ni `role`**
(`tests/test_equipo_entidad.py`), **ni `used_at`, `used_by` ni `revoked_at`**
(`tests/test_codigo_entidad.py`). Quien quiera cambiarlos se lo pide a la
entidad y la guarda por su repositorio.
"""
from __future__ import annotations

from app.dominio.entidades import CodigoDeVinculacion, Equipo, Pertenencia, Usuario
from app.persistencia.tablas.codigos import LinkCode
from app.persistencia.tablas.equipos import Team, TeamMember
from app.persistencia.tablas.usuarios import User


def usuario_desde_fila(fila: User) -> Usuario:
    return Usuario(
        id=fila.id, correo=fila.email, nombre=fila.name,
        hash_de_password=fila.password_hash, activo=fila.is_active,
        version_de_token=fila.token_version, rotacion_de_refresh=fila.refresh_rotation,
        creado=fila.created_at, ultimo_login=fila.last_login_at,
    )


def volcar_usuario(usuario: Usuario, fila: User) -> None:
    """Escribe en la fila **solo lo que la entidad gobierna**: las sesiones, el
    hash y el último acceso. El correo, el nombre y la baja de la cuenta tienen
    otras puertas (el alta y la edición del miembro)."""
    fila.password_hash = usuario.hash_de_password
    fila.token_version = usuario.version_de_token
    fila.refresh_rotation = usuario.rotacion_de_refresh
    fila.last_login_at = usuario.ultimo_login


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
